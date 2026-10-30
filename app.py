# =========================================================
# NEOGUARD - LIVE FLASK BACKEND
# Port: 5001
# =========================================================

import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, Response

from backend.database.database import get_connection, initialize_database

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
sys.path.insert(0, str(ROOT / "dashboard"))  # for ai_care_engine

app = Flask(__name__)
initialize_database()

_ai = None


def get_ai():
    """Lazy-load the AI care engine (Groq if configured, local fallback otherwise)."""
    global _ai
    if _ai is None:
        try:
            from ai_care_engine import AICareEngine
        except Exception:
            from dashboard.ai_care_engine import AICareEngine
        _ai = AICareEngine()
    return _ai


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def insert_reading(name, value, unit):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO sensor_readings
           (sensor_name, value, unit, timestamp, valid)
           VALUES (?, ?, ?, ?, 1)""",
        (name, float(value), unit, datetime.now()),
    )
    conn.commit()
    conn.close()


def insert_alert(alert_type, message):
    conn = get_connection()
    cur = conn.cursor()
    # Skip duplicates: same unresolved alert already logged in the last 60 s
    cur.execute(
        """SELECT timestamp FROM alerts
           WHERE message=? AND resolved=0 ORDER BY id DESC LIMIT 1""",
        (message,),
    )
    last = cur.fetchone()
    if last:
        try:
            if (datetime.now() - datetime.fromisoformat(str(last["timestamp"]))).total_seconds() < 60:
                conn.close()
                return
        except ValueError:
            pass
    cur.execute(
        """INSERT INTO alerts
           (alert_type, severity, message, timestamp, resolved)
           VALUES (?, ?, ?, ?, 0)""",
        (alert_type, alert_type, message, datetime.now()),
    )
    conn.commit()
    conn.close()


def insert_event(event_type, description):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO events
           (event_type, description, timestamp)
           VALUES (?, ?, ?)""",
        (event_type, description, datetime.now()),
    )
    conn.commit()
    conn.close()


def latest_value(sensor_names):
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in sensor_names)
    cur.execute(
        f"""SELECT sensor_name, value, timestamp
            FROM sensor_readings
            WHERE sensor_name IN ({placeholders})
            ORDER BY id DESC LIMIT 1""",
        tuple(sensor_names),
    )
    row = cur.fetchone()
    conn.close()
    return row


def set_actuator(name, state):
    """Persist only a state transition to avoid duplicate log spam."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT state FROM actuator_logs
           WHERE actuator_name=? ORDER BY id DESC LIMIT 1""",
        (name,),
    )
    row = cur.fetchone()
    if not row or row["state"] != state:
        cur.execute(
            """INSERT INTO actuator_logs
               (actuator_name, state, duty_cycle, timestamp)
               VALUES (?, ?, 0, ?)""",
            (name, state, datetime.now()),
        )
        conn.commit()
    conn.close()


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.route("/")
def home():
    """Serve the tabbed NeoGuard web dashboard."""
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "system": "NeoGuard",
        "status": "ONLINE",
        "message": "NeoGuard live backend is running",
    })


# ---------------------------------------------------------
# LIVE ESP32 INGESTION
# ---------------------------------------------------------

@app.route("/api/sensor-data", methods=["POST"])
def sensor_data():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "JSON object required"}), 400

    try:
        ambient = float(payload["DHT_TEMP"])
        humidity = float(payload["DHT11"])
        movement = int(payload.get("ITG_MPU", 0))
        vibration = int(payload.get("MPU_VIBRATION", payload.get("VIBRATION", payload.get("SW420", 0))))
        fever = int(payload.get("FEVER", 0))
        fan_reported = payload.get("FAN")
        fan_reported = None if fan_reported is None else int(fan_reported)
    except (KeyError, TypeError, ValueError):
        return jsonify({
            "ok": False,
            "error": "Expected DHT_TEMP, DHT11, ITG_MPU, MPU_VIBRATION (or VIBRATION) and FEVER"
        }), 400

    # Final hardware semantics. NTC numeric field is deliberately ignored.
    insert_reading("DHT_TEMP", ambient, "°C")
    insert_reading("DHT11", humidity, "%")
    insert_reading("ITG_MPU", movement, "STATE")
    insert_reading("MPU_VIBRATION", vibration, "STATE")
    insert_reading("FEVER", fever, "STATE")

    # ------------------ Alerts (limits configurable from Settings) ------------------
    cfg = read_settings()
    hmin, hmax = float(cfg.get("humidity_min", 30)), float(cfg.get("humidity_max", 70))
    tmin, tmax = float(cfg.get("temp_low", 15)), float(cfg.get("temp_high", 30))
    if fever and str(cfg.get("fever_alert", "1")) == "1":
        insert_alert("CRITICAL", "FEVER SIGNAL DETECTED — verify sensor and follow safety procedure")
    elif ambient >= tmax + 5 or ambient <= tmin - 5:
        insert_alert("CRITICAL", f"Critical DHT22 ambient temperature: {ambient:.1f} °C")
    elif ambient > tmax or ambient < tmin:
        insert_alert("HIGH", f"DHT22 ambient temperature outside configured range: {ambient:.1f} °C")

    if humidity >= min(100, hmax + 15) or humidity <= max(0, hmin - 10):
        insert_alert("CRITICAL", f"Critical DHT22 humidity: {humidity:.1f} %")
    elif humidity > hmax or humidity < hmin:
        insert_alert("WARNING", f"DHT22 humidity outside configured band: {humidity:.1f} %")

    if movement:
        insert_alert("WARNING", "MPU6050 movement detected")
        insert_event("ITG_MPU", "Movement detected")

    if vibration:
        insert_alert("WARNING", "MPU6050 vibration detected (dynamic acceleration)")
        insert_event("MPU_VIBRATION", "Vibration detected by MPU6050")

    # ------------------ Physical actuator mirror ------------------
    # ESP32 is the physical source of truth. The server mirrors FEVER so the
    # GUI displays exactly what the local safety logic is doing.
    set_actuator("BUZZER", "ON" if fever else "OFF")
    set_actuator("LED", "ON" if fever else "OFF")
    # Fan: the ESP32 decides locally from the DHT22 reading and the dashboard
    # threshold; the server mirrors what the hardware reports. If the node does
    # not report FAN (older firmware), derive it from the same threshold.
    fan_threshold = float(cfg.get("fan_on_temp", 28))
    fan_on = bool(fan_reported) if fan_reported is not None else ambient >= fan_threshold
    set_actuator("FAN", "ON" if fan_on else "OFF")

    previous = latest_value(["FEVER"])
    # latest_value now returns the just-inserted row, so determine transition
    # using the second newest record.
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT value FROM sensor_readings
        WHERE sensor_name='FEVER'
        ORDER BY id DESC LIMIT 2
    """)
    fever_rows = cur.fetchall()
    conn.close()

    previous_fever = int(fever_rows[1]["value"]) if len(fever_rows) > 1 else None
    if previous_fever != fever:
        insert_event(
            "EMERGENCY",
            "Emergency mode activated" if fever else "Emergency mode deactivated",
        )

    return jsonify({
        "ok": True,
        "status": "UPDATED",
        "sensors": {
            "DHT_TEMP": ambient,
            "DHT11": humidity,
            "ITG_MPU": movement,
            "MPU_VIBRATION": vibration,
            "VIBRATION": vibration,
            "FEVER": fever,
        },
        "actuators": {
            "LED": "ON" if fever else "OFF",
            "BUZZER": "ON" if fever else "OFF",
            "FAN": "ON" if fan_on else "OFF",
        },
        "config": {"fan_on_temp": fan_threshold},
    }), 200


# ---------------------------------------------------------
# Sensor APIs
# ---------------------------------------------------------

@app.route("/api/sensors/latest")
def latest_sensors():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sensor_name, value, unit, timestamp, valid
        FROM sensor_readings
        WHERE id IN (
            SELECT MAX(id) FROM sensor_readings GROUP BY sensor_name
        )
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/sensors/history")
def sensor_history():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sensor_name, value, unit, timestamp, valid
        FROM sensor_readings ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------
# SETTINGS, ACKNOWLEDGEMENTS, HISTORY, REPORTS AND CARE LOG
# ---------------------------------------------------------
DEFAULT_SETTINGS = {"humidity_min": "30", "humidity_max": "70", "fever_alert": "1", "temp_low": "15", "temp_high": "30", "fan_on_temp": "28", "baby_name": "Baby", "sound_enabled": "1", "browser_notifications": "1"}

def read_settings():
    conn=get_connection(); cur=conn.cursor(); cur.execute("SELECT key,value FROM app_settings")
    values={r["key"]:r["value"] for r in cur.fetchall()}; conn.close()
    return {**DEFAULT_SETTINGS, **values}

@app.route('/api/settings', methods=['GET','POST'])
def api_settings():
    if request.method=='GET': return jsonify(read_settings())
    body=request.get_json(silent=True) or {}
    allowed=set(DEFAULT_SETTINGS)
    conn=get_connection(); cur=conn.cursor()
    for k,v in body.items():
        if k in allowed:
            cur.execute('INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
    conn.commit(); conn.close()
    insert_event('SETTINGS','Dashboard thresholds/settings updated')
    return jsonify({"ok":True,"settings":read_settings()})

@app.route('/api/alerts/<int:alert_id>/ack', methods=['POST'])
def acknowledge_alert(alert_id):
    conn=get_connection(); cur=conn.cursor(); cur.execute('UPDATE alerts SET resolved=1 WHERE id=?',(alert_id,)); changed=cur.rowcount; conn.commit(); conn.close()
    if changed: insert_event('ALERT_ACKNOWLEDGED',f'Alert #{alert_id} marked handled')
    return jsonify({"ok":bool(changed)}), (200 if changed else 404)

@app.route('/api/care-log', methods=['GET','POST'])
def api_care_log():
    conn=get_connection(); cur=conn.cursor()
    if request.method=='POST':
        body=request.get_json(silent=True) or {}; note=str(body.get('note','')).strip(); category=str(body.get('category','Care')).strip()[:40] or 'Care'
        if not note: conn.close(); return jsonify({"ok":False,"error":"Note is required"}),400
        cur.execute('INSERT INTO care_log(note,category,timestamp) VALUES(?,?,?)',(note,category,datetime.now().isoformat(timespec='seconds'))); conn.commit()
        insert_event('CARE_LOG',f'{category}: {note[:120]}')
    cur.execute('SELECT id,note,category,timestamp FROM care_log ORDER BY id DESC LIMIT 500'); rows=[dict(r) for r in cur.fetchall()]; conn.close()
    return jsonify(rows)

SENSOR_LABELS = {'DHT_TEMP': 'Room temperature (DHT22)', 'DHT11': 'Humidity (DHT22)',
                 'ITG_MPU': 'Movement (MPU6050)', 'MPU_VIBRATION': 'Vibration (MPU6050)', 'FEVER': 'NTC alert signal'}
def sensor_label(n): return SENSOR_LABELS.get(n, n)

RANGE_HOURS = {'hour': 1, 'day': 24, 'week': 24*7, 'month': 24*30, 'year': 24*365, 'all': None}

def _range_cutoff(period):
    """Cutoff as a local-time string. Readings are stored with datetime.now()
    (local time), so the cutoff MUST also be local time (not SQLite's UTC now)."""
    hours = RANGE_HOURS.get(period, 24)
    if hours is None:
        return None
    return (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

def history_rows(period='day', sensor=None):
    cutoff = _range_cutoff(period)
    conn=get_connection(); cur=conn.cursor(); query='SELECT sensor_name,value,unit,timestamp,valid FROM sensor_readings WHERE 1=1'; args=[]
    if cutoff: query += " AND timestamp >= ?"; args.append(cutoff)
    if sensor: query+=' AND sensor_name=?'; args.append(sensor)
    # newest rows first so the LIMIT never cuts off recent data, then restore order
    query+=' ORDER BY timestamp DESC LIMIT 20000'; cur.execute(query,args); rows=[dict(r) for r in cur.fetchall()]; conn.close(); rows.reverse(); return rows

@app.route('/api/history/series')
def api_history_series():
    """Time-bucketed averages for charts, so every range covers its FULL window."""
    period = request.args.get('range', 'day')
    cutoff = _range_cutoff(period)
    now = datetime.now()
    conn = get_connection(); cur = conn.cursor()
    names = ['DHT_TEMP', 'DHT11']
    if cutoff:
        start = datetime.strptime(cutoff, '%Y-%m-%d %H:%M:%S')
    else:
        cur.execute("SELECT MIN(timestamp) AS t FROM sensor_readings WHERE sensor_name IN (?,?)", names)
        r = cur.fetchone()
        try: start = datetime.fromisoformat(str(r['t'])) if r and r['t'] else now - timedelta(hours=1)
        except ValueError: start = now - timedelta(hours=1)
    span = max(60, (now - start).total_seconds())
    size = max(1, int(span / 120))            # ~120 points across the window
    out = {'start': start.isoformat(timespec='seconds'), 'end': now.isoformat(timespec='seconds'), 'bucket_seconds': size, 'series': {n: [] for n in names}}
    cur.execute(f"""SELECT sensor_name, CAST(strftime('%s', timestamp) AS INTEGER)/? AS b, AVG(value) AS v, MIN(value) AS lo, MAX(value) AS hi, COUNT(*) AS n
                    FROM sensor_readings WHERE sensor_name IN (?,?) AND valid=1 AND timestamp >= ?
                    GROUP BY sensor_name, b ORDER BY b""", (size, *names, start.strftime('%Y-%m-%d %H:%M:%S')))
    for r in cur.fetchall():
        # bucket start is epoch-in-UTC-naive; timestamps were stored local, strftime('%s') treats them as UTC, so reconstruct naively
        t = datetime.utcfromtimestamp(r['b'] * size)
        out['series'][r['sensor_name']].append({'t': t.isoformat(timespec='seconds'), 'v': r['v'], 'lo': r['lo'], 'hi': r['hi'], 'n': r['n']})
    conn.close()
    return jsonify(out)

@app.route('/api/history')
def api_history():
    return jsonify(history_rows(request.args.get('range','day'),request.args.get('sensor')))

# ---------------------------------------------------------
# CUSTOMER-FRIENDLY REPORTS (plain language, one row per time slot)
# ---------------------------------------------------------
RANGE_TITLES = {'hour': 'Last hour', 'day': 'Last 24 hours', 'week': 'Last 7 days',
                'month': 'Last 30 days', 'year': 'Last 12 months', 'all': 'All recorded data'}

def _bucket_size(period, start, now):
    fixed = {'hour': 60, 'day': 900, 'week': 3600, 'month': 21600, 'year': 86400}
    if period in fixed: return fixed[period]
    return max(60, int((now - start).total_seconds() / 300))

def _fmt_slot(dt, size):
    if size >= 86400: return dt.strftime('%d %b %Y'), ''
    return dt.strftime('%d %b %Y'), dt.strftime('%I:%M %p').lstrip('0')

def _plain_alert(msg):
    m = msg or ''
    if m.startswith('FEVER SIGNAL'): return 'Fever alert signal was triggered. Please check on your baby and verify the sensor.', 'Urgent'
    if 'humidity' in m.lower():
        return ('Room humidity was extremely high or low.' if m.startswith('Critical') else 'Room humidity was outside the comfortable range.'), ('Urgent' if m.startswith('Critical') else 'Warning')
    if 'temperature' in m.lower():
        return ('Room temperature was extremely high or low.' if m.startswith('Critical') else 'Room temperature was outside the comfortable range.'), ('Urgent' if m.startswith('Critical') else 'Warning')
    if 'movement' in m.lower(): return 'Movement was detected in the crib area.', 'Notice'
    if 'vibration' in m.lower(): return 'Vibration was detected in the crib area.', 'Notice'
    return m, 'Notice'

def build_report(period):
    period = period if period in RANGE_HOURS else 'day'
    now = datetime.now(); cfg = read_settings()
    hmin, hmax = float(cfg.get('humidity_min', 30)), float(cfg.get('humidity_max', 70))
    tmin, tmax = float(cfg.get('temp_low', 15)), float(cfg.get('temp_high', 30))
    cutoff = _range_cutoff(period)
    conn = get_connection(); cur = conn.cursor()
    if cutoff: start = datetime.strptime(cutoff, '%Y-%m-%d %H:%M:%S')
    else:
        cur.execute("SELECT MIN(timestamp) AS t FROM sensor_readings"); r = cur.fetchone()
        try: start = datetime.fromisoformat(str(r['t'])) if r and r['t'] else now
        except ValueError: start = now
    size = _bucket_size(period, start, now)
    cur.execute("""SELECT CAST(strftime('%s', timestamp) AS INTEGER)/? AS b,
        AVG(CASE WHEN sensor_name='DHT_TEMP' THEN value END) AS temp,
        AVG(CASE WHEN sensor_name='DHT11' THEN value END) AS hum,
        MAX(CASE WHEN sensor_name='ITG_MPU' THEN value END) AS mov,
        MAX(CASE WHEN sensor_name IN ('MPU_VIBRATION','VIBRATION','SW420') THEN value END) AS vib,
        MAX(CASE WHEN sensor_name='FEVER' THEN value END) AS fev
        FROM sensor_readings WHERE valid=1 AND timestamp >= ? GROUP BY b ORDER BY b""",
        (size, start.strftime('%Y-%m-%d %H:%M:%S')))
    rows = []; temps = []; hums = []; fever_slots = move_slots = vib_slots = 0
    for r in cur.fetchall():
        dt = datetime.utcfromtimestamp(r['b'] * size); d, t = _fmt_slot(dt, size)
        temp, hum = r['temp'], r['hum']
        fev, mov, vib = bool(r['fev']), bool(r['mov']), bool(r['vib'])
        notes = []
        if fev: notes.append('Fever alert signal')
        if hum is not None and hum > hmax: notes.append('Humidity too high')
        if hum is not None and hum < hmin: notes.append('Humidity too low')
        if temp is not None and temp > tmax: notes.append('Room too warm')
        if temp is not None and temp < tmin: notes.append('Room too cool')
        if mov: notes.append('Movement')
        if vib: notes.append('Vibration')
        if temp is not None: temps.append(temp)
        if hum is not None: hums.append(hum)
        fever_slots += fev; move_slots += mov; vib_slots += vib
        status = 'Needs attention' if (fev or any(n.startswith(('Humidity','Room')) for n in notes)) else ('Activity' if (mov or vib) else 'All good')
        rows.append({'date': d, 'time': t, 'temperature': None if temp is None else round(temp, 1),
                     'humidity': None if hum is None else round(hum), 'movement': 'Yes' if mov else 'No',
                     'vibration': 'Yes' if vib else 'No', 'fever_alert': 'YES' if fev else 'No',
                     'status': status, 'notes': ', '.join(notes) or '-'})
    # alerts, grouped by plain-language meaning
    q = "SELECT severity,message,timestamp,resolved FROM alerts"; args = []
    if cutoff: q += " WHERE timestamp >= ?"; args.append(cutoff)
    cur.execute(q + " ORDER BY timestamp", args); groups = {}
    for a in cur.fetchall():
        text, level = _plain_alert(a['message']); g = groups.setdefault(text, {'what': text, 'level': level, 'times': 0, 'first': a['timestamp'], 'last': a['timestamp'], 'open': 0})
        g['times'] += 1; g['last'] = a['timestamp']; g['open'] += 0 if a['resolved'] else 1
    def nice(ts):
        try: return datetime.fromisoformat(str(ts)).strftime('%d %b %Y, %I:%M %p').replace(' 0', ' ')
        except ValueError: return str(ts)
    order = {'Urgent': 0, 'Warning': 1, 'Notice': 2}
    alerts = sorted(({'what': g['what'], 'level': g['level'], 'times': g['times'], 'first': nice(g['first']), 'last': nice(g['last']),
                      'handled': 'Yes' if g['open'] == 0 else 'Not yet'} for g in groups.values()), key=lambda g: (order[g['level']], -g['times']))
    q = "SELECT category,note,timestamp FROM care_log"; args = []
    if cutoff: q += " WHERE timestamp >= ?"; args.append(cutoff)
    cur.execute(q + " ORDER BY timestamp", args)
    notes = [{'when': nice(r['timestamp']), 'category': r['category'], 'note': r['note']} for r in cur.fetchall()]
    conn.close()
    avg = lambda v: (sum(v) / len(v)) if v else None
    summary = {
        'title': RANGE_TITLES[period], 'from': start.strftime('%d %b %Y, %I:%M %p').replace(' 0', ' '), 'to': now.strftime('%d %b %Y, %I:%M %p').replace(' 0', ' '),
        'generated': now.strftime('%d %b %Y, %I:%M %p'), 'slot_minutes': size // 60 if size < 86400 else None, 'slot_label': ('1 day' if size >= 86400 else (f'{size//3600} hour' + ('s' if size//3600 > 1 else '') if size >= 3600 else f'{max(1,size//60)} min')),
        'avg_temp': None if not temps else round(avg(temps), 1), 'min_temp': None if not temps else round(min(temps), 1), 'max_temp': None if not temps else round(max(temps), 1),
        'avg_hum': None if not hums else round(avg(hums)), 'min_hum': None if not hums else round(min(hums)), 'max_hum': None if not hums else round(max(hums)),
        'fever_slots': int(fever_slots), 'urgent_alerts': sum(a['times'] for a in alerts if a['level'] == 'Urgent'),
        'comfort': f"{round(hmin)}–{round(hmax)}% humidity, {tmin:g}–{tmax:g} °C",
    }
    if not rows: verdict = 'No readings were recorded in this period.'
    elif summary['urgent_alerts'] == 0 and not fever_slots: verdict = 'Everything looked normal during this period.'
    else:
        bits = []
        if fever_slots: bits.append('the fever alert signal was triggered')
        if hums and (avg(hums) > hmax or avg(hums) < hmin): bits.append('room humidity was outside the comfortable range')
        if temps and (avg(temps) > tmax or avg(temps) < tmin): bits.append('room temperature was outside the comfortable range')
        verdict = ('Needs attention: ' + ' and '.join(bits) + '.') if bits else 'A few urgent alerts were recorded. See the alerts section below.'
    summary['verdict'] = verdict
    return {'summary': summary, 'rows': rows, 'alerts': alerts, 'care': notes}

@app.route('/api/report/data')
def report_data():
    return jsonify(build_report(request.args.get('range', 'day')))

@app.route('/api/report.csv')
def report_csv():
    import csv, io
    period = request.args.get('range', 'day'); rep = build_report(period); sm = rep['summary']
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(['NEOGUARD BABY ROOM REPORT']); w.writerow(['Period', sm['title']]); w.writerow(['From', sm['from']]); w.writerow(['To', sm['to']]); w.writerow(['Report created', sm['generated']])
    w.writerow([]); w.writerow(['SUMMARY']); w.writerow(['Overall', sm['verdict']])
    w.writerow(['Room temperature (°C)', f"average {sm['avg_temp']}, lowest {sm['min_temp']}, highest {sm['max_temp']}"])
    w.writerow(['Room humidity (%)', f"average {sm['avg_hum']}, lowest {sm['min_hum']}, highest {sm['max_hum']}"])
    w.writerow(['Comfortable range', sm['comfort']])
    w.writerow([]); w.writerow(['ALERTS (what happened)']); w.writerow(['Level', 'What happened', 'How many times', 'First seen', 'Last seen', 'Handled?'])
    for a in rep['alerts'] or []: w.writerow([a['level'], a['what'], a['times'], a['first'], a['last'], a['handled']])
    if not rep['alerts']: w.writerow(['', 'No alerts in this period'])
    w.writerow([]); w.writerow([f"READINGS (one row per {sm['slot_label']})"])
    w.writerow(['Date', 'Time', 'Room temperature (°C)', 'Humidity (%)', 'Movement?', 'Vibration?', 'Fever alert?', 'Status', 'Notes'])
    for r in rep['rows']: w.writerow([r['date'], r['time'], r['temperature'], r['humidity'], r['movement'], r['vibration'], r['fever_alert'], r['status'], r['notes']])
    w.writerow([]); w.writerow(['CARE NOTES']); w.writerow(['When', 'Type', 'Note'])
    for n in rep['care']: w.writerow([n['when'], n['category'], n['note']])
    if not rep['care']: w.writerow(['', 'No care notes in this period'])
    w.writerow([]); w.writerow(['This report comes from a sensor system. It is not a medical device and is not a diagnosis.'])
    return Response('﻿' + out.getvalue(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename=neoguard_report_{period}.csv'})

@app.route('/api/report.html')
def report_html():
    from html import escape as e
    period = request.args.get('range', 'day'); rep = build_report(period); sm = rep['summary']
    def v(x, u=''): return '—' if x is None else f'{x}{u}'
    cls = {'Needs attention': 'bad', 'Activity': 'mid', 'All good': 'ok'}
    lvl = {'Urgent': 'bad', 'Warning': 'mid', 'Notice': 'mid'}
    rows = ''.join(f"<tr class='{cls[r['status']]}'><td>{e(r['date'])}</td><td>{e(r['time'])}</td><td>{v(r['temperature'], ' °C')}</td><td>{v(r['humidity'], '%')}</td><td>{r['movement']}</td><td>{r['vibration']}</td><td>{r['fever_alert']}</td><td><b>{r['status']}</b>{'' if r['notes']=='-' else '<br><small>'+e(r['notes'])+'</small>'}</td></tr>" for r in rep['rows']) or "<tr><td colspan='8'>No readings in this period.</td></tr>"
    alerts = ''.join(f"<tr><td><span class='tag {lvl[a['level']]}'>{a['level']}</span></td><td>{e(a['what'])}</td><td>{a['times']}</td><td>{e(a['first'])}</td><td>{e(a['last'])}</td><td>{a['handled']}</td></tr>" for a in rep['alerts']) or "<tr><td colspan='6'>No alerts in this period.</td></tr>"
    care = ''.join(f"<tr><td>{e(n['when'])}</td><td>{e(n['category'])}</td><td>{e(n['note'])}</td></tr>" for n in rep['care']) or "<tr><td colspan='3'>No care notes in this period.</td></tr>"
    good = sm['verdict'].startswith('Everything')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>NeoGuard Report - {e(sm['title'])}</title><style>
body{{font:15px/1.5 -apple-system,Segoe UI,Arial,sans-serif;margin:32px auto;max-width:980px;color:#1d2a3a;padding:0 16px}}
h1{{margin:0 0 4px;color:#0f5f7f}}h2{{margin:32px 0 8px;color:#0f5f7f;font-size:19px}}.meta{{color:#5b6d80;margin:0 0 18px}}
.verdict{{padding:16px 18px;border-radius:12px;font-size:18px;font-weight:600;background:{'#e6f6ee' if good else '#fdecec'};color:{'#17703f' if good else '#a32020'}}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:14px}}.card{{border:1px solid #d8e2ec;border-radius:12px;padding:14px}}
.card small{{color:#5b6d80;display:block}}.card b{{font-size:24px;display:block;margin:2px 0}}table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{background:#eaf2f8;text-align:left}}td,th{{border:1px solid #d8e2ec;padding:8px}}tr.bad td{{background:#fff5f5}}tr.mid td{{background:#fffbea}}
.tag{{padding:2px 9px;border-radius:99px;font-size:12.5px;font-weight:700}}.tag.bad{{background:#f8d4d4;color:#a32020}}.tag.mid{{background:#fdeeb8;color:#7a5b00}}
small{{color:#5b6d80}}.print{{float:right;padding:8px 14px;border:0;border-radius:8px;background:#0f5f7f;color:#fff;cursor:pointer}}@media print{{.print{{display:none}}}}</style></head><body>
<button class="print" onclick="window.print()">Print / Save as PDF</button>
<h1>NeoGuard Baby Room Report</h1><p class="meta">{e(sm['title'])} · {e(sm['from'])} to {e(sm['to'])} · Created {e(sm['generated'])}</p>
<div class="verdict">{e(sm['verdict'])}</div>
<div class="cards"><div class="card"><small>Room temperature (average)</small><b>{v(sm['avg_temp'],' °C')}</b><small>Lowest {v(sm['min_temp'])} · Highest {v(sm['max_temp'])}</small></div>
<div class="card"><small>Room humidity (average)</small><b>{v(sm['avg_hum'],'%')}</b><small>Lowest {v(sm['min_hum'])} · Highest {v(sm['max_hum'])}</small></div>
<div class="card"><small>Comfortable range</small><b style="font-size:17px">{e(sm['comfort'])}</b><small>Limits set for your system</small></div></div>
<h2>Alerts - what happened</h2><table><tr><th>Level</th><th>What happened</th><th>Times</th><th>First seen</th><th>Last seen</th><th>Handled?</th></tr>{alerts}</table>
<h2>Readings (one row per {e(sm['slot_label'])})</h2><table><tr><th>Date</th><th>Time</th><th>Temperature</th><th>Humidity</th><th>Movement?</th><th>Vibration?</th><th>Fever alert?</th><th>Status</th></tr>{rows}</table>
<h2>Care notes</h2><table><tr><th>When</th><th>Type</th><th>Note</th></tr>{care}</table>
<p class="meta" style="margin-top:28px">This report comes from a sensor system. It is not a medical device and is not a diagnosis. If you are worried about your baby, contact a doctor.</p></body></html>"""
    return Response(html, mimetype='text/html; charset=utf-8')


# ---------------------------------------------------------
# ---------------------------------------------------------


# ---------------------------------------------------------
# Alerts / events
# ---------------------------------------------------------

@app.route("/api/alerts")
def alerts():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, alert_type, severity, message, timestamp, resolved
        FROM alerts ORDER BY id DESC LIMIT 100
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/events")
def events():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, event_type, description, timestamp
        FROM events ORDER BY id DESC LIMIT 100
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------
# LIVE ACTUATOR STATUS
# ---------------------------------------------------------

def _fan_state():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT state FROM actuator_logs WHERE actuator_name='FAN' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row["state"] if row else "OFF"


@app.route("/api/actuators")
def actuator_status():
    fever_row = latest_value(["FEVER"])
    fever = bool(fever_row and int(fever_row["value"]) == 1)

    return jsonify({
        "heater": {"state": "OFF", "duty_cycle": 0},
        "fan": {"state": _fan_state(), "duty_cycle": 0},
        "buzzer": {"state": "ON" if fever else "OFF", "duty_cycle": 0},
        "emergency": {
            "active": fever,
            "timestamp": fever_row["timestamp"] if fever_row else None,
        },
    })


# ---------------------------------------------------------
# DASHBOARD STATE (single call that powers every tab)
# ---------------------------------------------------------

TEMP_NAMES = ("DHT_TEMP", "DHT22_TEMP", "DHT22_TEMPERATURE", "AMBIENT_TEMPERATURE")
HUM_NAMES = ("DHT11", "DHT22", "DHT22_HUMIDITY", "HUMIDITY")
FEVER_NAMES = ("FEVER", "NTC_FEVER", "BABY_FEVER")
MOVE_NAMES = ("ITG_MPU", "MPU6050", "MOVEMENT")
VIB_NAMES = ("MPU_VIBRATION", "VIBRATION", "SW420")  # SW420 only for legacy database rows


def classify(d):
    """Classify the latest sensor state; never label missing data as stable."""
    if (d.get("temperature") is None and d.get("humidity") is None
            and not d.get("fever") and not d.get("movement") and not d.get("vibration")):
        return {
            "level": "unknown", "title": "Awaiting readings", "score": 0,
            "detail": "No sensor readings have arrived yet. Connect the ESP32 or run a simulation to begin monitoring.",
            "do": ["Check that the ESP32 and dashboard are on the same network.",
                   "Confirm the device is posting to /api/sensor-data."],
            "avoid": ["Don't interpret missing readings as a stable condition.",
                      "Don't use this prototype as a substitute for clinical monitoring."],
        }
    cfg = read_settings()
    hum = d.get("humidity")
    hmin, hmax = float(cfg.get("humidity_min", 30)), float(cfg.get("humidity_max", 70))
    tmin, tmax = float(cfg.get("temp_low", 15)), float(cfg.get("temp_high", 30))
    temp = d.get("temperature")
    if d.get("fever"):
        return {
            "level": "critical", "title": "Critical sensor alert", "score": 20,
            "detail": "The NTC digital alert signal is active. Check the sensor and hardware state; this signal is not a body-temperature measurement or diagnosis.",
            "do": ["Check the physical NeoGuard sensor connections.",
                   "Follow the project's emergency response procedure.",
                   "Confirm the fever indication with a clinical thermometer.",
                   "Seek qualified clinical help when required."],
            "avoid": ["Don't treat the NTC module as an exact temperature sensor.",
                      "Don't rely on this dashboard alone for clinical decisions.",
                      "Don't ignore a persistent fever indication."],
        }
    if ((hum is not None and (hum < hmin or hum > hmax)) or
            (temp is not None and (temp < tmin or temp > tmax))):
        reasons = []
        if hum is not None and (hum < hmin or hum > hmax):
            reasons.append(f"humidity is {hum:.0f}%, outside {hmin:g}–{hmax:g}%")
        if temp is not None and (temp < tmin or temp > tmax):
            reasons.append(f"room temperature is {temp:.1f}°C, outside {tmin:g}–{tmax:g}°C")
        return {
            "level": "watch", "title": "Environment check", "score": 0,
            "detail": "Configured environmental check: " + "; ".join(reasons) + ".",
            "do": ["Check room ventilation and humidity conditions.", "Continue normal monitoring."],
            "avoid": ["Don't read a humidity warning as a fever diagnosis."],
        }
    if d.get("movement") or d.get("vibration"):
        return {
            "level": "activity", "title": "Movement detected", "score": 72,
            "detail": "Movement or vibration was detected by the connected motion sensors. Check the crib and surrounding surface for the source.",
            "do": ["Check the crib and surface for the source of motion.", "Continue normal monitoring."],
            "avoid": ["Don't ignore repeated or sustained motion."],
        }
    return {
        "level": "ok", "title": "Monitoring normal", "score": 0,
        "detail": "The latest received readings do not currently trigger the configured alert rules. This is a sensor-system status, not a medical assessment.",
        "do": ["Continue normal monitoring."],
        "avoid": ["Don't ignore persistent sensor changes."],
    }


def build_state():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""SELECT sensor_name, value, unit, timestamp FROM sensor_readings
                   WHERE id IN (SELECT MAX(id) FROM sensor_readings GROUP BY sensor_name)""")
    d = {"temperature": None, "humidity": None, "fever": False,
         "movement": False, "vibration": False}
    latest_ts = None
    for r in cur.fetchall():
        n, v = r["sensor_name"], float(r["value"])
        if n in TEMP_NAMES: d["temperature"] = v
        elif n in HUM_NAMES: d["humidity"] = v
        elif n in FEVER_NAMES: d["fever"] = v == 1
        elif n in MOVE_NAMES: d["movement"] = v != 0
        elif n in VIB_NAMES: d["vibration"] = v != 0
        ts = str(r["timestamp"])
        latest_ts = ts if latest_ts is None or ts > latest_ts else latest_ts
    d["emergency"] = d["fever"]

    # actuators (latest logged state; FEVER always drives LED + buzzer)
    cur.execute("SELECT actuator_name, state FROM actuator_logs ORDER BY id DESC")
    acts = {}
    for r in cur.fetchall():
        acts.setdefault(r["actuator_name"], r["state"])
    actuators = {
        "LED": "ON" if d["fever"] else acts.get("LED", "OFF"),
        "FAN": acts.get("FAN", "OFF"),
        "BUZZER": "ON" if d["fever"] else acts.get("BUZZER", "OFF"),
        "EMERGENCY": "ACTIVE" if d["fever"] else "INACTIVE",
    }

    def series(names):
        marks = ",".join("?" for _ in names)
        cur.execute(f"""SELECT value, timestamp FROM sensor_readings
                        WHERE valid=1 AND sensor_name IN ({marks})
                        ORDER BY id DESC LIMIT 60""", names)
        return [{"v": float(r["value"]), "t": str(r["timestamp"])} for r in reversed(cur.fetchall())]

    temp_series, hum_series = series(TEMP_NAMES), series(HUM_NAMES)

    cur.execute("SELECT id, severity, message, timestamp, resolved FROM alerts ORDER BY id DESC LIMIT 60")
    alerts = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT id, event_type, description, timestamp FROM events ORDER BY id DESC LIMIT 40")
    events = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) AS n FROM sensor_readings")
    total_readings = cur.fetchone()["n"]
    conn.close()

    age = None
    if latest_ts:
        try:
            age = max(0, (datetime.now() - datetime.fromisoformat(latest_ts)).total_seconds())
        except ValueError:
            age = None

    ai = get_ai()
    return {
        "sensors": d,
        "status": classify(d),
        "actuators": actuators,
        "series": {"temperature": temp_series, "humidity": hum_series},
        "alerts": alerts,
        "events": events,
        "total_readings": total_readings,
        "last_reading": latest_ts,
        "age_seconds": age,
        "ai": {"online": bool(getattr(ai, "online", False)),
               "provider": getattr(ai, "provider", "groq"),
               "text": getattr(ai, "status_text", "")},
        "simulation": dict(_sim),
        "server_time": datetime.now().isoformat(timespec="seconds"),
    }


@app.route("/api/state")
def api_state():
    return jsonify(build_state())


@app.route("/api/classify", methods=["POST"])
def api_classify():
    """Classify a hypothetical sensor snapshot (used by the dashboard's preview scenarios)."""
    body = request.get_json(silent=True) or {}
    d = {k: body.get(k) for k in ("temperature", "humidity")}
    d.update({k: bool(body.get(k)) for k in ("fever", "movement", "vibration")})
    return jsonify(classify(d))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip()
    if not question:
        return jsonify({"ok": False, "error": "Empty question"}), 400
    snap = body.get("state")
    if not isinstance(snap, dict):
        snap = build_state()["sensors"]
    try:
        answer = get_ai().ai_chat(question, snap)
    except Exception as exc:  # never let the chat crash the dashboard
        answer = f"I couldn't complete that AI request: {exc}"
    return jsonify({"ok": True, "answer": answer})


# ---------------------------------------------------------
# SIMULATION RUNNER (the old "RUN 5 SCENARIOS" button)
# ---------------------------------------------------------

_sim = {"running": False, "last_finished": None, "error": None}


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    if _sim["running"]:
        return jsonify({"ok": False, "error": "Simulation already running"}), 409
    cycles = int((request.get_json(silent=True) or {}).get("cycles", 5))
    cycles = max(1, min(cycles, 20))

    def worker():
        try:
            from backend.services.simulation_engine import SimulationEngine
            SimulationEngine().run(cycles=cycles, delay=1)
            _sim["error"] = None
        except Exception as exc:
            _sim["error"] = str(exc)
        finally:
            _sim["running"] = False
            _sim["last_finished"] = datetime.now().isoformat(timespec="seconds")

    _sim["running"] = True
    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True, "cycles": cycles})


@app.route("/api/sessions")
def sessions():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, session_name, started_at, ended_at, status
        FROM simulation_sessions ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    print("NeoGuard backend running on http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)

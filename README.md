# NeoGuard 303 — Neonatal Care Monitoring Prototype

NeoGuard is an educational Cyber-Physical Systems (CPS) prototype that connects ESP32 sensor readings to a local web dashboard, persistent SQLite history, alerts, a digital-twin visualization, and downloadable reports.

> **Safety:** NeoGuard is not a certified medical device. Its sensor flags are demonstrations, not clinical measurements or diagnoses. Never use this prototype as a substitute for clinical monitoring or professional medical care.

## Dashboard

Run the dashboard locally at **http://127.0.0.1:5001**.

- **Overview** — monitoring status, transparent sensor/environment checks, latest sensor values, crib visualization and recent activity. No medical stability percentage is shown.
- **Copilot** — sensor-grounded guidance with a local fallback when an AI provider is not configured.
- **Trends** — temperature and humidity charts and summary statistics.
- **Alerts** — alert history, severity and acknowledgement.
- **Hardware** — actuator state, scenario previews, simulated readings, device link and wiring reference.
- **History & Reports** — filter readings by hour, day, week, month, year or all time; view charts and export CSV or a printable report.
- **Digital Twin** — crib visualization that reflects the latest received sensor state.
- **Care Log** — timestamped notes for feeding, medication, sleep, diaper changes and observations.
- **Settings** — baby profile, humidity and ambient-temperature thresholds, sound and browser-notification preferences.

The dashboard uses a responsive layout and supports light/dark themes.

## Run on macOS

1. Extract the ZIP and keep the folder structure intact.
2. Open Terminal in `NEOGUARD_ALL_IN_ONE`.
3. Install the dependency and start the server:

   ```bash
   python3 -m pip install -r requirements.txt
   python3 app.py
   ```

4. Open Safari at `http://127.0.0.1:5001`.
5. To stop the server, press **Control+C** in the Terminal window.

You can also use `OPEN_NEOGUARD.command` to start the app, and `STOP_NEOGUARD.command` to stop its background server.

## ESP32 connection

In `NeoGuard_ESP32.ino`, set `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_URL` before uploading. Use your Mac's current LAN IP in `SERVER_URL`, for example:

`http://192.168.1.5:5001/api/sensor-data`

The Mac and ESP32 must be on the same Wi-Fi network. The IP above is only an example.

### Current wiring reference

| Component | ESP32 connection | Purpose |
|---|---|---|
| DHT22 data | GPIO 4 | Ambient temperature and humidity |
| NTC digital output | GPIO 34 | Digital fever flag; verify module polarity |
| MPU6050 SDA / SCL | GPIO 21 / GPIO 22 | Motion / orientation |
| Red LED | GPIO 25 | Local status indicator |
| Buzzer | GPIO 27 | Local alert sound |

Confirm the exact sensor module and its output polarity before relying on a reading. GPIO 34 is input-only on common ESP32 boards.

## Reports and stored history

Readings, alerts, actuator changes, settings and care notes are stored in the local SQLite database. Use **History & Reports** to select a time range and download a CSV, or open the printable report and use the browser's **Print → Save as PDF** option.

Keep a backup of `database/sncs.db` if you need to preserve project history. The included database may contain earlier demonstration data.

## AI configuration

The dashboard can operate without an external AI key using its local fallback. If you configure Groq or another supported provider, set credentials in your shell environment rather than writing secrets into the source files or sharing them in screenshots.

## Project structure

- `app.py` — Flask server, API routes and sensor ingestion.
- `web/index.html` — responsive tabbed dashboard.
- `backend/database/` — SQLite connection and schema.
- `backend/services/` — sensor persistence, alerts and actuator / simulation logic.
- `backend/dsa/` — internal queue / stack / buffer helpers still used by the backend; the DSA Lab page and its demo endpoint are removed from the user-facing dashboard.
- `backend/models/` — sensor models.
- `dashboard/ai_care_engine.py` — Copilot support.
- `NeoGuard_ESP32.ino` — ESP32 firmware.
- `database/sncs.db` — local SQLite database.

## Project scope

The overview reports monitoring status and configured sensor checks; it does not assign a medical stability percentage. The NTC module's digital alert is not a measured body temperature. The digital twin is a visual representation driven by reported sensor values. It is not a validated physical simulation, and browser notifications may require permission and a user gesture to enable audio.

## Deploy as a website (Render)

This repo includes a `render.yaml` blueprint. On [Render](https://render.com): **New → Blueprint → select this repo**. The app starts with `gunicorn app:app`. Optionally add `GROQ_API_KEY` in the Render dashboard for AI Copilot. Note: on Render's free plan the SQLite file resets on redeploy/restart.

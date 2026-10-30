# =========================================================
# SNCS - DATABASE SERVICE
# =========================================================

from datetime import datetime

from backend.database.database import get_connection


# =========================================================
# SENSOR READINGS
# =========================================================

def save_sensor_reading(reading):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO sensor_readings
        (sensor_name, value, unit, timestamp, valid)
        VALUES (?, ?, ?, ?, ?)
    """, (
        reading.sensor_name,
        reading.value,
        reading.unit,
        reading.timestamp,
        1
    ))

    connection.commit()
    connection.close()


# =========================================================
# ALERTS
# =========================================================

def save_alert(alert):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO alerts
        (alert_type, severity, message, timestamp, resolved)
        VALUES (?, ?, ?, ?, ?)
    """, (
        alert.alert_type,
        alert.alert_type,
        alert.message,
        alert.timestamp,
        0
    ))

    connection.commit()
    connection.close()


# =========================================================
# EVENTS
# =========================================================

def save_event(event_type, description):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO events
        (event_type, description, timestamp)
        VALUES (?, ?, ?)
    """, (
        event_type,
        description,
        datetime.now()
    ))

    connection.commit()
    connection.close()


# =========================================================
# ACTUATOR LOGS
# =========================================================

def save_actuator_log(actuator_name, state, duty_cycle=0):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO actuator_logs
        (actuator_name, state, duty_cycle, timestamp)
        VALUES (?, ?, ?, ?)
    """, (
        actuator_name,
        state,
        duty_cycle,
        datetime.now()
    ))

    connection.commit()
    connection.close()


# =========================================================
# SYSTEM STATUS
# =========================================================

def save_system_status(component, status, message=None):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO system_status
        (component, status, message, timestamp)
        VALUES (?, ?, ?, ?)
    """, (
        component,
        status,
        message,
        datetime.now()
    ))

    connection.commit()
    connection.close()


# =========================================================
# SIMULATION SESSION
# =========================================================

def start_simulation_session(session_name):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO simulation_sessions
        (session_name, started_at, status)
        VALUES (?, ?, ?)
    """, (
        session_name,
        datetime.now(),
        "RUNNING"
    ))

    session_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return session_id


def end_simulation_session(session_id, status="COMPLETED"):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE simulation_sessions
        SET ended_at = ?, status = ?
        WHERE id = ?
    """, (
        datetime.now(),
        status,
        session_id
    ))

    connection.commit()
    connection.close()


# =========================================================
# DATABASE TEST
# =========================================================

if __name__ == "__main__":

    print("Testing database service...")

    save_event(
        "SYSTEM_TEST",
        "Database service test successful"
    )

    save_system_status(
        "DATABASE",
        "ONLINE",
        "Database service operational"
    )

    print("Database service test completed successfully.")
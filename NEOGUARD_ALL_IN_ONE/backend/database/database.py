import sqlite3
from pathlib import Path


# ---------------------------------------------------------
# DATABASE LOCATION
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_FOLDER = PROJECT_ROOT / "database"
DATABASE_FOLDER.mkdir(exist_ok=True)

DATABASE_PATH = DATABASE_FOLDER / "sncs.db"


# ---------------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------------

def get_connection():
    """
    Creates and returns a connection to the SQLite database.
    """
    connection = sqlite3.connect(DATABASE_PATH)

    # Allows rows to be accessed using column names
    connection.row_factory = sqlite3.Row

    return connection


# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    # -----------------------------------------------------
    # SENSOR READINGS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            valid INTEGER DEFAULT 1
        )
    """)

    # -----------------------------------------------------
    # ALERTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # EVENTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # ACTUATOR LOGS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actuator_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actuator_name TEXT NOT NULL,
            state TEXT NOT NULL,
            duty_cycle REAL DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # SYSTEM STATUS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # SIMULATION SESSIONS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simulation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ended_at DATETIME,
            status TEXT DEFAULT 'RUNNING'
        )
    """)

    # -----------------------------------------------------
    # INDEXES
    # -----------------------------------------------------

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sensor_timestamp
        ON sensor_readings(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sensor_name
        ON sensor_readings(sensor_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alert_severity
        ON alerts(severity)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_timestamp
        ON events(timestamp)
    """)

    cursor.execute("""CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS care_log (id INTEGER PRIMARY KEY AUTOINCREMENT, note TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Care', timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")

    connection.commit()
    connection.close()

    print("Database initialized successfully.")
    print(f"Database location: {DATABASE_PATH}")


# ---------------------------------------------------------
# SENSOR READING FUNCTIONS
# ---------------------------------------------------------

def insert_sensor_reading(sensor_name, value, unit, valid=True):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO sensor_readings
        (sensor_name, value, unit, valid)
        VALUES (?, ?, ?, ?)
    """, (
        sensor_name,
        value,
        unit,
        int(valid)
    ))

    connection.commit()
    connection.close()


def get_sensor_readings():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM sensor_readings
        ORDER BY timestamp DESC
    """)

    readings = cursor.fetchall()

    connection.close()

    return readings


# ---------------------------------------------------------
# RESET DATABASE DATA
# ---------------------------------------------------------

def reset_database():

    """
    Clears all stored SNCS data while keeping
    the database tables and structure intact.

    This is useful when starting a fresh
    simulation/demo after changing the sensor architecture.
    """

    connection = get_connection()
    cursor = connection.cursor()

    tables = [
        "sensor_readings",
        "alerts",
        "events",
        "actuator_logs",
        "system_status",
        "simulation_sessions"
    ]

    for table in tables:
        cursor.execute(f"DELETE FROM {table}")

    connection.commit()
    connection.close()

    print("Database data reset successfully.")
    print("Old sensor records and simulation data have been removed.")


# ---------------------------------------------------------
# TEST
# ---------------------------------------------------------

if __name__ == "__main__":

    initialize_database()
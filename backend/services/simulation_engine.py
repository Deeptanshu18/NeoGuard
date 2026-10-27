# =========================================================
# SNCS - CENTRAL SIMULATION ENGINE
# =========================================================

from datetime import datetime
import time

from backend.models.sensor import SensorReading
from backend.dsa.queue import SensorQueue
from backend.dsa.circular_buffer import CircularBuffer
from backend.services.alert_engine import AlertEngine
from backend.services.control_engine import ControlEngine

from backend.services.database_service import (
    save_sensor_reading,
    save_alert,
    save_event,
    start_simulation_session,
    end_simulation_session
)


# =========================================================
# SIMULATION ENGINE
# =========================================================

class SimulationEngine:

    def __init__(self):

        # -------------------------------------------------
        # DSA STRUCTURES
        # -------------------------------------------------

        self.sensor_queue = SensorQueue()

        self.temperature_buffer = CircularBuffer(
            capacity=5
        )

        # -------------------------------------------------
        # ALERT ENGINE
        # -------------------------------------------------

        self.alert_engine = AlertEngine()
        self.control_engine = ControlEngine()

        # -------------------------------------------------
        # Simulation state
        # -------------------------------------------------

        self.running = False

        self.session_id = None

        self.processed_readings = 0

        self.generated_alerts = 0

    # =====================================================
    # GENERATE SENSOR READINGS
    # =====================================================

    def generate_readings(self, cycle):

        # -------------------------------------------------
        # Simulation scenarios
        #
        # ITG/MPU:
        # 0 = No movement
        # 1 = Movement detected
        #
        # SW420:
        # 0 = No vibration
        # 1 = Vibration detected
        # -------------------------------------------------

        scenarios = [

            # Cycle 1 - Normal
            {
                "NTC": 36.8,
                "DHT11": 55.0,
                "ITG/MPU": 0,
                "SW420": 0
            },

            # Cycle 2 - High temperature + movement
            {
                "NTC": 38.2,
                "DHT11": 65.0,
                "ITG/MPU": 1,
                "SW420": 0
            },

            # Cycle 3 - Critical temperature + movement + vibration
            {
                "NTC": 39.5,
                "DHT11": 75.0,
                "ITG/MPU": 1,
                "SW420": 1
            },

            # Cycle 4 - Low temperature + vibration
            {
                "NTC": 35.5,
                "DHT11": 50.0,
                "ITG/MPU": 0,
                "SW420": 1
            },

            # Cycle 5 - Normal recovery
            {
                "NTC": 37.0,
                "DHT11": 55.0,
                "ITG/MPU": 0,
                "SW420": 0
            }
        ]

        # Select scenario
        scenario = scenarios[
            (cycle - 1) % len(scenarios)
        ]

        readings = [

            # -------------------------------------------------
            # NTC
            # -------------------------------------------------

            SensorReading(
                sensor_name="NTC",
                value=scenario["NTC"],
                unit="°C",
                timestamp=datetime.now()
            ),

            # -------------------------------------------------
            # DHT11
            # -------------------------------------------------

            SensorReading(
                sensor_name="DHT11",
                value=scenario["DHT11"],
                unit="%",
                timestamp=datetime.now()
            ),

            # -------------------------------------------------
            # ITG/MPU
            # -------------------------------------------------

            SensorReading(
                sensor_name="ITG/MPU",
                value=scenario["ITG/MPU"],
                unit="STATE",
                timestamp=datetime.now()
            ),

            # -------------------------------------------------
            # SW420
            # -------------------------------------------------

            SensorReading(
                sensor_name="SW420",
                value=scenario["SW420"],
                unit="STATE",
                timestamp=datetime.now()
            )
        ]

        return readings

    # =====================================================
    # ADD READINGS TO QUEUE
    # =====================================================

    def collect_sensor_data(self, cycle):

        readings = self.generate_readings(cycle)

        print("\nCollecting sensor readings...")

        for reading in readings:

            self.sensor_queue.enqueue(reading)

            print(
                f"Added: {reading.sensor_name} = "
                f"{reading.value} {reading.unit}"
            )

    # =====================================================
    # PROCESS QUEUE
    # =====================================================

    def process_sensor_data(self):

        print("\nProcessing sensor queue...")

        while not self.sensor_queue.is_empty():

            reading = self.sensor_queue.dequeue()

            if reading is None:
                break

            # ---------------------------------------------
            # Save sensor reading
            # ---------------------------------------------

            save_sensor_reading(reading)

            print(
                f"Processing: {reading.sensor_name} = "
                f"{reading.value} {reading.unit}"
            )

            # ---------------------------------------------
            # Store NTC reading in circular buffer
            # ---------------------------------------------

            if reading.sensor_name == "NTC":

                self.temperature_buffer.add(reading)

            # ---------------------------------------------
            # Send reading to Alert Engine
            # ---------------------------------------------

            alert = self.alert_engine.evaluate(reading)

            save_alert(alert)

            self.generated_alerts += 1

            print(
                f"Alert Status: {alert.alert_type} "
                f"| Priority: {alert.priority}"
            )

            # ---------------------------------------------
            # Send NTC temperature to Control Engine
            # ---------------------------------------------

            if reading.sensor_name == "NTC":

                self.control_engine.control_temperature(
                    reading.value
                )

            # ---------------------------------------------
            # Send movement to Control Engine
            # ---------------------------------------------

            elif reading.sensor_name == "ITG/MPU":

                self.control_engine.record_movement(
                    reading.value == 1
                )

            # ---------------------------------------------
            # Send vibration to Control Engine
            # ---------------------------------------------

            elif reading.sensor_name == "SW420":

                self.control_engine.record_vibration(
                    reading.value == 1
                )

            self.processed_readings += 1

    # =====================================================
    # DISPLAY RECENT TEMPERATURE DATA
    # =====================================================

    def display_recent_temperature(self):

        print("\nRecent Temperature Buffer:")

        self.temperature_buffer.display()

    # =====================================================
    # DISPLAY ALERT QUEUE
    # =====================================================

    def display_alert_queue(self):

        print("\nCurrent Alert Queue:")

        self.alert_engine.display_alerts()

    # =====================================================
    # PROCESS ALERTS
    # =====================================================

    def process_alerts(self):

        print("\nProcessing alerts by priority...")

        while not self.alert_engine.alert_queue.is_empty():

            alert = self.alert_engine.process_next_alert()

            if alert is None:
                break

            print(
                f"Processing Alert: "
                f"[Priority {alert.priority}] "
                f"{alert.alert_type} | "
                f"{alert.sensor_name} | "
                f"{alert.message}"
            )

    # =====================================================
    # RUN ONE SIMULATION CYCLE
    # =====================================================

    def run_cycle(self, cycle):

        print("\n" + "=" * 60)

        print(
            f"SNCS SIMULATION CYCLE {cycle}"
        )

        print("=" * 60)

        # ---------------------------------------------
        # Step 1 - Collect
        # ---------------------------------------------

        self.collect_sensor_data(cycle)

        # ---------------------------------------------
        # Step 2 - Process
        # ---------------------------------------------

        self.process_sensor_data()

        # ---------------------------------------------
        # Step 3 - Display recent temperature data
        # ---------------------------------------------

        self.display_recent_temperature()

        # ---------------------------------------------
        # Step 4 - Display alerts
        # ---------------------------------------------

        self.display_alert_queue()

        # ---------------------------------------------
        # Step 5 - Display actuator status
        # ---------------------------------------------

        self.control_engine.display_status()

    # =====================================================
    # RUN SIMULATION
    # =====================================================

    def run(self, cycles=5, delay=2):

        self.running = True

        # -------------------------------------------------
        # Start simulation session
        # -------------------------------------------------

        self.session_id = start_simulation_session(
            "SNCS Simulation"
        )

        save_event(
            "SIMULATION_STARTED",
            f"Simulation session {self.session_id} started"
        )

        print("\n")
        print("=" * 60)
        print("SMART NEONATAL CARE SYSTEM")
        print("CENTRAL SIMULATION ENGINE")
        print("=" * 60)

        # -------------------------------------------------
        # Run simulation cycles
        # -------------------------------------------------

        for cycle in range(1, cycles + 1):

            self.run_cycle(cycle)

            if cycle < cycles:

                print(
                    f"\nWaiting {delay} seconds "
                    "for next cycle..."
                )

                time.sleep(delay)

        # -------------------------------------------------
        # Process all generated alerts
        # -------------------------------------------------

        self.process_alerts()

        # -------------------------------------------------
        # End simulation session
        # -------------------------------------------------

        self.running = False

        end_simulation_session(
            self.session_id,
            "COMPLETED"
        )

        save_event(
            "SIMULATION_COMPLETED",
            f"Simulation session {self.session_id} completed"
        )

        print("\n")
        print("=" * 60)
        print("SIMULATION COMPLETED")
        print("=" * 60)

        print(
            "\nTotal readings processed:",
            self.processed_readings
        )

        print(
            "Total alerts generated:",
            self.generated_alerts
        )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    engine = SimulationEngine()

    engine.run(
        cycles=5,
        delay=1
    )
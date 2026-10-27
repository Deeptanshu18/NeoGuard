# =========================================================
# NEOGUARD - LIVE ALERT ENGINE
# Current hardware semantics:
# DHT_TEMP = ambient temperature
# DHT11/DHT22 = humidity
# FEVER = digital NTC fever signal (1=YES, 0=NO)
# ITG_MPU = movement
# SW420 = MPU-derived vibration compatibility field
# NTC numeric temperature is NOT used.
# =========================================================

from datetime import datetime
from backend.dsa.priority_queue import Alert, AlertPriorityQueue


class AlertEngine:
    def __init__(self):
        self.alert_queue = AlertPriorityQueue()

    def _create_alert(self, alert_type, message, priority, sensor_name):
        alert = Alert(
            alert_type=alert_type,
            message=message,
            priority=priority,
            timestamp=datetime.now(),
            sensor_name=sensor_name,
        )
        self.alert_queue.enqueue(alert)
        return alert

    def evaluate(self, reading):
        name = str(reading.sensor_name).upper()
        value = float(reading.value)

        # Digital fever signal from the NTC module.
        if name in {"FEVER", "NTC_FEVER", "BABY_FEVER"}:
            if value >= 1:
                return self._create_alert(
                    "CRITICAL",
                    "FEVER DETECTED — EMERGENCY MODE",
                    1,
                    "FEVER",
                )
            return self._create_alert(
                "INFO", "Fever signal clear", 5, "FEVER"
            )

        # NTC is retained only as a compatibility field in the ESP32 packet.
        if name == "NTC":
            return self._create_alert(
                "INFO",
                "NTC numeric value ignored; fever is reported by FEVER signal",
                5,
                "NTC",
            )

        # DHT22 ambient temperature.
        if name in {"DHT_TEMP", "DHT22_TEMP", "DHT22_TEMPERATURE", "AMBIENT_TEMPERATURE"}:
            if value >= 35 or value <= 10:
                return self._create_alert(
                    "CRITICAL",
                    f"Critical DHT22 ambient temperature: {value:.1f} °C",
                    1,
                    "DHT_TEMP",
                )
            if value > 30 or value < 15:
                return self._create_alert(
                    "HIGH",
                    f"DHT22 ambient temperature outside preferred range: {value:.1f} °C",
                    2,
                    "DHT_TEMP",
                )
            return self._create_alert(
                "INFO",
                f"DHT22 ambient temperature normal: {value:.1f} °C",
                5,
                "DHT_TEMP",
            )

        # DHT22 humidity. DHT11 is retained as the project's historical name.
        if name in {"DHT11", "DHT22", "DHT22_HUMIDITY", "HUMIDITY"}:
            if value >= 85 or value <= 20:
                return self._create_alert(
                    "CRITICAL",
                    f"Critical DHT22 humidity: {value:.1f} %",
                    1,
                    "DHT11",
                )
            if value > 70 or value < 30:
                return self._create_alert(
                    "WARNING",
                    f"DHT22 humidity outside preferred range: {value:.1f} %",
                    3,
                    "DHT11",
                )
            return self._create_alert(
                "INFO",
                f"DHT22 humidity normal: {value:.1f} %",
                5,
                "DHT11",
            )

        if name in {"ITG_MPU", "ITG/MPU", "MPU6050", "MOVEMENT"}:
            if value == 1:
                return self._create_alert(
                    "WARNING", "MPU6050 movement detected", 3, "ITG_MPU"
                )
            return self._create_alert(
                "INFO", "No movement detected", 5, "ITG_MPU"
            )

        if name in {"SW420", "MPU_VIBRATION", "VIBRATION"}:
            if value == 1:
                return self._create_alert(
                    "WARNING", "MPU6050 vibration detected", 3, "SW420"
                )
            return self._create_alert(
                "INFO", "No vibration detected", 5, "SW420"
            )

        return self._create_alert(
            "WARNING", f"Unknown sensor: {reading.sensor_name}", 3, reading.sensor_name
        )

    def process_next_alert(self):
        return self.alert_queue.dequeue()

    def display_alerts(self):
        self.alert_queue.display()

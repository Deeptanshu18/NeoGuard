from dataclasses import dataclass
from datetime import datetime

from backend.database.database import insert_sensor_reading

@dataclass
class SensorReading:
    sensor_name: str
    value: float
    unit: str
    timestamp: datetime
    valid: bool = True

    def display(self):
        status = "VALID" if self.valid else "INVALID"

        print(
            f"[{self.timestamp.strftime('%H:%M:%S')}] "
            f"{self.sensor_name}: "
            f"{self.value:.2f} {self.unit} "
            f"({status})"
        )


if __name__ == "__main__":

    temperature = SensorReading(
        sensor_name="NTC",
        value=34.2,
        unit="°C",
        timestamp=datetime.now()
    )

    humidity = SensorReading(
        sensor_name="DHT11",
        value=56.5,
        unit="%",
        timestamp=datetime.now()
    )

    weight = SensorReading(
        sensor_name="HX711",
        value=3.21,
        unit="kg",
        timestamp=datetime.now()
    )

    temperature.display()
    humidity.display()
    weight.display()

    insert_sensor_reading(
    temperature.sensor_name,
    temperature.value,
    temperature.unit,
    temperature.valid
    )

    insert_sensor_reading(
    humidity.sensor_name,
    humidity.value,
    humidity.unit,
    humidity.valid
    )

    insert_sensor_reading(
    weight.sensor_name,
    weight.value,
    weight.unit,
    weight.valid
    )

    print("\nSensor readings successfully stored in SQL database.")
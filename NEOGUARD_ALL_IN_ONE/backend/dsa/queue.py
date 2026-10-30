class SensorQueue:

    def __init__(self):
        self.items = []

    # Add a sensor reading to the rear
    def enqueue(self, reading):
        self.items.append(reading)

    # Remove and return the reading from the front
    def dequeue(self):
        if self.is_empty():
            return None

        return self.items.pop(0)

    # Look at the front reading without removing it
    def peek(self):
        if self.is_empty():
            return None

        return self.items[0]

    # Check whether the queue is empty
    def is_empty(self):
        return len(self.items) == 0

    # Return number of readings in queue
    def size(self):
        return len(self.items)

    # Display all readings currently in queue
    def display(self):
        if self.is_empty():
            print("Queue is empty.")
            return

        print("\nSensor Queue:")

        for i, reading in enumerate(self.items):
            print(
                f"{i + 1}. "
                f"{reading.sensor_name}: "
                f"{reading.value} {reading.unit}"
            )


# ---------------------------------------------------------
# TEST
# ---------------------------------------------------------

if __name__ == "__main__":

    from backend.models.sensor import SensorReading
    from datetime import datetime

    queue = SensorQueue()

    reading1 = SensorReading(
        sensor_name="NTC",
        value=34.2,
        unit="°C",
        timestamp=datetime.now()
    )

    reading2 = SensorReading(
        sensor_name="DHT11",
        value=56.5,
        unit="%",
        timestamp=datetime.now()
    )

    reading3 = SensorReading(
        sensor_name="SW420",
        value=1,
        unit="VIBRATION",
        timestamp=datetime.now()
    )

    print("Adding readings to queue...")

    queue.enqueue(reading1)
    queue.enqueue(reading2)
    queue.enqueue(reading3)

    queue.display()

    print("\nQueue size:", queue.size())

    print(
        "\nFront reading:",
        queue.peek().sensor_name
    )

    print(
        "Processing:",
        queue.dequeue().sensor_name
    )

    print(
        "Processing:",
        queue.dequeue().sensor_name
    )

    print("\nQueue after processing:")
    queue.display()

    print("\nRemaining queue size:", queue.size())
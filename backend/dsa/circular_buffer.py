class CircularBuffer:

    def __init__(self, capacity):
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.front = 0
        self.size = 0

    # -----------------------------------------------------
    # ADD A NEW READING
    # -----------------------------------------------------

    def add(self, reading):

        if self.capacity == 0:
            return

        position = (self.front + self.size) % self.capacity

        self.buffer[position] = reading

        # Buffer is not full
        if self.size < self.capacity:
            self.size += 1

        # Buffer is full
        else:
            self.front = (self.front + 1) % self.capacity

    # -----------------------------------------------------
    # GET ALL READINGS
    # -----------------------------------------------------

    def get_all(self):

        readings = []

        for i in range(self.size):
            position = (self.front + i) % self.capacity
            readings.append(self.buffer[position])

        return readings

    # -----------------------------------------------------
    # GET LATEST READING
    # -----------------------------------------------------

    def latest(self):

        if self.size == 0:
            return None

        position = (self.front + self.size - 1) % self.capacity

        return self.buffer[position]

    # -----------------------------------------------------
    # CHECK IF EMPTY
    # -----------------------------------------------------

    def is_empty(self):
        return self.size == 0

    # -----------------------------------------------------
    # CHECK IF FULL
    # -----------------------------------------------------

    def is_full(self):
        return self.size == self.capacity

    # -----------------------------------------------------
    # CURRENT SIZE
    # -----------------------------------------------------

    def get_size(self):
        return self.size

    # -----------------------------------------------------
    # DISPLAY BUFFER
    # -----------------------------------------------------

    def display(self):

        if self.is_empty():
            print("Circular buffer is empty.")
            return

        print("\nCircular Buffer:")

        readings = self.get_all()

        for i, reading in enumerate(readings):

            print(
                f"{i + 1}. "
                f"{reading.sensor_name}: "
                f"{reading.value} {reading.unit}"
            )


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    from backend.models.sensor import SensorReading
    from datetime import datetime

    # Create a buffer that can store 5 readings
    buffer = CircularBuffer(5)

    print("Adding first five temperature readings...")

    temperatures = [34.0, 34.1, 34.2, 34.3, 34.4]

    for temperature in temperatures:

        reading = SensorReading(
            sensor_name="NTC",
            value=temperature,
            unit="°C",
            timestamp=datetime.now()
        )

        buffer.add(reading)

    buffer.display()

    print("\nBuffer size:", buffer.get_size())
    print("Is buffer full?", buffer.is_full())

    # -----------------------------------------------------
    # Add another reading
    # -----------------------------------------------------

    print("\nAdding new reading: 34.5 °C")

    new_reading = SensorReading(
        sensor_name="NTC",
        value=34.5,
        unit="°C",
        timestamp=datetime.now()
    )

    buffer.add(new_reading)

    buffer.display()

    print("\nBuffer size:", buffer.get_size())

    print(
        "\nLatest reading:",
        buffer.latest().value,
        buffer.latest().unit
    )
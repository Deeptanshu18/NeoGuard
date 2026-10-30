# =========================================================
# HASH TABLE
# =========================================================

class SensorHashTable:

    def __init__(self, capacity=10):
        self.capacity = capacity
        self.table = [[] for _ in range(capacity)]

    # -----------------------------------------------------
    # HASH FUNCTION
    # -----------------------------------------------------

    def _hash(self, key):

        hash_value = 0

        for character in key:
            hash_value += ord(character)

        return hash_value % self.capacity

    # -----------------------------------------------------
    # INSERT / UPDATE
    # -----------------------------------------------------

    def insert(self, key, value):

        index = self._hash(key)

        bucket = self.table[index]

        # Update existing key
        for i, (existing_key, existing_value) in enumerate(bucket):

            if existing_key == key:
                bucket[i] = (key, value)
                return

        # Add new key-value pair
        bucket.append((key, value))

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    def search(self, key):

        index = self._hash(key)

        bucket = self.table[index]

        for existing_key, value in bucket:

            if existing_key == key:
                return value

        return None

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    def delete(self, key):

        index = self._hash(key)

        bucket = self.table[index]

        for i, (existing_key, value) in enumerate(bucket):

            if existing_key == key:
                bucket.pop(i)
                return True

        return False

    # -----------------------------------------------------
    # CHECK WHETHER KEY EXISTS
    # -----------------------------------------------------

    def contains(self, key):

        return self.search(key) is not None

    # -----------------------------------------------------
    # DISPLAY
    # -----------------------------------------------------

    def display(self):

        print("\nSensor Hash Table:")

        for index, bucket in enumerate(self.table):

            print(f"Index {index}: ", end="")

            if not bucket:
                print("Empty")
                continue

            for key, value in bucket:

                print(
                    f"[{key} → {value}]",
                    end=" "
                )

            print()


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    sensor_table = SensorHashTable(capacity=5)

    # -----------------------------------------------------
    # Insert sensor information
    # -----------------------------------------------------

    print("Adding sensor configurations...")

    sensor_table.insert(
        "NTC",
        {
            "type": "Temperature",
            "unit": "°C",
            "normal_min": 36.5,
            "normal_max": 37.5
        }
    )

    sensor_table.insert(
        "DHT11",
        {
            "type": "Humidity",
            "unit": "%",
            "normal_min": 40,
            "normal_max": 60
        }
    )

    sensor_table.insert(
        "ITG/MPU",
        {
            "type": "Movement",
            "unit": "STATE",
            "normal_min": 0,
            "normal_max": 0
        }
    )

    sensor_table.insert(
        "SW420",
        {
            "type": "Vibration",
            "unit": "STATE",
            "normal_min": 0,
            "normal_max": 0
        }
    )

    sensor_table.display()

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    print("\nSearching for NTC...")

    ntc = sensor_table.search("NTC")

    if ntc:
        print("NTC configuration found:")
        print(ntc)

    # -----------------------------------------------------
    # Contains
    # -----------------------------------------------------

    print(
        "\nDoes DHT11 exist?",
        sensor_table.contains("DHT11")
    )

    print(
        "Does ITG/MPU exist?",
        sensor_table.contains("ITG/MPU")
    )

    print(
        "Does ESP32 exist?",
        sensor_table.contains("ESP32")
    )

    # -----------------------------------------------------
    # Update
    # -----------------------------------------------------

    print("\nUpdating NTC configuration...")

    sensor_table.insert(
        "NTC",
        {
            "type": "Temperature",
            "unit": "°C",
            "normal_min": 36.0,
            "normal_max": 37.5
        }
    )

    print(
        "Updated NTC:",
        sensor_table.search("NTC")
    )

    # -----------------------------------------------------
    # Delete
    # -----------------------------------------------------

    print("\nDeleting SW420...")

    deleted = sensor_table.delete("SW420")

    print("Deleted:", deleted)

    print(
        "Does SW420 exist?",
        sensor_table.contains("SW420")
    )

    sensor_table.display()
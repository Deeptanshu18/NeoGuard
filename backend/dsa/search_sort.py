# =========================================================
# SEARCHING AND SORTING ALGORITHMS
# =========================================================


# =========================================================
# BUBBLE SORT
# =========================================================

def bubble_sort(data, key=lambda x: x):

    arr = data.copy()

    n = len(arr)

    for i in range(n):

        swapped = False

        for j in range(0, n - i - 1):

            if key(arr[j]) > key(arr[j + 1]):

                arr[j], arr[j + 1] = arr[j + 1], arr[j]

                swapped = True

        if not swapped:
            break

    return arr


# =========================================================
# SELECTION SORT
# =========================================================

def selection_sort(data, key=lambda x: x):

    arr = data.copy()

    n = len(arr)

    for i in range(n):

        min_index = i

        for j in range(i + 1, n):

            if key(arr[j]) < key(arr[min_index]):

                min_index = j

        arr[i], arr[min_index] = arr[min_index], arr[i]

    return arr


# =========================================================
# INSERTION SORT
# =========================================================

def insertion_sort(data, key=lambda x: x):

    arr = data.copy()

    for i in range(1, len(arr)):

        current = arr[i]

        j = i - 1

        while j >= 0 and key(arr[j]) > key(current):

            arr[j + 1] = arr[j]

            j -= 1

        arr[j + 1] = current

    return arr


# =========================================================
# MERGE SORT
# =========================================================

def merge_sort(data, key=lambda x: x):

    if len(data) <= 1:
        return data.copy()

    middle = len(data) // 2

    left = merge_sort(data[:middle], key)

    right = merge_sort(data[middle:], key)

    return merge(left, right, key)


def merge(left, right, key):

    result = []

    i = 0
    j = 0

    while i < len(left) and j < len(right):

        if key(left[i]) <= key(right[j]):

            result.append(left[i])

            i += 1

        else:

            result.append(right[j])

            j += 1

    result.extend(left[i:])
    result.extend(right[j:])

    return result


# =========================================================
# LINEAR SEARCH
# =========================================================

def linear_search(data, target, key=lambda x: x):

    for i, item in enumerate(data):

        if key(item) == target:

            return i

    return -1


# =========================================================
# BINARY SEARCH
# =========================================================

def binary_search(data, target, key=lambda x: x):

    left = 0
    right = len(data) - 1

    while left <= right:

        middle = (left + right) // 2

        middle_value = key(data[middle])

        if middle_value == target:

            return middle

        elif middle_value < target:

            left = middle + 1

        else:

            right = middle - 1

    return -1


# =========================================================
# DISPLAY SENSOR READINGS
# =========================================================

def display_readings(readings, title):

    print(f"\n{title}")

    for reading in readings:

        print(
            f"{reading.sensor_name}: "
            f"{reading.value} "
            f"{reading.unit}"
        )


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    from backend.models.sensor import SensorReading
    from datetime import datetime

    # -----------------------------------------------------
    # Create sample temperature readings
    # -----------------------------------------------------

    readings = [

        SensorReading(
            sensor_name="NTC",
            value=37.4,
            unit="°C",
            timestamp=datetime.now()
        ),

        SensorReading(
            sensor_name="NTC",
            value=36.8,
            unit="°C",
            timestamp=datetime.now()
        ),

        SensorReading(
            sensor_name="NTC",
            value=38.1,
            unit="°C",
            timestamp=datetime.now()
        ),

        SensorReading(
            sensor_name="NTC",
            value=36.2,
            unit="°C",
            timestamp=datetime.now()
        ),

        SensorReading(
            sensor_name="NTC",
            value=37.0,
            unit="°C",
            timestamp=datetime.now()
        )
    ]

    print("Original readings:")

    display_readings(
        readings,
        "Sensor Data"
    )

    # -----------------------------------------------------
    # Bubble Sort
    # -----------------------------------------------------

    bubble_result = bubble_sort(
        readings,
        key=lambda x: x.value
    )

    display_readings(
        bubble_result,
        "Bubble Sort - Temperature"
    )

    # -----------------------------------------------------
    # Selection Sort
    # -----------------------------------------------------

    selection_result = selection_sort(
        readings,
        key=lambda x: x.value
    )

    display_readings(
        selection_result,
        "Selection Sort - Temperature"
    )

    # -----------------------------------------------------
    # Insertion Sort
    # -----------------------------------------------------

    insertion_result = insertion_sort(
        readings,
        key=lambda x: x.value
    )

    display_readings(
        insertion_result,
        "Insertion Sort - Temperature"
    )

    # -----------------------------------------------------
    # Merge Sort
    # -----------------------------------------------------

    merge_result = merge_sort(
        readings,
        key=lambda x: x.value
    )

    display_readings(
        merge_result,
        "Merge Sort - Temperature"
    )

    # -----------------------------------------------------
    # Linear Search
    # -----------------------------------------------------

    target_temperature = 38.1

    linear_index = linear_search(
        readings,
        target_temperature,
        key=lambda x: x.value
    )

    print(
        f"\nLinear Search:"
        f" {target_temperature}°C found at index "
        f"{linear_index}"
    )

    # -----------------------------------------------------
    # Binary Search
    # -----------------------------------------------------

    target_temperature = 37.0

    binary_index = binary_search(
        merge_result,
        target_temperature,
        key=lambda x: x.value
    )

    print(
        f"\nBinary Search:"
        f" {target_temperature}°C found at index "
        f"{binary_index}"
    )
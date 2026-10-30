from dataclasses import dataclass
from datetime import datetime


# =========================================================
# ALERT DATA MODEL
# =========================================================

@dataclass
class Alert:
    alert_type: str
    message: str
    priority: int
    timestamp: datetime
    sensor_name: str

    def display(self):
        print(
            f"[Priority {self.priority}] "
            f"{self.alert_type} | "
            f"{self.sensor_name} | "
            f"{self.message}"
        )


# =========================================================
# PRIORITY QUEUE
# =========================================================

class AlertPriorityQueue:

    def __init__(self):
        self.items = []

    # -----------------------------------------------------
    # INSERT ALERT
    # -----------------------------------------------------

    def enqueue(self, alert):

        self.items.append(alert)

        # Sort according to priority
        # Smaller number = higher priority
        self.items.sort(key=lambda x: x.priority)

    # -----------------------------------------------------
    # REMOVE HIGHEST PRIORITY ALERT
    # -----------------------------------------------------

    def dequeue(self):

        if self.is_empty():
            return None

        return self.items.pop(0)

    # -----------------------------------------------------
    # VIEW HIGHEST PRIORITY ALERT
    # -----------------------------------------------------

    def peek(self):

        if self.is_empty():
            return None

        return self.items[0]

    # -----------------------------------------------------
    # CHECK EMPTY
    # -----------------------------------------------------

    def is_empty(self):
        return len(self.items) == 0

    # -----------------------------------------------------
    # SIZE
    # -----------------------------------------------------

    def size(self):
        return len(self.items)

    # -----------------------------------------------------
    # DISPLAY QUEUE
    # -----------------------------------------------------

    def display(self):

        if self.is_empty():
            print("Priority queue is empty.")
            return

        print("\nAlert Priority Queue:")

        for i, alert in enumerate(self.items):

            print(
                f"{i + 1}. ",
                end=""
            )

            alert.display()


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    queue = AlertPriorityQueue()

    # -----------------------------------------------------
    # Create different alerts
    # -----------------------------------------------------

    normal_alert = Alert(
        alert_type="INFO",
        message="Temperature within normal range",
        priority=5,
        timestamp=datetime.now(),
        sensor_name="NTC"
    )

    weight_alert = Alert(
        alert_type="WARNING",
        message="Weight variation detected",
        priority=3,
        timestamp=datetime.now(),
        sensor_name="HX711"
    )

    temperature_alert = Alert(
        alert_type="HIGH",
        message="Temperature above safe limit",
        priority=2,
        timestamp=datetime.now(),
        sensor_name="NTC"
    )

    critical_alert = Alert(
        alert_type="CRITICAL",
        message="Critical temperature detected",
        priority=1,
        timestamp=datetime.now(),
        sensor_name="NTC"
    )

    # -----------------------------------------------------
    # Add alerts
    # -----------------------------------------------------

    print("Adding alerts...")

    queue.enqueue(normal_alert)
    queue.enqueue(weight_alert)
    queue.enqueue(temperature_alert)
    queue.enqueue(critical_alert)

    # -----------------------------------------------------
    # Display queue
    # -----------------------------------------------------

    queue.display()

    print("\nQueue size:", queue.size())

    # -----------------------------------------------------
    # Process alerts
    # -----------------------------------------------------

    print("\nProcessing alerts:")

    while not queue.is_empty():

        alert = queue.dequeue()

        print("Processing:", end=" ")
        alert.display()

    print("\nAll alerts processed.")
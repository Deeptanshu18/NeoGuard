from dataclasses import dataclass
from datetime import datetime


# =========================================================
# SYSTEM ACTION DATA MODEL
# =========================================================

@dataclass
class SystemAction:
    action: str
    component: str
    timestamp: datetime

    def display(self):
        print(
            f"{self.timestamp.strftime('%H:%M:%S')} | "
            f"{self.component} | "
            f"{self.action}"
        )


# =========================================================
# STACK
# =========================================================

class ActionStack:

    def __init__(self):
        self.items = []

    # -----------------------------------------------------
    # PUSH
    # -----------------------------------------------------

    def push(self, action):
        self.items.append(action)

    # -----------------------------------------------------
    # POP
    # -----------------------------------------------------

    def pop(self):

        if self.is_empty():
            return None

        return self.items.pop()

    # -----------------------------------------------------
    # PEEK
    # -----------------------------------------------------

    def peek(self):

        if self.is_empty():
            return None

        return self.items[-1]

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
    # DISPLAY
    # -----------------------------------------------------

    def display(self):

        if self.is_empty():
            print("Action stack is empty.")
            return

        print("\nSystem Action Stack:")

        # Display newest action first
        for i, action in enumerate(reversed(self.items)):

            print(
                f"{i + 1}. ",
                end=""
            )

            action.display()


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    stack = ActionStack()

    # -----------------------------------------------------
    # Create system actions
    # -----------------------------------------------------

    actions = [

        SystemAction(
            action="Fan turned OFF",
            component="FAN",
            timestamp=datetime.now()
        ),

        SystemAction(
            action="Fan turned ON",
            component="FAN",
            timestamp=datetime.now()
        ),

        SystemAction(
            action="Heater turned ON",
            component="HEATER",
            timestamp=datetime.now()
        ),

        SystemAction(
            action="Buzzer activated",
            component="BUZZER",
            timestamp=datetime.now()
        ),

        SystemAction(
            action="Emergency mode activated",
            component="SYSTEM",
            timestamp=datetime.now()
        )
    ]

    # -----------------------------------------------------
    # Push actions
    # -----------------------------------------------------

    print("Adding system actions...")

    for action in actions:
        stack.push(action)

    stack.display()

    print("\nStack size:", stack.size())

    # -----------------------------------------------------
    # Peek
    # -----------------------------------------------------

    print("\nMost recent action:")

    stack.peek().display()

    # -----------------------------------------------------
    # Pop
    # -----------------------------------------------------

    print("\nUndoing most recent action:")

    removed_action = stack.pop()
    removed_action.display()

    print("\nStack after pop:")

    stack.display()

    print("\nRemaining stack size:", stack.size())
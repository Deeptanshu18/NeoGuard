# =========================================================
# SNCS - CONTROL ENGINE
# =========================================================

from datetime import datetime

from backend.dsa.stack import ActionStack, SystemAction

from backend.services.database_service import (
    save_actuator_log,
    save_event
)


# =========================================================
# CONTROL ENGINE
# =========================================================

class ControlEngine:

    def __init__(self):

        self.heater = False
        self.fan = False
        self.buzzer = False
        self.emergency_mode = False

        self.action_stack = ActionStack()

    # =====================================================
    # RECORD ACTION
    # =====================================================

    def record_action(self, device, action):

        timestamp = datetime.now()

        action_data = SystemAction(
            action=action,
            component=device,
            timestamp=timestamp
        )

        self.action_stack.push(action_data)

        # Save actuator action to SQL
        if device in ["HEATER", "FAN", "BUZZER"]:

            state = "ON" if "ON" in action else "OFF"

            save_actuator_log(
                device,
                state
            )

        # Save system events to SQL
        if device == "SYSTEM":

            save_event(
                "EMERGENCY",
                action
            )

        # Save movement/vibration events to SQL
        if device in ["ITG/MPU", "SW420"]:

            save_event(
                device,
                action
            )

    # =====================================================
    # HEATER CONTROL
    # =====================================================

    def set_heater(self, state):

        if self.heater != state:

            self.heater = state

            if state:

                self.record_action(
                    "HEATER",
                    "Heater turned ON"
                )

                print("HEATER → ON")

            else:

                self.record_action(
                    "HEATER",
                    "Heater turned OFF"
                )

                print("HEATER → OFF")

    # =====================================================
    # FAN CONTROL
    # =====================================================

    def set_fan(self, state):

        if self.fan != state:

            self.fan = state

            if state:

                self.record_action(
                    "FAN",
                    "Fan turned ON"
                )

                print("FAN → ON")

            else:

                self.record_action(
                    "FAN",
                    "Fan turned OFF"
                )

                print("FAN → OFF")

    # =====================================================
    # BUZZER CONTROL
    # =====================================================

    def set_buzzer(self, state):

        if self.buzzer != state:

            self.buzzer = state

            if state:

                self.record_action(
                    "BUZZER",
                    "Buzzer activated"
                )

                print("BUZZER → ON")

            else:

                self.record_action(
                    "BUZZER",
                    "Buzzer deactivated"
                )

                print("BUZZER → OFF")

    # =====================================================
    # EMERGENCY MODE
    # =====================================================

    def set_emergency_mode(self, state):

        if self.emergency_mode != state:

            self.emergency_mode = state

            if state:

                self.record_action(
                    "SYSTEM",
                    "Emergency mode activated"
                )

                print("EMERGENCY MODE → ACTIVE")

            else:

                self.record_action(
                    "SYSTEM",
                    "Emergency mode deactivated"
                )

                print("EMERGENCY MODE → INACTIVE")

    # =====================================================
    # MOVEMENT EVENT
    # =====================================================

    def record_movement(self, detected):

        if detected:

            self.record_action(
                "ITG/MPU",
                "Movement detected"
            )

            print("ITG/MPU → MOVEMENT DETECTED")

    # =====================================================
    # VIBRATION EVENT
    # =====================================================

    def record_vibration(self, detected):

        if detected:

            self.record_action(
                "SW420",
                "Vibration detected"
            )

            print("SW420 → VIBRATION DETECTED")

    # =====================================================
    # TEMPERATURE CONTROL
    # =====================================================

    def control_temperature(self, temperature):

        print(
            f"\nControlling temperature: "
            f"{temperature} °C"
        )

        # -------------------------------------------------
        # LOW TEMPERATURE
        # -------------------------------------------------

        if temperature < 36.0:

            self.set_heater(True)
            self.set_fan(False)

        # -------------------------------------------------
        # NORMAL TEMPERATURE
        # -------------------------------------------------

        elif 36.0 <= temperature <= 37.5:

            self.set_heater(False)
            self.set_fan(False)

        # -------------------------------------------------
        # HIGH TEMPERATURE
        # -------------------------------------------------

        elif temperature > 38.0:

            self.set_heater(False)
            self.set_fan(True)

        # -------------------------------------------------
        # BETWEEN NORMAL AND HIGH
        # -------------------------------------------------

        else:

            self.set_heater(False)
            self.set_fan(False)

        # -------------------------------------------------
        # CRITICAL TEMPERATURE
        # -------------------------------------------------

        if temperature >= 39.0:

            self.set_buzzer(True)
            self.set_emergency_mode(True)

        else:

            self.set_buzzer(False)
            self.set_emergency_mode(False)

    # =====================================================
    # DISPLAY SYSTEM STATUS
    # =====================================================

    def display_status(self):

        print("\nCurrent Actuator Status:")

        print(
            "Heater:",
            "ON" if self.heater else "OFF"
        )

        print(
            "Fan:",
            "ON" if self.fan else "OFF"
        )

        print(
            "Buzzer:",
            "ON" if self.buzzer else "OFF"
        )

        print(
            "Emergency Mode:",
            "ACTIVE"
            if self.emergency_mode
            else "INACTIVE"
        )

    # =====================================================
    # DISPLAY ACTION HISTORY
    # =====================================================

    def display_action_history(self):

        print("\nSystem Action History:")

        self.action_stack.display()


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    controller = ControlEngine()

    # -----------------------------------------------------
    # Normal temperature
    # -----------------------------------------------------

    print("\n--- NORMAL TEMPERATURE ---")

    controller.control_temperature(37.0)

    controller.display_status()

    # -----------------------------------------------------
    # High temperature
    # -----------------------------------------------------

    print("\n--- HIGH TEMPERATURE ---")

    controller.control_temperature(38.2)

    controller.display_status()

    # -----------------------------------------------------
    # Critical temperature
    # -----------------------------------------------------

    print("\n--- CRITICAL TEMPERATURE ---")

    controller.control_temperature(39.5)

    controller.display_status()

    # -----------------------------------------------------
    # Low temperature
    # -----------------------------------------------------

    print("\n--- LOW TEMPERATURE ---")

    controller.control_temperature(35.5)

    controller.display_status()

    # -----------------------------------------------------
    # Movement event
    # -----------------------------------------------------

    print("\n--- MOVEMENT EVENT ---")

    controller.record_movement(True)

    # -----------------------------------------------------
    # Vibration event
    # -----------------------------------------------------

    print("\n--- VIBRATION EVENT ---")

    controller.record_vibration(True)

    # -----------------------------------------------------
    # Action history
    # -----------------------------------------------------

    controller.display_action_history()
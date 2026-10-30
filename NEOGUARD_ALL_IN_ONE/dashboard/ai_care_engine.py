from __future__ import annotations

import ast
import base64
import operator
import os
import re
import json
import urllib.request
import urllib.error
from pathlib import Path

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except Exception:
    Image = ImageDraw = ImageFilter = ImageFont = None


class AICareEngine:
    """NeoGuard AI layer.

    Works in two modes:
    1. Local Care Copilot: always available, deterministic and grounded in the
       project's sensor thresholds.
    2. Groq reasoning mode: used for Copilot and sensor interpretation only.
    3. OpenAI image mode: used only for automatic condition-image generation.

    OpenAI is never used for Copilot text or sensor reasoning.
    """

    def __init__(self):
        # Text chat provider: Groq is preferred when configured.
        # Groq is OpenAI-client compatible, but requires its own base URL.
        self.provider = os.getenv("AI_PROVIDER", "groq").strip().lower()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

        # Optional OpenAI key is kept only for true image generation.
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.image_model = os.getenv("NEOGUARD_IMAGE_MODEL", "gpt-image-2").strip()
        self.last_error = ""
        self.last_ai_assessment = None

        self.chat_client = bool(self.provider == "groq" and self.groq_key)
        # NeoGuard V15: Groq controls animation parameters; no image API is required.
        self.image_client = False
        self.last_animation_spec = None

        # NeoGuard deliberately uses direct HTTPS for Groq. This keeps
        # the Groq path independent of Python HTTP/compression SDK issues and
        # keeps the OpenAI key isolated to image generation.

    @property
    def online(self) -> bool:
        return bool(self.chat_client)

    @property
    def status_text(self) -> str:
        if self.provider == "groq" and self.chat_client:
            return f"AI ONLINE • GROQ • {self.groq_model}"
        if self.provider == "groq":
            return "AI OFFLINE • GROQ NOT CONNECTED"
        return "AI OFFLINE • SET AI_PROVIDER=groq"

    def analyze(self, data):
        # The only temperature sensor is the DHT22, which reads AMBIENT room air, not
        # body temperature. Fever comes from the digital NTC signal (the "emergency"
        # flag), so ambient values must not be judged against body-temperature bands.
        t = None
        h = data.get("humidity")
        movement = bool(data.get("movement"))
        vibration = bool(data.get("vibration"))
        emergency = bool(data.get("emergency"))

        issues = []
        do = []
        dont = []
        score = 96
        condition = "STABLE"

        if emergency:
            condition = "EMERGENCY MODE"
            score = 20
            issues.append("The control system has recorded an emergency state.")
            do.extend([
                "Check the physical NeoGuard station and sensor connections.",
                "Follow your project's emergency response procedure.",
                "Escalate to qualified clinical staff when required.",
            ])
            dont.append("Do not treat the dashboard as a substitute for clinical judgement.")
        elif t is not None and t >= 39.0:
            condition = "CRITICAL TEMPERATURE"
            score = 15
            issues.append(f"Temperature is critically high at {t:.1f} °C.")
            do.extend([
                "Check the baby and sensor placement immediately.",
                "Verify the reading with the intended clinical measurement method.",
                "Follow your clinical escalation procedure.",
            ])
            dont.append("Do not rely on a single sensor reading for a medical decision.")
        elif t is not None and t > 38.0:
            condition = "HIGH TEMPERATURE"
            score = 48
            issues.append(f"Temperature is above the configured high threshold at {t:.1f} °C.")
            do.extend([
                "Check sensor placement and the physical environment.",
                "Watch whether the reading remains elevated.",
                "Escalate according to your project/clinical procedure if persistent.",
            ])
            dont.append("Do not ignore a sustained high reading.")
        elif t is not None and t < 35.0:
            condition = "CRITICAL TEMPERATURE"
            score = 15
            issues.append(f"Temperature is critically low at {t:.1f} °C.")
            do.extend([
                "Check the baby and sensor placement immediately.",
                "Verify the reading with the intended clinical measurement method.",
                "Follow your clinical escalation procedure.",
            ])
            dont.append("Do not use the dashboard alone to diagnose or treat a condition.")
        elif t is not None and t < 36.0:
            condition = "LOW TEMPERATURE"
            score = 50
            issues.append(f"Temperature is below the configured low threshold at {t:.1f} °C.")
            do.extend([
                "Check sensor placement and the surrounding environment.",
                "Watch the trend for persistent low readings.",
                "Escalate according to your project/clinical procedure if persistent.",
            ])
            dont.append("Do not assume a single low reading explains the whole situation.")
        elif t is not None and not (36.5 <= t <= 37.5):
            condition = "TEMPERATURE WATCH"
            score = 78
            issues.append(f"Temperature is outside the project's normal band at {t:.1f} °C.")
            do.append("Continue monitoring the trend and verify sensor placement.")
            dont.append("Do not overreact to one isolated reading.")

        if h is not None and not (30 <= h <= 70):
            score = min(score, 84)
            issues.append(f"Ambient humidity is {h:.0f}%, outside the configured 30–70% band.")
            do.append("Check the local environment and continue monitoring humidity.")

        if vibration:
            score = min(score, 70)
            issues.append("Vibration activity has been detected.")
            do.append("Check the station and surrounding surface for vibration sources.")
        elif movement:
            issues.append("Movement has been detected by the motion sensor.")

        if not issues:
            do = [
                "Continue normal monitoring.",
                "Keep the sensor setup secure and unobstructed.",
                "Watch the trend for sustained changes.",
            ]
            dont = ["Do not assume one normal reading guarantees ongoing stability."]

        return {
            "condition": condition,
            "score": max(0, min(100, score)),
            "issues": issues,
            "do": do,
            "dont": dont,
        }

    def _safe_math(self, expression):
        """Evaluate simple arithmetic only; never execute arbitrary Python."""
        expression = expression.strip().replace("×", "*").replace("÷", "/").replace("^", "**")
        if len(expression) > 80 or not re.fullmatch(r"[0-9\s+\-*/().%]+", expression):
            return None
        allowed = {
            ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        try:
            node = ast.parse(expression, mode="eval")
            def walk(n):
                if isinstance(n, ast.Expression): return walk(n.body)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                    if abs(float(n.value)) > 1e12: raise ValueError
                    return n.value
                if isinstance(n, ast.UnaryOp) and type(n.op) in allowed:
                    return allowed[type(n.op)](walk(n.operand))
                if isinstance(n, ast.BinOp) and type(n.op) in allowed:
                    left, right = walk(n.left), walk(n.right)
                    if isinstance(n.op, ast.Pow) and abs(float(right)) > 8: raise ValueError
                    return allowed[type(n.op)](left, right)
                raise ValueError
            result = walk(node)
            if isinstance(result, complex) or abs(float(result)) > 1e15: return None
            return int(result) if float(result).is_integer() else round(float(result), 8)
        except Exception:
            return None

    def quick_reply(self, question, data):
        """Strong offline fallback for common questions plus NeoGuard sensor Q&A."""
        q = question.lower().strip()
        q_clean = re.sub(r"[^a-z0-9+*/().%\-\s]", "", q)
        a = self.analyze(data)
        t = data.get("temperature")
        h = data.get("humidity")
        movement = data.get("movement")
        vibration = data.get("vibration")

        # Simple arithmetic: "what is 2+2", "2 * 8", etc.
        math_match = re.search(r"(?:what is|calculate|solve)\s+([0-9\s+\-*/().%×÷^]+)\s*\??$", q)
        if math_match:
            result = self._safe_math(math_match.group(1))
            if result is not None:
                return f"{math_match.group(1).strip()} = {result}"
        if re.fullmatch(r"[0-9\s+\-*/().%×÷^]+", q_clean) and any(ch in q_clean for ch in "+-*/%"):
            result = self._safe_math(q_clean)
            if result is not None:
                return f"{q.strip()} = {result}"

        if q in {"hi", "hello", "hey", "hey neoguard", "hello neoguard"} or q.startswith("good morning") or q.startswith("good evening"):
            return f"Hi! I'm NeoGuard Care Copilot. The current station status is {a['condition']}. You can ask me anything about the sensor readings, or simple general questions."
        if any(x in q for x in ["thank you", "thanks", "thx"]):
            return "You're welcome. I'm here to help you understand the NeoGuard prototype."
        if "who are you" in q or "what are you" in q:
            return "I'm NeoGuard Care Copilot, the AI assistant inside the NeoGuard neonatal monitoring prototype. I can explain sensor data, alerts, actuators and general questions."
        if "what is neoguard" in q or "what does neoguard do" in q:
            return "NeoGuard is a smart neonatal monitoring prototype. It uses sensors such as temperature, humidity, movement and vibration, then applies alerts, control logic and data structures to help monitor the station."
        if "what sensors" in q or "which sensors" in q:
            return "The current prototype uses an NTC thermistor for temperature, DHT11/DHT22 for ambient humidity, an MPU/MPU6050-type motion sensor for movement, and an SW420 vibration sensor."
        if "how is my baby" in q or "how is baby" in q or "is my baby okay" in q or "is the baby okay" in q or "baby okay" in q:
            if a["condition"] == "STABLE":
                return f"Based on the NeoGuard sensors, the current station state is STABLE. Temperature is {t:.1f} °C and humidity is {h:.0f}% if available. Movement is {'detected' if movement else 'not detected'}, and vibration is {'detected' if vibration else 'not detected'}. This is a sensor status, not a medical diagnosis."
            return f"NeoGuard currently reports {a['condition']}. {a['issues'][0] if a['issues'] else 'Please review the sensor readings and follow your project response procedure.'}"
        if any(x in q for x in ["what should i do", "what do i do", "do right now", "action", "next step"]):
            return f"Current status: {a['condition']}.\n\n" + "\n".join("• " + x for x in a["do"][:4])
        if "avoid" in q or "shouldn't" in q or "dont" in q or "do not" in q:
            return f"For {a['condition'].lower()}, avoid:\n\n" + "\n".join("• " + x for x in a["dont"][:4])
        if "temperature" in q or "temp" in q:
            if t is None:
                return "Temperature data is not available yet."
            return f"The DHT22 is reading {t:.1f} °C of ambient room temperature. This is the room, not the baby's body temperature. Fever is detected separately by the NTC signal, and the station is currently {a['condition'].lower()}."
        if "humidity" in q or "humid" in q:
            if h is None:
                return "Humidity data is not available yet."
            return f"Ambient humidity is {h:.0f}%. NeoGuard's configured monitoring band is 30–70%."
        if "activity" in q or "movement" in q or "vibration" in q:
            return f"Movement: {'DETECTED' if movement else 'NONE'}\nVibration: {'DETECTED' if vibration else 'NONE'}\n\nThese sensors indicate activity status; they do not by themselves establish a medical condition."
        if "heater" in q or "fan" in q or "buzzer" in q or "actuator" in q:
            return "NeoGuard uses the control engine to respond to sensor thresholds. In the configured prototype logic, low temperature can request heating, high temperature can request fan cooling, and an emergency/high-critical condition can activate the buzzer."
        if "status" in q or "stable" in q or "current state" in q:
            issues = "\n".join("• " + x for x in a["issues"][:3]) if a["issues"] else "• All configured sensor values are currently within the project's stable ranges."
            return f"NeoGuard status: {a['condition']} ({a['score']}% stability indicator).\n\n{issues}"
        return "__ONLINE_AI_REQUIRED__"

    def _state_payload(self, data):
        analysis = self.analyze(data)
        actuators = data.get("actuators") or {}
        return {
            "temperature_c": data.get("temperature"),
            "humidity_percent": data.get("humidity"),
            "movement_detected": bool(data.get("movement")),
            "vibration_detected": bool(data.get("vibration")),
            "emergency": bool(data.get("emergency")),
            "actuators": actuators,
            "neoguard_condition": analysis["condition"],
            "stability_indicator_percent": analysis["score"],
            "configured_normal_temperature_c": "36.5-37.5",
            "configured_high_temperature_c": ">38.0",
            "configured_critical_temperature_c": ">=39.0 or <35.0",
            "configured_humidity_percent": "30-70",
            "local_analysis": analysis,
        }

    def _groq_text(self, system, user, max_tokens=700, structured=False):
        """Call Groq directly over HTTPS.

        This avoids an SDK/http compression incompatibility seen on some
        macOS Python environments (the previous client raised
        `Decompressor.decompress() ... output_buffer_limit`).
        """
        if not self.groq_key:
            return None

        if structured:
            instruction = (
                "Return ONLY valid JSON with exactly these keys: "
                "condition, severity, caregiver_answer, what_to_do, "
                "what_to_avoid, visual_prompt, visual_reason. "
                "what_to_do and what_to_avoid must be JSON arrays of strings. "
                "Do not wrap the JSON in markdown fences."
            )
            user = user + "\n\n" + instruction

        payload = {
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_completion_tokens": max_tokens,
        }
        if self.provider == "groq":
            payload["reasoning_effort"] = "low"

        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "NeoGuard/13",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read().decode("utf-8")
            obj = json.loads(body)
            content = obj.get("choices", [{}])[0].get("message", {}).get("content")
            if content:
                self.last_error = ""
                return content.strip()
            self.last_error = f"Groq returned no message content: {body[:300]}"
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:800]
            except Exception:
                detail = str(exc)
            self.last_error = f"Groq HTTP {exc.code}: {detail}"
            print(f"NeoGuard Groq API error: {self.last_error}")
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            print(f"NeoGuard Groq API error: {self.last_error}")
        return None

    def _ai_assessment(self, data):
        """Ask Groq to interpret the exact live dashboard state and build a visual prompt."""
        state = self._state_payload(data)
        system = """You are NeoGuard Care Copilot, the reasoning layer of a student smart neonatal monitoring prototype.
You receive the CURRENT dashboard sensor state. Treat those values as the source of truth for the prototype state.
Do not invent camera observations, patient appearance, diagnoses, medications, or clinical measurements.
This is sensor intelligence, not a medical diagnosis. If the state is abnormal, clearly say that the caregiver should check the baby/station and follow the project's clinical escalation procedure rather than giving treatment instructions.
For the visual prompt, create a safe educational illustration description that visibly reflects the actual condition: temperature level, humidity, movement/vibration activity, alert severity, and actuator response when provided.
Never depict a live camera feed, surveillance view, identifiable real baby, injury, gore, needles, or frightening medical distress.
The visual should be a conceptual neonatal-care illustration, not a claim of what the baby looks like."""
        user = f"CURRENT NEOGUARD DASHBOARD STATE:\n{state}\n\nReturn a structured assessment for this exact state."
        raw = self._groq_text(system, user, max_tokens=900, structured=True)
        if not raw:
            return None
        try:
            import json
            obj = json.loads(raw)
            self.last_ai_assessment = obj
            return obj
        except Exception as exc:
            self.last_error = f"Invalid structured AI response: {exc}"
            return None

    def ai_chat(self, question, data):
        # Local answers remain instant for deterministic project questions/math.
        local = self.quick_reply(question, data)
        q = question.lower().strip()
        if local != "__ONLINE_AI_REQUIRED__":
            known = (
                re.search(r"(?:what is|calculate|solve)\s+[0-9\s+\-*/().%×÷^]+\s*\??$", q)
                or re.fullmatch(r"[0-9\s+\-*/().%×÷^]+", q)
                or any(k in q for k in [
                    "hello", "hi", "hey", "thanks", "thank you", "who are you",
                    "what are you", "what is neoguard", "what sensors", "which sensors",
                    "how is my baby", "how is baby", "is my baby okay", "baby okay",
                    "what should i do", "what do i do", "what should i avoid",
                    "temperature", "temp", "humidity", "humid", "movement", "vibration",
                    "activity", "heater", "fan", "buzzer", "actuator", "status",
                    "stable", "current state", "avoid", "shouldn't", "do not"
                ])
            )
            if known:
                # For general questions, don't let broad keyword matching hijack the query.
                if any(k in q for k in ["what should i do", "what do i do", "avoid", "shouldn't", "do not", "temperature", "temp", "humidity", "humid", "movement", "vibration", "activity", "heater", "fan", "buzzer", "actuator", "status", "stable", "current state", "how is my baby", "baby okay"]):
                    return local
                if q in {"hi", "hello", "hey", "hey neoguard", "hello neoguard"} or any(k in q for k in ["thanks", "thank you", "who are you", "what are you", "what is neoguard", "what sensors", "which sensors"]):
                    return local
                if re.search(r"(?:what is|calculate|solve)\s+[0-9\s+\-*/().%×÷^]+\s*\??$", q) or re.fullmatch(r"[0-9\s+\-*/().%×÷^]+", q):
                    return local

        if not self.chat_client:
            return "Groq is not connected. Keep GROQ_API_KEY exported and relaunch NeoGuard."

        state = self._state_payload(data)
        prompt = f"""CURRENT NEO GUARD STATE:\n{state}\n\nUSER QUESTION:\n{question}\n\nAnswer naturally and directly. If the question is about the baby/station, ground it in the current state above. If it is a general question, answer it normally while keeping NeoGuard context available when useful. Do not claim camera access or diagnose a patient."""
        answer = self._groq_text(
            "You are a helpful general-purpose AI assistant embedded in NeoGuard. The current sensor state is provided as context; never invent missing readings or camera observations.",
            prompt,
            max_tokens=700,
            structured=False,
        )
        if answer:
            return answer
        return f"I couldn't reach Groq right now, so I can't answer that reliably.\n\n[Groq error: {self.last_error or 'unknown API error'}]"

    def _font(self, size, bold=False):
        if ImageFont is None:
            return None
        candidates = [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
        if bold:
            candidates = [
                "/System/Library/Fonts/SFNS.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial Bold.ttf",
            ] + candidates
        for p in candidates:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _local_visual(self, data):
        """Create a clearly-labelled offline educational visual; never a fake camera feed."""
        if Image is None:
            return None
        out_dir = Path("ai_generated")
        out_dir.mkdir(exist_ok=True)
        path = out_dir / "neoguard_condition_visual.png"

        W, H = 1400, 820
        img = Image.new("RGB", (W, H), (5, 13, 24))
        draw = ImageDraw.Draw(img)
        condition = self.analyze(data)["condition"]
        accent = {
            "STABLE": (65, 230, 162), "TEMPERATURE WATCH": (255, 209, 102),
            "LOW TEMPERATURE": (255, 159, 67), "HIGH TEMPERATURE": (255, 159, 67),
            "CRITICAL TEMPERATURE": (255, 93, 115), "EMERGENCY MODE": (255, 93, 115),
        }.get(condition, (83, 216, 251))

        # Background glow / room panels.
        draw.rounded_rectangle((35, 35, W-35, H-35), radius=32, fill=(8, 24, 39), outline=(24, 66, 91), width=3)
        draw.rounded_rectangle((65, 70, 860, 750), radius=28, fill=(7, 20, 33), outline=(20, 55, 77), width=2)
        draw.rounded_rectangle((900, 70, 1335, 750), radius=28, fill=(10, 31, 48), outline=accent, width=2)

        # Stylised crib — educational illustration, not a photograph.
        crib_x1, crib_y1, crib_x2, crib_y2 = 145, 285, 800, 660
        draw.rounded_rectangle((crib_x1, crib_y1, crib_x2, crib_y2), radius=22, fill=(18, 37, 52), outline=(83, 216, 251), width=5)
        draw.rounded_rectangle((175, 390, 770, 630), radius=18, fill=(220, 228, 232), outline=(110, 137, 151), width=3)
        # Mattress and blanket.
        draw.rounded_rectangle((205, 485, 740, 610), radius=28, fill=(235, 239, 241), outline=(150, 166, 176), width=2)
        draw.ellipse((390, 455, 525, 585), fill=(235, 198, 175), outline=(160, 130, 115), width=2)
        draw.arc((425, 492, 490, 540), 10, 170, fill=(90, 75, 70), width=3)
        draw.rounded_rectangle((355, 530, 620, 615), radius=32, fill=(190, 215, 228), outline=(125, 158, 174), width=2)
        # Crib rails.
        for x in range(180, 780, 48):
            draw.line((x, 275, x, 670), fill=(140, 167, 180), width=7)
        draw.line((130, 675, 820, 675), fill=(83, 216, 251), width=7)
        # Condition-specific visual cues. These are a fallback only; the real AI image
        # uses the Groq-generated visual prompt when an image API key is available.
        if "HIGH TEMPERATURE" in condition or "CRITICAL TEMPERATURE" in condition or "EMERGENCY" in condition:
            # Heat waves above the crib.
            for off in (0, 55, 110):
                draw.arc((250 + off, 185, 320 + off, 265), 205, 335, fill=accent, width=6)
            if data.get("actuators", {}).get("FAN") == "ON":
                draw.arc((735, 300, 830, 395), 30, 330, fill=(83,216,251), width=6)
                draw.arc((750, 315, 815, 380), 30, 330, fill=(83,216,251), width=4)
        elif "LOW TEMPERATURE" in condition:
            # Cooling cue / low-temperature indicator.
            draw.text((270, 205), "❄", font=self._font(52, True), fill=accent)
            draw.text((420, 205), "LOW TEMP", font=self._font(24, True), fill=accent)
        else:
            draw.arc((300, 205, 380, 275), 205, 335, fill=(65,230,162), width=5)
            draw.arc((430, 205, 510, 275), 205, 335, fill=(65,230,162), width=5)

        if data.get("movement"):
            draw.arc((535, 445, 610, 520), 275, 85, fill=(255,209,102), width=5)
            draw.arc((560, 430, 650, 530), 275, 85, fill=(255,209,102), width=4)
        if data.get("vibration"):
            for y in (355, 390, 425):
                draw.line((90, y, 135, y-12), fill=(167,139,250), width=5)
                draw.line((90, y, 135, y+12), fill=(167,139,250), width=5)

        # Sensor nodes.
        for x, y in [(190, 250), (720, 250), (160, 650), (780, 650)]:
            draw.ellipse((x-12, y-12, x+12, y+12), fill=accent, outline=(235,245,250), width=2)
        draw.text((95, 100), "NEOGUARD", font=self._font(48, True), fill=(83, 216, 251))
        draw.text((98, 160), "AI CONDITION VISUAL", font=self._font(24, True), fill=(247, 250, 252))
        draw.text((98, 198), "Educational illustration • no camera connected", font=self._font(18), fill=(145, 164, 184))

        # Right-side status card.
        draw.text((945, 110), "CURRENT SENSOR STATE", font=self._font(21, True), fill=(83, 216, 251))
        draw.text((945, 155), condition, font=self._font(42, True), fill=accent)
        draw.text((945, 220), "Sensor-derived visual only", font=self._font(18), fill=(145, 164, 184))
        vals = [
            f"TEMPERATURE   {data.get('temperature'):.1f} °C" if data.get('temperature') is not None else "TEMPERATURE   --",
            f"HUMIDITY   {data.get('humidity'):.0f}%" if data.get('humidity') is not None else "HUMIDITY   --",
            f"MOVEMENT   {'DETECTED' if data.get('movement') else 'NONE'}",
            f"VIBRATION   {'DETECTED' if data.get('vibration') else 'NONE'}",
        ]
        for i, v in enumerate(vals):
            y = 300 + i * 62
            draw.rounded_rectangle((940, y, 1295, y+46), radius=12, fill=(7, 21, 34), outline=(27, 62, 83), width=2)
            draw.text((960, y+10), v, font=self._font(17, True), fill=(247, 250, 252))
        draw.text((945, 590), "SENSOR-AWARE VISUAL", font=self._font(17, True), fill=accent)
        draw.text((945, 625), "Groq interprets the condition.\nAdd OPENAI_API_KEY for a true AI image.", font=self._font(17), fill=(145, 164, 184), spacing=8)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.08))
        img.save(path)
        return str(path)

    def get_animation_spec(self, data):
        """Ask Groq for the visual animation state.

        Groq does not render pixels/video here. It generates a compact animation
        specification which the local Tkinter canvas renders immediately.
        """
        analysis = self.analyze(data)
        state = self._state_payload(data)
        system = """You are the NeoGuard animation director.
You receive the exact sensor state of a smart neonatal monitoring prototype.
Return ONLY JSON. You control a LOCAL dashboard animation, not a camera and not a real baby.
The animation must visually communicate the sensor condition without showing injury,
gore, distress, surveillance or an identifiable child.

Allowed mode values: stable, watch, critical, low, recovery.
Use the condition and sensor values to choose severity 0-5.
Return exactly these keys:
mode, severity, pulse_speed, wave_speed, glow_strength, particle_count,
sweep_speed, accent, caption.

Numeric ranges:
severity 0-5
pulse_speed 0.2-2.5
wave_speed 0.2-3.0
glow_strength 1-8
particle_count 0-18
sweep_speed 0.2-4.0
accent must be one of: green, cyan, amber, red.
caption must be a short dashboard label.

The result should make NORMAL calm, WATCH more active, CRITICAL unmistakably urgent,
LOW cool/low-energy, and RECOVERY gradually calming."""
        demo_phase = data.get("_demo_phase", "")
        user = f"""LOCAL RULE-BASED CONDITION: {analysis['condition']}
DEMO PHASE (if present): {demo_phase or "none"}
CURRENT NEOGUARD STATE:
{state}

If DEMO PHASE is RECOVERY, use mode="recovery" even though the underlying sensor state has returned to stable.
Choose the animation parameters for this exact state."""
        raw = self._groq_text(system, user, max_tokens=320, structured=False)
        if raw:
            try:
                # Be tolerant if a model accidentally wraps JSON in fences.
                cleaned = raw.strip()
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                try:
                    obj = json.loads(cleaned)
                except json.JSONDecodeError:
                    # Recover a JSON object if the reasoning model added a short
                    # sentence before/after it.
                    match = re.search(r"\{.*\}", cleaned, flags=re.S)
                    if not match:
                        raise
                    obj = json.loads(match.group(0))
                required = {
                    "mode", "severity", "pulse_speed", "wave_speed",
                    "glow_strength", "particle_count", "sweep_speed",
                    "accent", "caption"
                }
                if required.issubset(obj):
                    spec = {
                        "mode": str(obj["mode"]).lower(),
                        "severity": max(0, min(5, int(float(obj["severity"])))),
                        "pulse_speed": max(0.2, min(2.5, float(obj["pulse_speed"]))),
                        "wave_speed": max(0.2, min(3.0, float(obj["wave_speed"]))),
                        "glow_strength": max(1, min(8, int(float(obj["glow_strength"])))),
                        "particle_count": max(0, min(18, int(float(obj["particle_count"])))),
                        "sweep_speed": max(0.2, min(4.0, float(obj["sweep_speed"]))),
                        "accent": str(obj["accent"]).lower(),
                        "caption": str(obj["caption"])[:70],
                    }
                    if spec["accent"] not in {"green", "cyan", "amber", "red"}:
                        raise ValueError("invalid accent")
                    self.last_animation_spec = spec
                    return spec
            except Exception as exc:
                self.last_error = f"Invalid animation JSON: {exc}"
                print(f"NeoGuard animation spec error: {self.last_error}")

        # Instant deterministic fallback if Groq is unavailable.
        c = analysis["condition"]
        if "CRITICAL" in c or "EMERGENCY" in c:
            spec = {"mode":"critical","severity":5,"pulse_speed":2.2,"wave_speed":2.8,
                    "glow_strength":7,"particle_count":16,"sweep_speed":3.8,
                    "accent":"red","caption":"GROQ/DIRECT • CRITICAL • EMERGENCY"}
        elif "HIGH" in c or "WATCH" in c:
            spec = {"mode":"watch","severity":3,"pulse_speed":1.25,"wave_speed":1.7,
                    "glow_strength":4,"particle_count":10,"sweep_speed":2.2,
                    "accent":"amber","caption":"GROQ/DIRECT • TEMPERATURE WATCH"}
        elif "LOW" in c:
            spec = {"mode":"low","severity":2,"pulse_speed":0.55,"wave_speed":0.7,
                    "glow_strength":3,"particle_count":8,"sweep_speed":1.0,
                    "accent":"cyan","caption":"GROQ/DIRECT • LOW TEMPERATURE"}
        else:
            spec = {"mode":"stable","severity":0,"pulse_speed":0.35,"wave_speed":0.5,
                    "glow_strength":2,"particle_count":4,"sweep_speed":0.7,
                    "accent":"green","caption":"GROQ/DIRECT • STABLE"}
        self.last_animation_spec = spec
        return spec

    def generate_condition_image(self, data):
        """Generate a visual from the CURRENT dashboard state.

        Groq (GPT-OSS 120B) interprets the sensor state and creates the image
        prompt. A separate image-capable API is required to actually render
        pixels; OpenAI Images is supported when OPENAI_API_KEY is configured.
        """
        out_dir = Path("ai_generated")
        out_dir.mkdir(exist_ok=True)

        assessment = self._ai_assessment(data) if self.chat_client else None
        analysis = self.analyze(data)

        if assessment:
            visual_prompt = assessment.get("visual_prompt", "")
            condition = assessment.get("condition", analysis["condition"])
            visual_reason = assessment.get("visual_reason", "AI visual based on current sensor state.")
        else:
            condition = analysis["condition"]
            visual_reason = "Local sensor-derived fallback because the AI assessment was unavailable."
            visual_prompt = f"Educational neonatal care illustration representing {condition}; temperature {data.get('temperature')}, humidity {data.get('humidity')}, movement {bool(data.get('movement'))}, vibration {bool(data.get('vibration'))}. Show a generic crib, sensor modules and appropriate environmental cues. No camera feed, no identifiable baby, no injury or distress."

        # True image generation: OpenAI is used ONLY here.
        # We call the Images API directly so image generation does not depend on
        # the OpenAI Python SDK version installed on the student's Mac.
        if self.image_client:
            prompt = f"""Create a premium presentation-ready educational illustration for the NeoGuard smart neonatal monitoring prototype.
The illustration MUST reflect the current sensor-derived condition described below. It is a conceptual visualization, not a photograph or camera feed.

CURRENT CONDITION: {condition}

AI-GENERATED VISUAL DIRECTION:
{visual_prompt}

IMPORTANT:
- Show a generic neonatal crib scene only as a conceptual educational scene; do not depict an identifiable real child.
- Do not claim or imply that NeoGuard can visually see the baby.
- Do not include a camera or surveillance interface.
- No gore, injury, needles, or frightening medical distress.
- Make environmental and device cues match the condition: normal/stable should feel calm; elevated temperature should show appropriate cooling/heat cues; critical/emergency should show clear but non-frightening alert and intervention cues.
- Use a premium deep-navy, cyan, teal and soft-violet NeoGuard medical-tech aesthetic.
- Wide landscape composition suitable for a desktop dashboard.
- Avoid large amounts of text inside the image.
"""
            payload = {
                "model": self.image_model,
                "prompt": prompt,
                "size": "1536x1024",
                "quality": "medium",
                "output_format": "png",
            }
            request = urllib.request.Request(
                "https://api.openai.com/v1/images/generations",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "NeoGuard/14",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    body = response.read().decode("utf-8")
                obj = json.loads(body)
                items = obj.get("data") or []
                b64 = items[0].get("b64_json") if items else None
                if b64:
                    path = out_dir / "neoguard_ai_condition.png"
                    path.write_bytes(base64.b64decode(b64))
                    self.last_ai_assessment = assessment
                    self.last_error = ""
                    return str(path), f"AI visual • {condition} • OpenAI generated from current sensor state"
                self.last_error = f"OpenAI image API returned no image data: {body[:500]}"
                print(self.last_error)
            except urllib.error.HTTPError as exc:
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:900]
                except Exception:
                    detail = str(exc)
                self.last_error = f"OpenAI image HTTP {exc.code}: {detail}"
                print(f"NeoGuard OpenAI image error: {self.last_error}")
            except Exception as exc:
                self.last_error = f"OpenAI image error: {type(exc).__name__}: {exc}"
                print(f"NeoGuard OpenAI image error: {self.last_error}")

        path = self._local_visual(data)
        if assessment:
            return path, f"Groq interpreted {condition} • OpenAI image unavailable (local visual fallback)"
        return path, f"Sensor-derived {condition} visual • OpenAI image unavailable"


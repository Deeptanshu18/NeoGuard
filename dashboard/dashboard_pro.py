
# ============================================================
# NEOGUARD PRO — ORIGINAL PRO UI RESTORED
# Hardware-sync compatible dashboard
#
# Keeps:
#   DHT22 -> ambient temperature + humidity
#   NTC   -> digital FEVER YES/NO
#   MPU6050 -> movement + vibration
#   FEVER -> LED + BUZZER + emergency state
#   Groq -> Care Copilot
#
# Restores:
#   Old NeoGuard PRO top layout
#   Large AI CONDITION VISUAL
#   Automatic animated crib/alert visual
#   Visible Care Copilot chat
#   Live sensor matrix
#   Trends / alerts / actuators / activity
# ============================================================

from __future__ import annotations

import math
import sqlite3
import threading
import time
import tkinter as tk
from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    from ai_care_engine import AICareEngine
except Exception:
    from dashboard.ai_care_engine import AICareEngine


# ----------------------------- Palette -----------------------------

BG = "#06101C"
PANEL = "#0B1928"
PANEL2 = "#0F2235"
CARD = "#102A40"
CARD2 = "#14344E"
BORDER = "#1B405D"

TEXT = "#F5F9FC"
MUTED = "#8EA4B8"

CYAN = "#42D7F5"
CYAN2 = "#1CA8D1"
GREEN = "#38E29A"
YELLOW = "#FFD166"
ORANGE = "#FF9E3D"
RED = "#FF5870"
PURPLE = "#A78BFA"


class NeoGuardPRO:
    def __init__(self, root):
        self.root = root
        self.root.title("NEOGUARD • Smart Neonatal Care Station")
        self.root.geometry("1550x950")
        self.root.minsize(1200, 760)
        self.root.resizable(True, True)
        self.root.configure(bg=BG)

        self.db_path = Path(__file__).resolve().parents[1] / "database" / "sncs.db"
        self.ai = AICareEngine()

        self.data = {
            "ambient_temp": None,
            "humidity": None,
            "fever": False,
            "movement": False,
            "vibration": False,
            "emergency": False,
            "led": "OFF",
            "fan": "OFF",
            "buzzer": "OFF",
        }

        self.anim_phase = 0
        self.anim_job = None
        self.anim_last_sway = 0.0
        self.anim_last_breath = 0.0
        self.last_visual_state = None
        self.chat_busy = False
        self.history_rows = []

        self._build_shell()
        self._build_top_area()
        self._build_sensor_matrix()
        self._build_copilot()
        self._build_trends()
        self._build_alerts()
        self._build_actuators()
        self._build_activity()

        self._append_chat(
            "NEOGUARD COPILOT",
            "NeoGuard AI is online. I can explain the live sensor state, alerts, actuators, and recorded trends."
        )

        self.refresh()
        self.root.after(900, self.live_update)
        self.root.after(120, self.animate_visual)

    # ----------------------------- Helpers -----------------------------

    def font(self, size, weight="normal"):
        return ("SF Pro Display", size, weight)

    def db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def panel(self, parent, title, subtitle=None):
        box = tk.Frame(
            parent, bg=PANEL,
            highlightbackground=BORDER, highlightthickness=1
        )
        top = tk.Frame(box, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(
            top, text=title, font=self.font(11, "bold"),
            fg=TEXT, bg=PANEL
        ).pack(side="left")
        if subtitle:
            tk.Label(
                top, text=subtitle, font=self.font(8),
                fg=MUTED, bg=PANEL
            ).pack(side="right")
        return box

    def set_badge(self, widget, text, fg, bg):
        widget.config(text=text, fg=fg, bg=bg)

    # ----------------------------- Shell -----------------------------

    def _build_shell(self):
        self.header = tk.Frame(self.root, bg=BG, height=82)
        self.header.pack(fill="x", padx=24, pady=(14, 8))
        self.header.pack_propagate(False)

        brand = tk.Frame(self.header, bg=BG)
        brand.pack(side="left", fill="y")

        tk.Label(
            brand, text="NEOGUARD",
            font=self.font(27, "bold"), fg=CYAN, bg=BG
        ).pack(side="left", pady=(8, 0))

        tk.Label(
            brand, text="  SMART NEONATAL MONITORING",
            font=self.font(11, "bold"), fg=TEXT, bg=BG
        ).pack(side="left", pady=(15, 0))

        tk.Label(
            brand,
            text="Prototype command center • sensor intelligence • caregiver guidance",
            font=self.font(8), fg=MUTED, bg=BG
        ).pack(side="left", padx=(18, 0), pady=(17, 0))

        self.ai_badge = tk.Label(
            self.header,
            text="GROQ • NEOGUARD AI  ✦",
            font=self.font(8, "bold"),
            fg=CYAN, bg="#10293B", padx=12, pady=7
        )
        self.ai_badge.pack(side="right", pady=10, padx=(8, 0))

        self.online_badge = tk.Label(
            self.header,
            text="●  SYSTEM ONLINE",
            font=self.font(9, "bold"),
            fg=GREEN, bg="#092A25", padx=13, pady=7
        )
        self.online_badge.pack(side="right", pady=10)

    def _build_top_area(self):
        # The main workspace must occupy all space below the fixed header.
        # The previous build used fill="x", which left the rest of the Mac
        # window empty and made the dashboard look vertically broken.
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        self.nav = tk.Frame(
            outer, bg=PANEL, width=220,
            highlightbackground=BORDER, highlightthickness=1
        )
        self.nav.pack(side="left", fill="y", padx=(0, 14))
        self.nav.pack_propagate(False)

        tk.Label(
            self.nav, text="NEOGUARD", font=self.font(15, "bold"),
            fg=CYAN, bg=PANEL
        ).pack(anchor="w", padx=18, pady=(18, 2))
        tk.Label(
            self.nav, text="COMMAND CENTER", font=self.font(8, "bold"),
            fg=MUTED, bg=PANEL
        ).pack(anchor="w", padx=18, pady=(0, 14))

        self.nav_buttons = {}
        nav_items = [
            ("01", "OVERVIEW", self.scroll_top),
            ("02", "AI CARE COPILOT", self.focus_chat),
            ("03", "LIVE TRENDS", self.focus_trends),
            ("04", "ALERTS", self.focus_alerts),
            ("05", "ACTUATORS", self.focus_actuators),
            ("06", "DSA ARCHITECTURE", self.open_dsa),
        ]
        for num, label, command in nav_items:
            # Use a Frame + Label instead of a native macOS Button. Aqua
            # rendering can ignore Tk button backgrounds and turn them white.
            b = tk.Frame(self.nav, bg=PANEL2, highlightbackground=BORDER,
                         highlightthickness=1, cursor="hand2")
            b.pack(fill="x", padx=10, pady=2)
            txt = tk.Label(
                b, text=f"{num}    {label}", anchor="w",
                font=self.font(8, "bold"), fg=TEXT, bg=PANEL2,
                padx=12, pady=9, cursor="hand2"
            )
            txt.pack(fill="x")
            b.bind("<Button-1>", lambda e, cmd=command: cmd())
            txt.bind("<Button-1>", lambda e, cmd=command: cmd())
            b.bind("<Enter>", lambda e, frame=b, lab=txt: (frame.config(bg=CARD2), lab.config(bg=CARD2, fg=CYAN)))
            b.bind("<Leave>", lambda e, frame=b, lab=txt: (frame.config(bg=PANEL2), lab.config(bg=PANEL2, fg=TEXT)))
            txt.bind("<Enter>", lambda e, frame=b, lab=txt: (frame.config(bg=CARD2), lab.config(bg=CARD2, fg=CYAN)))
            txt.bind("<Leave>", lambda e, frame=b, lab=txt: (frame.config(bg=PANEL2), lab.config(bg=PANEL2, fg=TEXT)))
            self.nav_buttons[label] = b

        tk.Frame(self.nav, bg=BORDER, height=1).pack(
            fill="x", padx=16, pady=14
        )

        tk.Label(
            self.nav, text="QUICK SCENARIOS",
            font=self.font(8, "bold"), fg=MUTED, bg=PANEL
        ).pack(anchor="w", padx=18, pady=(0, 8))

        tests = [
            ("NORMAL", self.test_normal, GREEN),
            ("CRITICAL", self.test_critical, RED),
            ("RECOVERY", self.test_recovery, CYAN),
        ]
        test_row = tk.Frame(self.nav, bg=PANEL)
        test_row.pack(fill="x", padx=10)
        for label, cmd, color in tests:
            tk.Button(
                test_row, text=label, command=cmd,
                font=self.font(7, "bold"), fg=BG, bg=color,
                activebackground=color, relief="flat", bd=0,
                padx=5, pady=7, cursor="hand2"
            ).pack(side="left", fill="x", expand=True, padx=2)

        tk.Label(
            self.nav, text="DB LIVE STATE",
            font=self.font(7, "bold"), fg=MUTED, bg=PANEL
        ).pack(anchor="w", padx=18, pady=(14, 2))

        self.db_state = tk.Label(
            self.nav, text="READING…",
            font=self.font(8, "bold"), fg=CYAN, bg=PANEL
        )
        self.db_state.pack(anchor="w", padx=18)

        self.sim_btn = tk.Button(
            self.nav, text="▶  RUN 5 SCENARIOS",
            command=self.run_simulation,
            font=self.font(8, "bold"),
            fg=BG, bg=CYAN,
            activebackground=CYAN2,
            relief="flat", bd=0, pady=10, cursor="hand2"
        )
        self.sim_btn.pack(fill="x", padx=12, pady=(18, 5))

        self.sim_status = tk.Label(
            self.nav, text="READY • 5 cycles",
            font=self.font(7, "bold"), fg=MUTED, bg=PANEL
        )
        self.sim_status.pack(anchor="w", padx=18)

        # Main scrollable area
        holder = tk.Frame(outer, bg=BG)
        holder.pack(side="left", fill="both", expand=True)

        self.scroll_canvas = tk.Canvas(
            holder, bg=BG, highlightthickness=0
        )
        self.scrollbar = tk.Scrollbar(
            holder, orient="vertical",
            command=self.scroll_canvas.yview,
            bg=PANEL, troughcolor=BG
        )
        self.scrollbar.pack(side="right", fill="y")
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scroll_canvas.configure(
            yscrollcommand=self.scrollbar.set
        )

        self.content = tk.Frame(self.scroll_canvas, bg=BG)
        self.window_id = self.scroll_canvas.create_window(
            (0, 0), window=self.content, anchor="nw"
        )

        self.content.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.configure(
                scrollregion=self.scroll_canvas.bbox("all")
            )
        )
        self.scroll_canvas.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.itemconfigure(
                self.window_id, width=e.width
            )
        )
        self.scroll_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.scroll_canvas.yview_scroll(
                int(-e.delta / 120), "units"
            )
        )

    # ----------------------------- Hero / Visual -----------------------------

    def _build_top_hero(self):
        row = tk.Frame(self.content, bg=BG)
        row.pack(fill="x", pady=(0, 14))

        left = tk.Frame(
            row, bg=PANEL,
            highlightbackground=BORDER, highlightthickness=1
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 7))

        tk.Label(
            left, text="CARE STATUS",
            font=self.font(8, "bold"), fg=CYAN, bg=PANEL
        ).pack(anchor="w", padx=22, pady=(17, 3))

        self.condition = tk.Label(
            left, text="ANALYZING…",
            font=self.font(24, "bold"), fg=TEXT, bg=PANEL
        )
        self.condition.pack(anchor="w", padx=22)

        self.condition_detail = tk.Label(
            left, text="Reading live sensor state…",
            font=self.font(9), fg=MUTED, bg=PANEL,
            justify="left", wraplength=620
        )
        self.condition_detail.pack(anchor="w", padx=22, pady=(4, 12))

        self.conf_bar = tk.Canvas(
            left, height=12, bg="#17344B",
            highlightthickness=0
        )
        self.conf_bar.pack(fill="x", padx=22)
        self.conf_rect = self.conf_bar.create_rectangle(
            0, 0, 0, 12, fill=CYAN, outline=""
        )

        self.conf_text = tk.Label(
            left, text="System confidence / stability indicator: --%",
            font=self.font(7, "bold"), fg=MUTED, bg=PANEL
        )
        self.conf_text.pack(anchor="w", padx=22, pady=(5, 15))

        visual = tk.Frame(
            row, bg=PANEL,
            highlightbackground=BORDER, highlightthickness=1,
            width=650, height=320
        )
        visual.pack(side="right", fill="both", padx=(7, 0))
        visual.pack_propagate(False)

        top = tk.Frame(visual, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(13, 4))
        tk.Label(
            top, text="✦  AI CONDITION VISUAL",
            font=self.font(10, "bold"), fg=CYAN, bg=PANEL
        ).pack(side="left")
        tk.Label(
            top, text="AUTO • NO CAMERA • GROQ-DIRECTED",
            font=self.font(7, "bold"), fg=MUTED, bg=PANEL
        ).pack(side="right")

        self.visual_canvas = tk.Canvas(
            visual, bg="#081725", highlightthickness=1,
            highlightbackground=BORDER
        )
        self.visual_canvas.pack(
            fill="both", expand=True, padx=14, pady=(0, 8)
        )

        self.visual_footer = tk.Label(
            visual, text="AUTO • LOCAL INSTANT • MONITORING",
            font=self.font(7, "bold"), fg=MUTED, bg=PANEL
        )
        self.visual_footer.pack(pady=(0, 10))

        self._draw_visual_static()
        self.visual_canvas.bind("<Configure>", self._visual_resize)

    def _visual_resize(self, event=None):
        """Redraw the scene when the panel size changes so the animation always fills it."""
        if not hasattr(self, "visual_canvas"):
            return
        w = max(self.visual_canvas.winfo_width(), 1)
        h = max(self.visual_canvas.winfo_height(), 1)
        last = getattr(self, "_visual_size", None)
        if last == (w, h):
            return
        self._visual_size = (w, h)
        self.anim_last_sway = 0.0
        self.anim_last_breath = 0.0
        self._draw_visual_static()

    def _draw_visual_static(self):
        """Modern, calm-tech monitoring scene. Illustrative only; never a camera feed."""
        c = self.visual_canvas
        c.delete("all")
        w = max(c.winfo_width(), 700)
        h = max(c.winfo_height(), 230)

        card_w = max(190, min(218, w * 0.22))
        scene_left = 18
        scene_right = w - card_w - 18
        scene_w = max(scene_right - scene_left, 430)
        cx = scene_left + scene_w * 0.50
        cy = h * 0.64
        scale = min(scene_w / 505.0, h / 255.0)
        scale = max(0.84, min(scale, 1.42))

        crib_w = 455 * scale
        crib_h = 118 * scale
        left = cx - crib_w / 2
        right = cx + crib_w / 2
        top = cy - crib_h / 2
        bottom = cy + crib_h / 2

        # Ambient field: layered, subtle and spacious.
        for r, alpha_color in ((190, "#102A3D"), (150, "#14344A"), (112, "#183E55") ):
            c.create_oval(cx-r*scale, cy-r*0.46*scale,
                          cx+r*scale, cy+r*0.46*scale,
                          outline=alpha_color, width=1, tags="field")

        # Crib outer shell and soft inner frame.
        c.create_rectangle(left, top, right, bottom, outline=CYAN, width=3, tags="crib")
        inner = 10 * scale
        c.create_rectangle(left+inner, top+inner, right-inner, bottom-8*scale,
                           outline="#31546D", width=2, tags="crib")
        rail_gap = 30 * scale
        x = left + 28 * scale
        while x < right - 25 * scale:
            c.create_line(x, top+inner, x, bottom-8*scale,
                          fill="#3A617D", width=max(1, int(1.7*scale)), tags="crib")
            x += rail_gap
        c.create_rectangle(left+27*scale, bottom-39*scale, right-27*scale,
                           bottom-13*scale, fill="#DDE8EF", outline="", tags="crib")

        # Baby silhouette: intentionally simple and calm.
        head_r = 25 * scale
        head_x = cx - 35 * scale
        head_y = cy - 30 * scale
        c.create_oval(head_x-head_r, head_y-head_r, head_x+head_r, head_y+head_r,
                      fill="#F2C8A7", outline="", tags="baby_head")
        body_left = cx - 145 * scale
        body_top = cy - 7 * scale
        body_right = cx + 24 * scale
        body_bottom = cy + 46 * scale
        c.create_oval(body_left, body_top, body_right, body_bottom,
                      fill="#B7D5E3", outline="", tags="baby_body")
        c.create_oval(cx-78*scale, cy+1*scale, cx+38*scale, cy+37*scale,
                      fill="#D8EAF1", outline="", tags="blanket")
        c.create_line(cx-20*scale, cy+17*scale, cx+21*scale, cy+17*scale,
                      fill="#7FAFC3", width=max(1, int(2*scale)), tags="breath_line")

        # Monitoring node with a modern target/crosshair treatment.
        node_r = 24 * scale
        node_x = cx + 4 * scale
        node_y = max(40, top - 55 * scale)
        for rr, col in ((node_r+14*scale, "#183D53"), (node_r+7*scale, "#24546B")):
            c.create_oval(node_x-rr, node_y-rr, node_x+rr, node_y+rr,
                          outline=col, width=1, tags="sensor_halo")
        c.create_oval(node_x-node_r, node_y-node_r, node_x+node_r, node_y+node_r,
                      outline=CYAN, width=3, tags="sensor_node")
        c.create_line(node_x, node_y+node_r, node_x, top+2,
                      fill=CYAN, width=2, tags="sensor_line")
        c.create_line(node_x-7*scale, node_y, node_x+7*scale, node_y,
                      fill=CYAN, width=2, tags="sensor_cross")
        c.create_line(node_x, node_y-7*scale, node_x, node_y+7*scale,
                      fill=CYAN, width=2, tags="sensor_cross")

        # Compact state card so the visual scene owns the majority of the space.
        bx = w - card_w + 1
        by = 14
        br = w - 12
        bb = h - 14
        c.create_rectangle(bx, by, br, bb, fill="#0A1B2A", outline=BORDER, width=2,
                           tags="state_card")
        c.create_text(bx+13, by+15, anchor="w", text="LIVE SENSOR STATE",
                      fill=MUTED, font=("SF Pro Display", 7, "bold"))
        self.visual_state_text = c.create_text(bx+13, by+43, anchor="w", text="STABLE",
                                               fill=GREEN, font=("SF Pro Display", 12, "bold"))
        self.visual_temp = c.create_text(bx+13, by+76, anchor="w", text="TEMP  --",
                                         fill=TEXT, font=("SF Pro Display", 8, "bold"))
        self.visual_hum = c.create_text(bx+13, by+101, anchor="w", text="HUM   --",
                                        fill=TEXT, font=("SF Pro Display", 8, "bold"))
        self.visual_move = c.create_text(bx+13, by+126, anchor="w", text="MOVE  NONE",
                                         fill=TEXT, font=("SF Pro Display", 8, "bold"))
        self.visual_vib = c.create_text(bx+13, by+151, anchor="w", text="VIB   NONE",
                                        fill=TEXT, font=("SF Pro Display", 8, "bold"))
        c.create_text(bx+13, bb-15, anchor="w", text="LIVE • HARDWARE STATE",
                      fill=CYAN, font=("SF Pro Display", 7, "bold"))

        c.create_text(scene_left, h-13, anchor="w",
                      text="CAMERA-FREE • ILLUSTRATIVE SENSOR VISUAL",
                      fill=MUTED, font=("SF Pro Display", 7, "bold"))

        self._visual_scene = {
            "cx": cx, "cy": cy, "scale": scale, "node_x": node_x,
            "node_y": node_y, "node_r": node_r, "scene_left": scene_left,
            "scene_right": scene_right, "top": top, "bottom": bottom,
        }

    def animate_visual(self):
        """Calm-tech animation whose intensity follows the actual sensor state."""
        try:
            c = self.visual_canvas
            if not c.winfo_exists():
                return

            self.anim_phase += 1
            fever = bool(self.data.get("fever"))
            hum = self.data.get("humidity")
            movement = bool(self.data.get("movement"))
            vibration = bool(self.data.get("vibration"))

            if fever:
                color, state, footer, speed, strength = RED, "EMERGENCY", "AUTO • FEVER SIGNAL ACTIVE", 0.085, 0.68
            elif hum is not None and (hum < 30 or hum > 70):
                color, state, footer, speed, strength = ORANGE, "HUMIDITY WATCH", "AUTO • ENVIRONMENT WATCH", 0.045, 0.42
            elif movement or vibration:
                color, state, footer, speed, strength = YELLOW, "ACTIVITY WATCH", "AUTO • ACTIVITY DETECTED", 0.060, 0.50
            else:
                color, state, footer, speed, strength = GREEN, "STABLE", "AUTO • CALM MONITORING", 0.028, 0.24

            scene = getattr(self, "_visual_scene", {})
            cx = scene.get("cx", c.winfo_width()*0.4)
            cy = scene.get("cy", c.winfo_height()*0.6)
            scale = scene.get("scale", 1.0)
            node_x = scene.get("node_x", cx)
            node_y = scene.get("node_y", 55)
            node_r = scene.get("node_r", 25)

            # Gentle crib movement. It is deliberately subtle unless movement is real.
            sway_amp = (3.6 if fever else 2.6 if movement else 1.8 if (hum is not None and (hum < 30 or hum > 70)) else 1.2) * scale
            sway = sway_amp * math.sin(self.anim_phase * speed)
            dsway = sway - self.anim_last_sway
            if abs(dsway) > 0.01:
                for tag in ("crib", "baby_head", "baby_body", "blanket", "breath_line"):
                    c.move(tag, dsway, 0)
            self.anim_last_sway = sway

            # Slow visible breathing motion.
            breath_amp = (3.2 if fever else 2.6 if movement else 2.2 if (hum is not None and (hum < 30 or hum > 70)) else 1.8) * scale
            breath = breath_amp * math.sin(self.anim_phase * speed * 0.72)
            dbreath = breath - self.anim_last_breath
            if abs(dbreath) > 0.01:
                c.move("baby_body", 0, dbreath)
                c.move("blanket", 0, dbreath * 0.72)
                c.move("breath_line", 0, dbreath * 0.85)
                c.move("baby_head", 0, dbreath * 0.14)
            self.anim_last_breath = breath

            # Rebuild only dynamic layers. The static crib stays crisp.
            c.delete("pulse")
            phase = (self.anim_phase * speed * 1.35) % 1.0
            max_r = min(c.winfo_width()*0.26, c.winfo_height()*0.62)
            ring_count = 4 if fever else 3
            for i in range(ring_count):
                r = (20 + ((phase + i*0.30) % 1.0) * max_r * (0.86 if fever else 0.72)) * scale
                width = 2 if (fever and i == 0) else 1
                c.create_oval(node_x-r, node_y-r*0.78, node_x+r, node_y+r*0.78,
                              outline=color, width=width, tags="pulse")

            # A soft scan beam moves through the scene.
            scan_span = max(180, (scene.get("scene_right", c.winfo_width()-240) - scene.get("scene_left", 20)))
            scan_rate = 1.35 if fever else 0.80 if (movement or vibration) else 0.58 if (hum is not None and (hum < 30 or hum > 70)) else 0.42
            scan_x = scene.get("scene_left", 20) + ((self.anim_phase * scan_rate) % scan_span)
            c.create_line(scan_x, cy-82*scale, scan_x, cy+58*scale,
                          fill=color, width=(2 if fever else 1), tags="pulse")
            c.create_line(scan_x, cy-82*scale, scan_x, cy+58*scale,
                          fill=color, width=(5 if fever else 3), stipple="gray25", tags="pulse")

            # State-aware sensor node pulse.
            blink = (math.sin(self.anim_phase * speed * 2.6) + 1) / 2
            node_width = 2 + int(blink * (3 if fever else 1))
            c.itemconfig("sensor_node", outline=color, width=node_width)
            c.itemconfig("sensor_line", fill=color)
            c.itemconfig("sensor_cross", fill=color)

            # Small floating status labels give the scene a modern HUD feel.
            c.create_text(20, 16, anchor="w", text=f"●  {state}",
                          fill=color, font=("SF Pro Display", 8, "bold"), tags="pulse")
            c.create_text(c.winfo_width()-20, 16, anchor="e", text="LIVE • NO CAMERA",
                          fill=MUTED, font=("SF Pro Display", 7, "bold"), tags="pulse")
            c.create_text(node_x, node_y, text="!" if fever else "✓",
                          fill=color, font=("SF Pro Display", 16, "bold"), tags="pulse")

            if hasattr(self, "visual_state_text"):
                c.itemconfig(self.visual_state_text, text=state, fill=color)
                c.itemconfig(self.visual_temp,
                             text=("TEMP  --" if self.data["ambient_temp"] is None
                                   else f"TEMP  {self.data['ambient_temp']:.1f}°C"))
                c.itemconfig(self.visual_hum,
                             text=("HUM   --" if hum is None else f"HUM   {hum:.0f}%"))
                c.itemconfig(self.visual_move,
                             text=f"MOVE  {'DETECTED' if movement else 'NONE'}")
                c.itemconfig(self.visual_vib,
                             text=f"VIB   {'DETECTED' if vibration else 'NONE'}")

            self.visual_footer.config(text=footer, fg=color)
        except Exception as exc:
            print("visual animation:", exc)

        self.anim_job = self.root.after(70, self.animate_visual)

    # ----------------------------- Sensors -----------------------------

    def _build_sensor_matrix(self):
        self._build_top_hero()

        panel = self.panel(
            self.content, "LIVE SENSOR MATRIX", "Updated every second"
        )
        panel.pack(fill="x", pady=(0, 14))

        cards = tk.Frame(panel, bg=PANEL)
        cards.pack(fill="x", padx=12, pady=(0, 14))

        self.temp_val, self.temp_state = self.metric_card(
            cards, "DHT22 AMBIENT TEMPERATURE", "--", "°C", CYAN, 0
        )
        self.hum_val, self.hum_state = self.metric_card(
            cards, "DHT22 HUMIDITY", "--", "%", CYAN, 1
        )
        self.fever_val, self.fever_state = self.metric_card(
            cards, "BABY FEVER STATUS", "NO", "", RED, 2
        )
        self.move_val, self.move_state = self.metric_card(
            cards, "MOVEMENT", "NONE", "", GREEN, 3
        )
        self.vib_val, self.vib_state = self.metric_card(
            cards, "VIBRATION", "NONE", "", PURPLE, 4
        )

    def metric_card(self, parent, title, value, unit, accent, col):
        card = tk.Frame(
            parent, bg=CARD,
            highlightbackground=BORDER, highlightthickness=1
        )
        card.grid(row=0, column=col, sticky="nsew", padx=4)
        parent.columnconfigure(col, weight=1)
        tk.Frame(card, bg=accent, height=4).pack(fill="x")
        tk.Label(
            card, text=title, font=self.font(7, "bold"),
            fg=MUTED, bg=CARD
        ).pack(anchor="w", padx=12, pady=(10, 3))
        row = tk.Frame(card, bg=CARD)
        row.pack(anchor="w", padx=12)
        val = tk.Label(
            row, text=value, font=self.font(21, "bold"),
            fg=TEXT, bg=CARD
        )
        val.pack(side="left")
        if unit:
            tk.Label(
                row, text=unit, font=self.font(8, "bold"),
                fg=MUTED, bg=CARD
            ).pack(side="left", padx=(5, 0), pady=(8, 0))
        state = tk.Label(
            card, text="NORMAL", font=self.font(7, "bold"),
            fg=GREEN, bg="#092A25", padx=7, pady=4
        )
        state.pack(anchor="w", padx=12, pady=(6, 11))
        return val, state

    # ----------------------------- Copilot -----------------------------

    def _build_copilot(self):
        panel = self.panel(
            self.content,
            "✦ AI CARE COPILOT",
            "Sensor-grounded caregiver guidance"
        )
        panel.pack(fill="x", pady=(0, 14))

        split = tk.Frame(panel, bg=PANEL)
        split.pack(fill="x", padx=12, pady=(0, 14))

        chatbox = tk.Frame(
            split, bg="#07131F",
            highlightbackground=BORDER, highlightthickness=1
        )
        chatbox.pack(side="left", fill="both", expand=True, padx=(0, 7))

        top = tk.Frame(chatbox, bg="#0A1D2C")
        top.pack(fill="x")
        tk.Label(
            top, text="NEOGUARD COPILOT",
            font=self.font(8, "bold"), fg=CYAN, bg="#0A1D2C"
        ).pack(side="left", padx=13, pady=9)
        tk.Label(
            top, text="AI",
            font=self.font(7, "bold"), fg=BG, bg=CYAN,
            padx=5, pady=2
        ).pack(side="right", padx=13)

        self.chat = tk.Text(
            chatbox, height=10, bg="#07131F", fg=TEXT,
            insertbackground=TEXT, relief="flat", bd=0,
            wrap="word", font=self.font(8), padx=12, pady=10
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.configure(state="disabled")

        quick = tk.Frame(chatbox, bg="#07131F")
        quick.pack(fill="x", padx=8, pady=(0, 7))
        quicks = [
            ("What should I do?", "What should I do right now?"),
            ("What should I avoid?", "What should I avoid right now?"),
            ("Explain temperature", "Explain the current temperature."),
            ("Explain activity", "What does the movement/vibration mean?"),
        ]
        for label, question in quicks:
            tk.Button(
                quick, text=label,
                command=lambda q=question: self.ask_ai(q),
                font=self.font(7, "bold"), fg=TEXT, bg=CARD2,
                activebackground="#214863", activeforeground=CYAN,
                relief="flat", bd=0, padx=8, pady=6, cursor="hand2"
            ).pack(side="left", padx=2)

        input_row = tk.Frame(chatbox, bg="#07131F")
        input_row.pack(fill="x", padx=8, pady=(0, 10))
        self.chat_entry = tk.Entry(
            input_row, bg=CARD, fg=TEXT,
            insertbackground=TEXT, relief="flat",
            font=self.font(8)
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.chat_entry.bind("<Return>", lambda e: self.ask_ai())
        tk.Button(
            input_row, text="SEND  →", command=self.ask_ai,
            font=self.font(7, "bold"), fg=BG, bg=CYAN,
            activebackground=CYAN2, relief="flat", bd=0,
            padx=14, pady=8, cursor="hand2"
        ).pack(side="left", padx=(6, 0))

        guide = tk.Frame(
            split, bg=CARD, width=335,
            highlightbackground=BORDER, highlightthickness=1
        )
        guide.pack(side="right", fill="y")
        guide.pack_propagate(False)

        tk.Label(
            guide, text="RIGHT NOW", font=self.font(7, "bold"),
            fg=CYAN, bg=CARD
        ).pack(anchor="w", padx=14, pady=(14, 2))
        self.guide_title = tk.Label(
            guide, text="STABLE", font=self.font(15, "bold"),
            fg=GREEN, bg=CARD
        )
        self.guide_title.pack(anchor="w", padx=14)

        self.guide_do = tk.Label(
            guide, text="WHAT TO DO\n• Continue normal monitoring.",
            font=self.font(8), fg=GREEN, bg=CARD,
            justify="left", anchor="w", wraplength=300
        )
        self.guide_do.pack(fill="x", padx=14, pady=(10, 7))

        self.guide_avoid = tk.Label(
            guide, text="WHAT TO AVOID\n• Do not ignore persistent changes.",
            font=self.font(8), fg=YELLOW, bg=CARD,
            justify="left", anchor="w", wraplength=300
        )
        self.guide_avoid.pack(fill="x", padx=14)

    # ----------------------------- Trends -----------------------------

    def _build_trends(self):
        panel = self.panel(
            self.content, "⌁ LIVE TRENDS", "Recent DHT22 history • parent-friendly view"
        )
        panel.pack(fill="x", pady=(0, 14))

        # A clean two-column trend view is easier to read than dual Y-axes.
        holder = tk.Frame(panel, bg=PANEL)
        holder.pack(fill="x", padx=12, pady=(0, 12))

        self.figure = Figure(figsize=(11.8, 3.7), dpi=100, facecolor=PANEL)
        self.ax = self.figure.add_subplot(121)
        self.ax_h = self.figure.add_subplot(122)
        self.chart = FigureCanvasTkAgg(self.figure, master=holder)
        chart_widget = self.chart.get_tk_widget()
        chart_widget.configure(height=330, highlightthickness=0)
        chart_widget.pack(fill="x")

    # ----------------------------- Alerts / actuators -----------------------------

    def _build_alerts(self):
        panel = self.panel(
            self.content, "⚠ ALERT INTELLIGENCE",
            "Priority queue • newest first"
        )
        panel.pack(fill="x", pady=(0, 14))
        self.alert_text = tk.Text(
            panel, height=7, bg="#07131F", fg=TEXT,
            relief="flat", bd=0, font=("Menlo", 8),
            padx=10, pady=8
        )
        self.alert_text.pack(fill="x", padx=12, pady=(0, 12))
        self.alert_text.configure(state="disabled")

    def _build_actuators(self):
        panel = self.panel(
            self.content, "⚙ ACTUATOR STATE • LIVE HARDWARE",
            "ESP32 / Flask synchronized state"
        )
        panel.pack(fill="x", pady=(0, 14))
        cards = tk.Frame(panel, bg=PANEL)
        cards.pack(fill="x", padx=12, pady=(0, 12))

        self.led_state = self.actuator_card(cards, "LED", 0, RED)
        self.fan_state = self.actuator_card(cards, "FAN", 1, GREEN)
        self.buzzer_state = self.actuator_card(cards, "BUZZER", 2, RED)
        self.emergency_state = self.actuator_card(cards, "EMERGENCY", 3, RED)

    def actuator_card(self, parent, title, col, accent):
        card = tk.Frame(
            parent, bg=CARD,
            highlightbackground=BORDER, highlightthickness=1
        )
        card.grid(row=0, column=col, sticky="nsew", padx=4)
        parent.columnconfigure(col, weight=1)
        tk.Label(
            card, text=title, font=self.font(7, "bold"),
            fg=MUTED, bg=CARD
        ).pack(anchor="w", padx=13, pady=(11, 3))
        state = tk.Label(
            card, text="OFF", font=self.font(19, "bold"),
            fg=MUTED, bg=CARD
        )
        state.pack(anchor="w", padx=13, pady=(0, 12))
        return state

    # ----------------------------- Activity -----------------------------

    def _build_activity(self):
        panel = self.panel(
            self.content, "▦ SYSTEM ACTIVITY", "Recent events"
        )
        panel.pack(fill="x", pady=(0, 14))
        self.events = tk.Text(
            panel, height=8, bg="#07131F", fg=MUTED,
            relief="flat", bd=0, font=("Menlo", 8),
            padx=10, pady=8
        )
        self.events.pack(fill="x", padx=12, pady=(0, 12))
        self.events.configure(state="disabled")

        tk.Label(
            panel,
            text="DSA layer: Queue • Circular Buffer • Priority Queue • Stack • Hash Table • Graph • Search/Sort",
            font=self.font(7, "bold"), fg=PURPLE, bg=PANEL
        ).pack(anchor="w", padx=12, pady=(0, 12))

    # ----------------------------- DB reads -----------------------------

    def latest_rows(self):
        conn = self.db()
        rows = conn.execute("""
            SELECT sensor_name, value, unit, timestamp
            FROM sensor_readings
            WHERE id IN (
                SELECT MAX(id)
                FROM sensor_readings
                GROUP BY sensor_name
            )
        """).fetchall()
        conn.close()
        return rows

    def latest_value(self, names):
        conn = self.db()
        marks = ",".join("?" for _ in names)
        row = conn.execute(
            f"""
            SELECT sensor_name, value, unit, timestamp
            FROM sensor_readings
            WHERE sensor_name IN ({marks})
            ORDER BY id DESC LIMIT 1
            """,
            list(names)
        ).fetchone()
        conn.close()
        return row

    def latest_emergency(self):
        conn = self.db()
        row = conn.execute("""
            SELECT description, timestamp
            FROM events
            WHERE event_type='EMERGENCY'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        conn.close()
        return row

    def read_actuators(self):
        conn = self.db()
        rows = conn.execute("""
            SELECT actuator_name, state
            FROM actuator_logs
            ORDER BY id DESC
        """).fetchall()
        latest = {}
        for r in rows:
            latest.setdefault(r["actuator_name"], r["state"])

        fever = self.latest_value(["FEVER", "NTC_FEVER", "BABY_FEVER"])
        conn.close()

        fever_on = bool(fever and float(fever["value"]) == 1)

        return {
            "LED": "ON" if fever_on else latest.get("LED", "OFF"),
            "FAN": latest.get("FAN", "OFF"),
            "BUZZER": "ON" if fever_on else latest.get("BUZZER", "OFF"),
            "EMERGENCY": "ACTIVE" if fever_on else "INACTIVE",
        }

    def read_history(self):
        conn = self.db()
        rows = conn.execute("""
            SELECT sensor_name, value, timestamp
            FROM sensor_readings
            WHERE valid=1
            ORDER BY id DESC LIMIT 100
        """).fetchall()
        conn.close()
        return rows

    # ----------------------------- Refresh -----------------------------

    def refresh(self):
        try:
            rows = self.latest_rows()
            d = dict(self.data)

            for r in rows:
                name = r["sensor_name"]
                value = float(r["value"])

                if name in {
                    "DHT_TEMP", "DHT22_TEMP",
                    "DHT22_TEMPERATURE", "AMBIENT_TEMPERATURE"
                }:
                    d["ambient_temp"] = value
                elif name in {"DHT11", "DHT22", "DHT22_HUMIDITY", "HUMIDITY"}:
                    d["humidity"] = value
                elif name in {"FEVER", "NTC_FEVER", "BABY_FEVER"}:
                    d["fever"] = value == 1
                elif name in {"ITG_MPU", "MPU6050", "MOVEMENT"}:
                    d["movement"] = value != 0
                elif name in {"SW420", "VIBRATION", "MPU_VIBRATION"}:
                    d["vibration"] = value != 0

            d["emergency"] = d["fever"]
            acts = self.read_actuators()
            d.update({
                "led": acts["LED"],
                "fan": acts["FAN"],
                "buzzer": acts["BUZZER"],
            })
            self.data = d

            self.update_ai_badge()
            self.update_status()
            self.update_sensors()
            self.update_copilot_state()
            self.update_chart()
            self.update_alerts()
            self.update_actuators(acts)
            self.update_events()

            self.db_state.config(
                text="LIVE • DB UPDATED",
                fg=GREEN if self.data["ambient_temp"] is not None else YELLOW
            )
        except Exception as exc:
            print("NeoGuard refresh:", exc)
            self.db_state.config(text="DB READ ERROR", fg=RED)

    def live_update(self):
        self.refresh()
        self.root.after(1000, self.live_update)

    def update_ai_badge(self):
        provider = getattr(self.ai, "provider", "GROQ")
        online = getattr(self.ai, "online", False)
        if online:
            self.set_badge(
                self.ai_badge,
                "GROQ CLOUD • NEOGUARD AI",
                CYAN, "#10293B"
            )
        else:
            self.set_badge(
                self.ai_badge,
                f"{provider} • CHECK CONNECTION",
                YELLOW, "#342B10"
            )

    def update_status(self):
        d = self.data
        hum = d["humidity"]

        if d["fever"]:
            title = "EMERGENCY MODE"
            color = RED
            detail = "FEVER DETECTED • NTC digital signal active • buzzer/LED ON • emergency state active."
            score = 20
            guide_title = "EMERGENCY MODE"
        elif hum is not None and (hum < 30 or hum > 70):
            title = "HUMIDITY WATCH"
            color = YELLOW
            detail = f"Ambient humidity is {hum:.0f}%, outside the configured 30–70% monitoring band."
            score = 84
            guide_title = "HUMIDITY WATCH"
        elif d["movement"] or d["vibration"]:
            title = "ACTIVITY WATCH"
            color = ORANGE
            detail = "Movement or vibration has been detected by the MPU6050."
            score = 72
            guide_title = "ACTIVITY WATCH"
        else:
            title = "STABLE"
            color = GREEN
            detail = "Configured sensor signals are currently stable."
            score = 96
            guide_title = "STABLE"

        self.condition.config(text=title, fg=color)
        self.condition_detail.config(text=detail)
        self.conf_text.config(
            text=f"System confidence / stability indicator: {score}%"
        )
        self.conf_bar.update_idletasks()
        width = max(self.conf_bar.winfo_width(), 400)
        self.conf_bar.coords(
            self.conf_rect, 0, 0, width * score / 100, 12
        )
        self.conf_bar.itemconfig(
            self.conf_rect, fill=RED if d["fever"] else CYAN
        )
        self.guide_title.config(text=guide_title, fg=color)

        if d["fever"]:
            self.guide_do.config(
                text="WHAT TO DO\n"
                     "• Check the physical NeoGuard sensor connections.\n"
                     "• Follow the project's emergency response procedure.\n"
                     "• Confirm the fever indication with an appropriate clinical thermometer.\n"
                     "• Seek qualified clinical help when required."
            )
            self.guide_avoid.config(
                text="WHAT TO AVOID\n"
                     "• Do not interpret the NTC module as an exact temperature sensor.\n"
                     "• Do not rely on the dashboard alone for clinical decisions.\n"
                     "• Do not ignore a persistent fever indication."
            )
        elif hum is not None and (hum < 30 or hum > 70):
            self.guide_do.config(
                text="WHAT TO DO\n"
                     "• Check room ventilation and humidity conditions.\n"
                     "• Continue normal monitoring."
            )
            self.guide_avoid.config(
                text="WHAT TO AVOID\n"
                     "• Do not interpret a humidity warning as a fever diagnosis."
            )
        else:
            self.guide_do.config(
                text="WHAT TO DO\n• Continue normal monitoring."
            )
            self.guide_avoid.config(
                text="WHAT TO AVOID\n• Do not ignore persistent sensor changes."
            )

    def update_sensors(self):
        d = self.data
        self.temp_val.config(
            text="--" if d["ambient_temp"] is None else f"{d['ambient_temp']:.1f}"
        )
        self.hum_val.config(
            text="--" if d["humidity"] is None else f"{d['humidity']:.0f}"
        )
        self.fever_val.config(text="YES" if d["fever"] else "NO")
        self.move_val.config(text="DETECTED" if d["movement"] else "NONE")
        self.vib_val.config(text="DETECTED" if d["vibration"] else "NONE")

        if d["fever"]:
            self.set_badge(self.fever_state, "EMERGENCY", RED, "#3B1220")
        else:
            self.set_badge(self.fever_state, "NORMAL", GREEN, "#092A25")

        if d["humidity"] is None:
            self.set_badge(self.hum_state, "NO DATA", MUTED, PANEL2)
        elif 30 <= d["humidity"] <= 70:
            self.set_badge(self.hum_state, "NORMAL", GREEN, "#092A25")
        else:
            self.set_badge(self.hum_state, "WATCH", YELLOW, "#352C0E")

        self.set_badge(
            self.temp_state, "DHT22 LIVE", CYAN, "#0B2A38"
        )
        self.set_badge(
            self.move_state,
            "DETECTED" if d["movement"] else "NONE",
            ORANGE if d["movement"] else GREEN,
            "#33200D" if d["movement"] else "#092A25"
        )
        self.set_badge(
            self.vib_state,
            "DETECTED" if d["vibration"] else "NONE",
            PURPLE if d["vibration"] else GREEN,
            "#251A3B" if d["vibration"] else "#092A25"
        )

    def update_copilot_state(self):
        # The visual panel is driven deterministically by the live hardware state.
        # Groq is used for explanations/chat, not as the safety-state source.
        pass

    def update_chart(self):
        """Modern parent-friendly trends: one clear story per panel, minimal clutter."""
        conn = self.db()
        temp_rows = conn.execute("""
            SELECT value, timestamp FROM sensor_readings
            WHERE valid=1 AND sensor_name IN
            ('DHT_TEMP','DHT22_TEMP','DHT22_TEMPERATURE','AMBIENT_TEMPERATURE')
            ORDER BY id DESC LIMIT 30
        """).fetchall()
        hum_rows = conn.execute("""
            SELECT value, timestamp FROM sensor_readings
            WHERE valid=1 AND sensor_name IN
            ('DHT11','DHT22','DHT22_HUMIDITY','HUMIDITY')
            ORDER BY id DESC LIMIT 30
        """).fetchall()
        conn.close()

        temp = list(reversed([(float(r["value"]), r["timestamp"]) for r in temp_rows]))
        hum = list(reversed([(float(r["value"]), r["timestamp"]) for r in hum_rows]))

        for ax in (self.ax, self.ax_h):
            ax.clear()
            ax.set_facecolor("#07131F")
            ax.grid(axis="y", alpha=0.075, color="#8AA0AF", linewidth=0.8)
            ax.tick_params(colors=MUTED, labelsize=7, length=0)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
                spine.set_linewidth(0.8)
            ax.set_xticks([])
            ax.margins(x=0.025)
            ax.set_xlabel("RECENT READINGS  →", color=MUTED, fontsize=6.5, labelpad=7)

        def trend_status(values, watch=None):
            if not values:
                return "NO DATA", MUTED
            change = values[-1] - values[0]
            if watch and (values[-1] < watch[0] or values[-1] > watch[1]):
                return "WATCH", YELLOW
            if abs(change) < max(0.15, (max(values)-min(values))*0.35):
                return "STABLE", GREEN
            return ("RISING" if change > 0 else "FALLING"), CYAN

        # Temperature: no invented clinical safe band; it is explicitly ambient.
        if temp:
            tx = list(range(len(temp)))
            ty = [v for v, _ in temp]
            latest = ty[-1]
            lo_data, hi_data = min(ty), max(ty)
            span = max(0.6, hi_data - lo_data)
            pad = max(0.28, span * 0.35)
            lo, hi = lo_data - pad, hi_data + pad
            if hi - lo < 1.5:
                mid = (hi + lo) / 2
                lo, hi = mid - 0.75, mid + 0.75
            status, status_color = trend_status(ty)
            ax = self.ax
            ax.plot(tx, ty, linewidth=2.5, color=RED, solid_capstyle="round", zorder=3)
            ax.scatter([tx[-1]], [latest], s=30, color=RED, zorder=4)
            ax.fill_between(tx, ty, lo, alpha=0.045, color=RED, zorder=1)
            ax.set_ylim(lo, hi)
            ax.set_ylabel("AMBIENT °C", color=RED, fontsize=7.5, fontweight="bold", labelpad=6)
            ax.set_title("ROOM TEMPERATURE", loc="left", color=TEXT,
                         fontsize=9.5, fontweight="bold", pad=10)
            ax.text(0.98, 1.045, f"{latest:.1f}°C  NOW", transform=ax.transAxes,
                    ha="right", va="bottom", color=RED, fontsize=8.5, fontweight="bold")
            ax.text(0.02, 1.045, f"DHT22 • {status}", transform=ax.transAxes,
                    ha="left", va="bottom", color=status_color, fontsize=6.5, fontweight="bold")
            ax.text(0.02, 0.05, "Ambient room reading — not baby body temperature",
                    transform=ax.transAxes, ha="left", va="bottom", color=MUTED,
                    fontsize=6.2)

        # Humidity: clearly show the project's configured 30–70% monitoring band.
        if hum:
            hx = list(range(len(hum)))
            hy = [v for v, _ in hum]
            latest = hy[-1]
            status, status_color = trend_status(hy, (30, 70))
            ax = self.ax_h
            ax.axhspan(30, 70, color=GREEN, alpha=0.045, zorder=0)
            ax.axhline(70, color=YELLOW, linewidth=1.0, alpha=0.7, linestyle="--")
            ax.axhline(30, color=YELLOW, linewidth=1.0, alpha=0.7, linestyle="--")
            ax.plot(hx, hy, linewidth=2.5, color=CYAN, solid_capstyle="round", zorder=3)
            ax.scatter([hx[-1]], [latest], s=30, color=CYAN, zorder=4)
            lo_data, hi_data = min(min(hy), 30), max(max(hy), 70)
            lo, hi = max(0, lo_data - 5), min(100, hi_data + 5)
            ax.set_ylim(lo, hi)
            ax.set_ylabel("HUMIDITY %", color=CYAN, fontsize=7.5, fontweight="bold", labelpad=6)
            ax.set_title("ROOM HUMIDITY", loc="left", color=TEXT,
                         fontsize=9.5, fontweight="bold", pad=10)
            ax.text(0.98, 1.045, f"{latest:.0f}%  NOW", transform=ax.transAxes,
                    ha="right", va="bottom", color=CYAN, fontsize=8.5, fontweight="bold")
            ax.text(0.02, 1.045, f"DHT22 • {status}", transform=ax.transAxes,
                    ha="left", va="bottom", color=status_color, fontsize=6.5, fontweight="bold")
            ax.text(0.02, 0.92, "● COMFORT BAND 30–70%", transform=ax.transAxes,
                    ha="left", va="top", color=GREEN, fontsize=6.2, fontweight="bold")
            ax.text(0.98, 0.05, "WATCH OUTSIDE BAND", transform=ax.transAxes,
                    ha="right", va="bottom", color=YELLOW, fontsize=6.2, fontweight="bold")

        self.figure.subplots_adjust(left=0.055, right=0.985, top=0.82, bottom=0.17,
                                    wspace=0.16)
        self.chart.draw_idle()

    def update_alerts(self):
        conn = self.db()
        rows = conn.execute("""
            SELECT severity, message, timestamp
            FROM alerts
            ORDER BY id DESC LIMIT 10
        """).fetchall()
        conn.close()

        self.alert_text.configure(state="normal")
        self.alert_text.delete("1.0", "end")
        if not rows:
            self.alert_text.insert("end", "No alerts recorded.\n")
        else:
            for r in rows:
                self.alert_text.insert(
                    "end",
                    f"[{r['severity']}] {r['message']}  •  {r['timestamp']}\n"
                )
        self.alert_text.configure(state="disabled")

    def update_actuators(self, acts):
        mapping = [
            ("LED", self.led_state, RED),
            ("FAN", self.fan_state, GREEN),
            ("BUZZER", self.buzzer_state, RED),
            ("EMERGENCY", self.emergency_state, RED),
        ]
        for key, widget, color in mapping:
            value = acts[key]
            active = value in {"ON", "ACTIVE"}
            widget.config(
                text=value,
                fg=color if active else MUTED
            )

    def update_events(self):
        conn = self.db()
        rows = conn.execute("""
            SELECT event_type, description, timestamp
            FROM events
            ORDER BY id DESC LIMIT 10
        """).fetchall()
        conn.close()

        self.events.configure(state="normal")
        self.events.delete("1.0", "end")
        for r in rows:
            self.events.insert(
                "end",
                f"{r['timestamp']}  {r['event_type']:<12}  {r['description']}\n"
            )
        self.events.configure(state="disabled")

    # ----------------------------- Chat -----------------------------

    def _append_chat(self, speaker, message):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{speaker}\n", ("speaker",))
        self.chat.insert("end", message + "\n\n")
        self.chat.tag_configure(
            "speaker", foreground=CYAN,
            font=self.font(7, "bold")
        )
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def ask_ai(self, question=None):
        if self.chat_busy:
            return

        q = question or self.chat_entry.get().strip()
        if not q:
            return

        self.chat_entry.delete(0, "end")
        self.chat_busy = True
        self._append_chat("YOU", q)
        self._append_chat("NEOGUARD COPILOT", "Reading the live sensor state…")

        snapshot = {
            "temperature": self.data["ambient_temp"],
            "humidity": self.data["humidity"],
            "fever": self.data["fever"],
            "movement": self.data["movement"],
            "vibration": self.data["vibration"],
            "emergency": self.data["emergency"],
        }

        def worker():
            try:
                answer = self.ai.ai_chat(q, snapshot)
            except Exception as exc:
                answer = f"I couldn't complete that AI request: {exc}"
            self.root.after(0, lambda: self.finish_ai(answer))

        threading.Thread(target=worker, daemon=True).start()

    def finish_ai(self, answer):
        self.chat_busy = False
        self.chat.configure(state="normal")
        content = self.chat.get("1.0", "end")
        marker = "NEOGUARD COPILOT\nReading the live sensor state…\n\n"
        if marker in content:
            content = content.rsplit(marker, 1)[0]
            self.chat.delete("1.0", "end")
            self.chat.insert("end", content)
        self.chat.configure(state="disabled")
        self._append_chat("NEOGUARD COPILOT", answer)

    # ----------------------------- Navigation -----------------------------

    def scroll_top(self):
        self.scroll_canvas.yview_moveto(0)

    def focus_chat(self):
        self.scroll_canvas.yview_moveto(0.25)

    def focus_trends(self):
        self.scroll_canvas.yview_moveto(0.50)

    def focus_alerts(self):
        self.scroll_canvas.yview_moveto(0.65)

    def focus_actuators(self):
        self.scroll_canvas.yview_moveto(0.78)

    # ----------------------------- Test states -----------------------------

    def test_normal(self):
        self._set_demo_state(False, False, False)

    def test_critical(self):
        self._set_demo_state(True, self.data["movement"], self.data["vibration"])

    def test_recovery(self):
        self._set_demo_state(False, False, False)

    def _set_demo_state(self, fever, movement, vibration):
        # UI-only test mode. It does not alter ESP32 hardware or the database.
        self.data["fever"] = fever
        self.data["emergency"] = fever
        self.data["movement"] = movement
        self.data["vibration"] = vibration
        self.data["led"] = "ON" if fever else "OFF"
        self.data["buzzer"] = "ON" if fever else "OFF"
        self.update_status()
        self.update_sensors()
        self.update_actuators({
            "LED": self.data["led"],
            "FAN": "OFF",
            "BUZZER": self.data["buzzer"],
            "EMERGENCY": "ACTIVE" if fever else "INACTIVE",
        })

    # ----------------------------- Simulation / DSA -----------------------------

    def run_simulation(self):
        try:
            from backend.services.simulation_engine import SimulationEngine
            self.sim_btn.config(state="disabled", text="RUNNING…")
            self.sim_status.config(text="RUNNING • 5 cycles", fg=ORANGE)

            def worker():
                try:
                    SimulationEngine().run(cycles=5, delay=1)
                finally:
                    self.root.after(0, self.simulation_finished)

            threading.Thread(target=worker, daemon=True).start()
        except Exception as exc:
            self.sim_status.config(text=f"ERROR: {exc}", fg=RED)
            self.sim_btn.config(state="normal", text="▶  RUN 5 SCENARIOS")

    def simulation_finished(self):
        self.sim_btn.config(state="normal", text="▶  RUN 5 SCENARIOS")
        self.sim_status.config(text="COMPLETE • 5 cycles", fg=GREEN)
        self.refresh()

    def open_dsa(self):
        """Show and run the four DSA concepts required for the DSA midterm."""
        win = tk.Toplevel(self.root)
        win.title("NEOGUARD • DSA Midterm Demonstration")
        win.geometry("980x700")
        win.minsize(800, 580)
        win.configure(bg=BG)

        tk.Label(
            win, text="DSA MIDTERM • LIVE DEMONSTRATION",
            font=self.font(20, "bold"), fg=CYAN, bg=BG
        ).pack(anchor="w", padx=25, pady=(22, 4))
        tk.Label(
            win,
            text="These structures run on NeoGuard's latest stored sensor readings.",
            font=self.font(10), fg=MUTED, bg=BG
        ).pack(anchor="w", padx=25, pady=(0, 14))

        rows = [
            ("CLASSES", "Sensor / SensorReadingLinkedList", "Sensor readings are represented as objects."),
            ("INHERITANCE", "TemperatureSensor, HumiditySensor, StateSensor → Sensor", "Subclasses inherit shared fields and override status()."),
            ("RECURSION", "recursive_count() / recursive_find()", "Recursive functions process the readings with base cases."),
            ("LINKED LIST", "Node → next → next", "Append, traverse, search and delete operations are implemented."),
            ("EXISTING DSA", "Queue / Stack / Graph / Sorting", "The existing NeoGuard DSA modules remain available."),
        ]
        table = tk.Frame(win, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        table.pack(fill="x", padx=25, pady=(0, 12))
        for i, (a, b, c) in enumerate(rows):
            tk.Label(table, text=a, font=self.font(9, "bold"), fg=PURPLE, bg=PANEL, width=16, anchor="w").grid(row=i, column=0, sticky="w", padx=14, pady=10)
            tk.Label(table, text=b, font=self.font(9, "bold"), fg=CYAN, bg=PANEL, anchor="w", wraplength=360, justify="left").grid(row=i, column=1, sticky="w", padx=12, pady=10)
            tk.Label(table, text=c, font=self.font(9), fg=TEXT, bg=PANEL, anchor="w", wraplength=350, justify="left").grid(row=i, column=2, sticky="ew", padx=12, pady=10)
        table.columnconfigure(2, weight=1)

        output = tk.Text(win, height=12, bg="#071522", fg=TEXT, insertbackground=TEXT,
                         font=("Menlo", 10), relief="flat", wrap="word")
        output.pack(fill="both", expand=True, padx=25, pady=(0, 12))
        output.insert("end", "Click RUN LIVE DSA DEMO to process the latest sensor readings stored in NeoGuard's database.\n")
        output.configure(state="disabled")

        def run_demo():
            try:
                from backend.dsa.midterm_structures import run_midterm_demo
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("""SELECT sensor_name, value, unit, timestamp FROM sensor_readings
                               WHERE id IN (SELECT MAX(id) FROM sensor_readings GROUP BY sensor_name)
                               ORDER BY sensor_name ASC""")
                sensor_rows = [dict(row) for row in cur.fetchall()]
                conn.close()
                result = run_midterm_demo(sensor_rows)
                lines = ["LIVE DSA DEMO RESULT", "=" * 48,
                         f"Database readings processed: {result['recursive_count']}",
                         f"Linked-list size: {result['linked_list']['size']}",
                         "", "OBJECTS (classes + inheritance):"]
                for item in result["readings"]:
                    lines.append(f" • {item['name']}: {item['value']} {item['unit']} | {item['status']} | object={item['class']}")
                lines += ["", "RECURSION:", f" • recursive_count() returned {result['recursive_count']}",
                          f" • recursive_find(DHT_TEMP) found: {result['recursive_find_temperature'] is not None}",
                          "", "LINKED LIST TRAVERSAL:"]
                lines.extend(f" • node {i + 1}: {item['name']} = {item['value']} {item['unit']}" for i, item in enumerate(result['readings']))
                if not sensor_rows:
                    lines += ["", "No readings are stored yet. Connect the ESP32 or run the simulation, then run this demo again."]
                output.configure(state="normal")
                output.delete("1.0", "end")
                output.insert("end", "\n".join(lines))
                output.configure(state="disabled")
            except Exception as exc:
                output.configure(state="normal")
                output.delete("1.0", "end")
                output.insert("end", f"DSA demo error: {exc}\nCheck that the project is launched from its root folder.")
                output.configure(state="disabled")

        controls = tk.Frame(win, bg=BG)
        controls.pack(fill="x", padx=25, pady=(0, 20))
        tk.Button(controls, text="▶  RUN LIVE DSA DEMO", command=run_demo,
                  font=self.font(10, "bold"), bg=CYAN, fg="#03121D",
                  activebackground=CYAN2, relief="flat", padx=18, pady=10,
                  cursor="hand2").pack(side="left")
        tk.Label(controls, text="Educational prototype • not a certified medical device",
                 font=self.font(8), fg=MUTED, bg=BG).pack(side="right", padx=4)


if __name__ == "__main__":
    root = tk.Tk()
    app = NeoGuardPRO(root)
    root.mainloop()

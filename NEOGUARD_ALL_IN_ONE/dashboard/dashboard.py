"""NeoGuard launcher. Run with: python3 dashboard.py"""
from dashboard_pro import NeoGuardDashboard
import tkinter as tk

if __name__ == "__main__":
    root = tk.Tk()
    app = NeoGuardDashboard(root)
    root.mainloop()

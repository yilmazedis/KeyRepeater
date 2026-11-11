"""
Key Repeater - presses up to 5 keyboard keys repeatedly, each at its own
millisecond interval (Windows).

Uses the same technique as pygta5's keys.py: ctypes + SendInput with
KEYEVENTF_SCANCODE, so the key presses are seen by DirectInput games as well
as normal applications.

Global hotkey (default F6) starts/stops repeating from any window.
"""

import ctypes
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

IS_WINDOWS = sys.platform == "win32"

# --------------------------------------------------------------------------
# SendInput structures (same layout as pygta5 keys.py, 32/64-bit safe)
# --------------------------------------------------------------------------
ULONG_PTR = ctypes.c_size_t


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]


INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    winmm = ctypes.WinDLL("winmm")
    user32.SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(Input), ctypes.c_int)
    user32.SendInput.restype = ctypes.c_uint
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
else:
    # Preview mode for macOS/Linux: the UI works but no keys are sent.
    class _NoOp:
        def __getattr__(self, name):
            return lambda *args: 0

    user32 = winmm = _NoOp()


def _send_key(scan, extended, key_up):
    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if key_up:
        flags |= KEYEVENTF_KEYUP
    inp = Input(type=INPUT_KEYBOARD)
    inp.ii.ki = KeyBdInput(0, scan, flags, 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def press_key(scan, extended=False):
    _send_key(scan, extended, key_up=False)


def release_key(scan, extended=False):
    _send_key(scan, extended, key_up=True)


# --------------------------------------------------------------------------
# DirectInput scan codes (set 1).  value = (scan_code, is_extended)
# --------------------------------------------------------------------------
KEYS = {}
for _ch, _sc in zip("QWERTYUIOP", range(0x10, 0x1A)):
    KEYS[_ch] = (_sc, False)
for _ch, _sc in zip("ASDFGHJKL", range(0x1E, 0x27)):
    KEYS[_ch] = (_sc, False)
for _ch, _sc in zip("ZXCVBNM", range(0x2C, 0x33)):
    KEYS[_ch] = (_sc, False)
for _i, _ch in enumerate("1234567890"):
    KEYS[_ch] = (0x02 + _i, False)
for _i in range(10):
    KEYS[f"F{_i + 1}"] = (0x3B + _i, False)
KEYS.update({
    "F11": (0x57, False), "F12": (0x58, False),
    "Space": (0x39, False), "Enter": (0x1C, False), "Tab": (0x0F, False),
    "Esc": (0x01, False), "Backspace": (0x0E, False), "CapsLock": (0x3A, False),
    "LShift": (0x2A, False), "RShift": (0x36, False),
    "LCtrl": (0x1D, False), "RCtrl": (0x1D, True),
    "LAlt": (0x38, False), "RAlt": (0x38, True),
    "-": (0x0C, False), "=": (0x0D, False), "[": (0x1A, False), "]": (0x1B, False),
    ";": (0x27, False), "'": (0x28, False), "`": (0x29, False), "\\": (0x2B, False),
    ",": (0x33, False), ".": (0x34, False), "/": (0x35, False),
    "Up": (0x48, True), "Down": (0x50, True), "Left": (0x4B, True), "Right": (0x4D, True),
    "Insert": (0x52, True), "Delete": (0x53, True), "Home": (0x47, True),
    "End": (0x4F, True), "PageUp": (0x49, True), "PageDown": (0x51, True),
    "Num0": (0x52, False), "Num1": (0x4F, False), "Num2": (0x50, False),
    "Num3": (0x51, False), "Num4": (0x4B, False), "Num5": (0x4C, False),
    "Num6": (0x4D, False), "Num7": (0x47, False), "Num8": (0x48, False),
    "Num9": (0x49, False), "Num+": (0x4E, False), "Num-": (0x4A, False),
    "Num*": (0x37, False), "Num.": (0x53, False), "NumEnter": (0x1C, True),
})
KEY_NAMES = list(KEYS.keys())

# Virtual-key codes for the start/stop hotkey (polled with GetAsyncKeyState)
HOTKEYS = {f"F{i}": 0x6F + i for i in range(1, 13)}
HOTKEYS.update({"Pause": 0x13, "ScrollLock": 0x91})

NUM_SLOTS = 5

SETTINGS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "KeyRepeater", "settings.json"
)
DEFAULT_SLOTS = [
    {"on": True, "key": "E", "interval": 100, "hold": 10, "times": 0},
    {"on": False, "key": "Q", "interval": 1000, "hold": 10, "times": 0},
    {"on": False, "key": "R", "interval": 1000, "hold": 10, "times": 0},
    {"on": False, "key": "F", "interval": 1000, "hold": 10, "times": 0},
    {"on": False, "key": "Space", "interval": 1000, "hold": 10, "times": 0},
]
DEFAULTS = {"slots": DEFAULT_SLOTS, "delay": 3, "hotkey": "F6", "dark": True, "topmost": True}

# --------------------------------------------------------------------------
# Themes
# --------------------------------------------------------------------------
THEMES = {
    True: {  # dark
        "bg": "#1e1f22", "field": "#2b2d31", "fg": "#e8e8e8", "muted": "#9a9fa6",
        "border": "#3d4047", "accent": "#4c8bf5", "hover": "#34363c",
    },
    False: {  # light
        "bg": "#f3f3f3", "field": "#ffffff", "fg": "#1f1f1f", "muted": "#6b6b6b",
        "border": "#c4c4c4", "accent": "#2f6fdf", "hover": "#e6e6e6",
    },
}
START_COLORS = ("#2e9e5b", "#36b468", "#26834b")  # normal, hover, pressed
STOP_COLORS = ("#d0453b", "#e0554b", "#ad3830")


def set_dark_titlebar(root, dark):
    """Dark window title bar on Windows 10/11 (no-op elsewhere)."""
    if not IS_WINDOWS:
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        root.withdraw()  # force the title bar to repaint
        root.deiconify()
    except (AttributeError, OSError):
        pass


# --------------------------------------------------------------------------
# Repeater engine: one thread per key, all sharing one stop signal
# --------------------------------------------------------------------------
class Repeater:
    def __init__(self):
        self._stop = threading.Event()
        self._threads = []
        self.counts = [0] * NUM_SLOTS

    @property
    def running(self):
        return any(t.is_alive() for t in self._threads)

    def start(self, jobs, delay_s=0.0):
        """jobs: list of (slot, key_name, interval_ms, hold_ms, times)."""
        if self.running:
            return
        self._stop.clear()
        self.counts = [0] * NUM_SLOTS
        self._threads = [
            threading.Thread(target=self._run, args=(*job, delay_s), daemon=True) for job in jobs
        ]
        for t in self._threads:
            t.start()

    def stop(self):
        self._stop.set()

    def _run(self, slot, key, interval_ms, hold_ms, times, delay_s):
        scan, ext = KEYS[key]
        winmm.timeBeginPeriod(1)  # 1 ms timer resolution for accurate sleeps
        try:
            if delay_s > 0 and self._stop.wait(delay_s):
                return
            interval = interval_ms / 1000.0
            hold = hold_ms / 1000.0
            next_t = time.perf_counter()
            while not self._stop.is_set():
                press_key(scan, ext)
                if hold > 0:
                    time.sleep(hold)
                release_key(scan, ext)
                self.counts[slot] += 1
                if times and self.counts[slot] >= times:
                    break
                next_t += interval
                wait = next_t - time.perf_counter()
                if wait > 0:
                    if self._stop.wait(wait):
                        break
                else:
                    next_t = time.perf_counter()  # fell behind: don't burst
        finally:
            release_key(scan, ext)  # never leave the key stuck down
            winmm.timeEndPeriod(1)


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.repeater = Repeater()
        self.settings = self._load_settings()
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        base = tkfont.nametofont("TkDefaultFont")
        self.font = (base.actual("family"), 10)
        self.bold = (base.actual("family"), 10, "bold")
        self.big = (base.actual("family"), 15, "bold")

        root.title("Key Repeater")
        root.resizable(False, False)

        frm = ttk.Frame(root, padding=14)
        frm.grid(sticky="nsew")
        self.combos = []

        # ---- key table ----
        headers = ["On", "Key", "Every (ms)", "Hold (ms)", "Times (0=∞)", "Sent"]
        for c, text in enumerate(headers):
            ttk.Label(frm, text=text, style="Header.TLabel").grid(
                row=0, column=c, sticky="w", padx=(0, 8), pady=(0, 4))

        self.rows = []
        for i, s in enumerate(self.settings["slots"]):
            row = {
                "on": tk.BooleanVar(value=s["on"]),
                "key": tk.StringVar(value=s["key"]),
                "interval": tk.IntVar(value=s["interval"]),
                "hold": tk.IntVar(value=s["hold"]),
                "times": tk.IntVar(value=s["times"]),
                "sent": tk.StringVar(value="0"),
            }
            r = i + 1
            ttk.Checkbutton(frm, variable=row["on"]).grid(row=r, column=0, sticky="w", pady=3)
            cb = ttk.Combobox(frm, textvariable=row["key"], values=KEY_NAMES,
                              state="readonly", width=9)
            cb.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=3)
            self.combos.append(cb)
            for c, (name, hi, step) in enumerate(
                    [("interval", 3_600_000, 10), ("hold", 60_000, 5), ("times", 10_000_000, 1)],
                    start=2):
                ttk.Spinbox(frm, from_=0, to=hi, increment=step, textvariable=row[name],
                            width=8).grid(row=r, column=c, sticky="w", padx=(0, 8), pady=3)
            ttk.Label(frm, textvariable=row["sent"], style="Muted.TLabel", width=7).grid(
                row=r, column=5, sticky="w", pady=3)
            self.rows.append(row)

        ttk.Separator(frm).grid(row=NUM_SLOTS + 1, column=0, columnspan=6, sticky="ew", pady=10)

        # ---- general options ----
        opts = ttk.Frame(frm)
        opts.grid(row=NUM_SLOTS + 2, column=0, columnspan=6, sticky="ew")
        self.delay_var = tk.IntVar(value=self.settings["delay"])
        self.hotkey_var = tk.StringVar(value=self.settings["hotkey"])
        self.topmost_var = tk.BooleanVar(value=self.settings["topmost"])
        self.dark_var = tk.BooleanVar(value=self.settings["dark"])

        ttk.Label(opts, text="Start/Stop hotkey").grid(row=0, column=0, sticky="w", padx=(0, 8))
        hk = ttk.Combobox(opts, textvariable=self.hotkey_var, values=list(HOTKEYS),
                          state="readonly", width=9)
        hk.grid(row=0, column=1, sticky="w", padx=(0, 20))
        self.combos.append(hk)
        ttk.Label(opts, text="Start delay (s)").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Spinbox(opts, from_=0, to=60, increment=1, textvariable=self.delay_var,
                    width=5).grid(row=0, column=3, sticky="w")
        ttk.Checkbutton(opts, text="Always on top", variable=self.topmost_var,
                        command=self._apply_topmost).grid(row=1, column=0, columnspan=2,
                                                          sticky="w", pady=(8, 0))
        ttk.Checkbutton(opts, text="Dark mode", variable=self.dark_var,
                        command=self._on_theme_toggle).grid(row=1, column=2, columnspan=2,
                                                            sticky="w", pady=(8, 0))

        # ---- big start/stop button ----
        self.btn = ttk.Button(frm, command=self.on_button, style="Start.TButton",
                              cursor="hand2")
        self.btn.grid(row=NUM_SLOTS + 3, column=0, columnspan=6, sticky="ew", pady=(14, 6))

        self.status = ttk.Label(frm, style="Muted.TLabel")
        self.status.grid(row=NUM_SLOTS + 4, column=0, columnspan=6, sticky="w")

        self._apply_theme()
        self._apply_topmost()
        self._hotkey_down = False
        self._watch_hotkey()
        self._refresh_ui()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---- theme ----
    def _apply_theme(self):
        t = THEMES[self.dark_var.get()]
        s = self.style
        self.root.configure(bg=t["bg"])
        s.configure(".", background=t["bg"], foreground=t["fg"], fieldbackground=t["field"],
                    bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"],
                    troughcolor=t["bg"], focuscolor=t["accent"], selectbackground=t["accent"],
                    selectforeground="#ffffff", insertcolor=t["fg"], arrowcolor=t["fg"],
                    font=self.font)
        s.map(".", foreground=[("disabled", t["muted"])])
        s.configure("Header.TLabel", foreground=t["muted"], font=self.bold)
        s.configure("Muted.TLabel", foreground=t["muted"])
        s.configure("TSeparator", background=t["border"])
        s.configure("TCheckbutton", indicatorbackground=t["field"],
                    indicatorforeground=t["fg"], indicatormargin=(0, 0, 6, 0))
        s.map("TCheckbutton", background=[("active", t["bg"])],
              indicatorbackground=[("selected", t["accent"]), ("active", t["hover"])],
              indicatorforeground=[("selected", "#ffffff")])
        for w in ("TCombobox", "TSpinbox"):
            s.configure(w, background=t["field"], fieldbackground=t["field"],
                        foreground=t["fg"], arrowcolor=t["fg"], padding=(6, 3))
            s.map(w, fieldbackground=[("readonly", t["field"])],
                  foreground=[("readonly", t["fg"])],
                  selectbackground=[("readonly", t["field"])],
                  selectforeground=[("readonly", t["fg"])],
                  background=[("active", t["hover"]), ("pressed", t["hover"])],
                  bordercolor=[("focus", t["accent"])])
        for name, (normal, hover, pressed) in (("Start", START_COLORS), ("Stop", STOP_COLORS)):
            style = f"{name}.TButton"
            s.configure(style, background=normal, foreground="#ffffff", font=self.big,
                        padding=(12, 14), borderwidth=0, focusthickness=0,
                        bordercolor=normal, lightcolor=normal, darkcolor=normal)
            s.map(style, background=[("pressed", pressed), ("active", hover)],
                  lightcolor=[("pressed", pressed), ("active", hover)],
                  darkcolor=[("pressed", pressed), ("active", hover)],
                  foreground=[("disabled", "#ffffff")])
        # dropdown lists are plain Tk listboxes, colour them directly
        for cb in self.combos:
            try:
                popdown = cb.tk.call("ttk::combobox::PopdownWindow", cb)
                cb.tk.call(f"{popdown}.f.l", "configure", "-background", t["field"],
                           "-foreground", t["fg"], "-selectbackground", t["accent"],
                           "-selectforeground", "#ffffff")
            except tk.TclError:
                pass
        set_dark_titlebar(self.root, self.dark_var.get())

    def _on_theme_toggle(self):
        self.settings["dark"] = self.dark_var.get()
        self._save_settings()
        self._apply_theme()

    def _apply_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())
        self.settings["topmost"] = self.topmost_var.get()

    # ---- settings ----
    def _load_settings(self):
        s = {k: v for k, v in DEFAULTS.items() if k != "slots"}
        slots = [dict(d) for d in DEFAULT_SLOTS]
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        for k in ("delay", "hotkey", "dark", "topmost"):
            if k in saved:
                s[k] = saved[k]
        if isinstance(saved.get("slots"), list):
            for i, d in enumerate(saved["slots"][:NUM_SLOTS]):
                if isinstance(d, dict):
                    slots[i].update({k: d[k] for k in slots[i] if k in d})
        elif "key" in saved:  # settings from v1.0 (single key)
            slots[0].update(key=saved["key"], interval=saved.get("interval", 100),
                            hold=saved.get("hold", 10), times=saved.get("count", 0))
        for d in slots:
            if d["key"] not in KEYS:
                d["key"] = "E"
        if s["hotkey"] not in HOTKEYS:
            s["hotkey"] = DEFAULTS["hotkey"]
        s["slots"] = slots
        return s

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except OSError:
            pass

    # ---- actions ----
    def _error(self, msg):
        messagebox.showerror("Key Repeater", msg, parent=self.root)

    def _read_inputs(self):
        slots, jobs, used = [], [], set()
        hotkey = self.hotkey_var.get()
        for i, row in enumerate(self.rows):
            n = i + 1
            try:
                d = {"on": row["on"].get(), "key": row["key"].get(),
                     "interval": int(row["interval"].get()), "hold": int(row["hold"].get()),
                     "times": int(row["times"].get())}
            except (tk.TclError, ValueError):
                self._error(f"Row {n}: please enter whole numbers only.")
                return None
            slots.append(d)
            if not d["on"]:
                continue
            if d["interval"] < 1:
                self._error(f"Row {n}: interval must be at least 1 ms.")
                return None
            if d["hold"] < 0 or d["times"] < 0:
                self._error(f"Row {n}: values can't be negative.")
                return None
            if d["hold"] >= d["interval"]:
                self._error(f"Row {n}: hold time must be shorter than the interval.")
                return None
            if d["key"] == hotkey:
                self._error(f"Row {n}: the key can't be the same as the Start/Stop hotkey.")
                return None
            if d["key"] in used:
                self._error(f"Row {n}: {d['key']} is already used in another row.")
                return None
            used.add(d["key"])
            jobs.append((i, d["key"], d["interval"], d["hold"], d["times"]))
        try:
            delay = int(self.delay_var.get())
        except (tk.TclError, ValueError):
            self._error("Start delay must be a whole number.")
            return None
        if not jobs:
            self._error("Tick at least one key to repeat.")
            return None
        self.settings.update(slots=slots, delay=max(0, delay), hotkey=hotkey)
        self._save_settings()
        return jobs, max(0, delay)

    def start(self, use_delay):
        vals = self._read_inputs()
        if vals is None:
            return
        jobs, delay = vals
        self.repeater.start(jobs, delay if use_delay else 0)

    def toggle(self, use_delay):
        if self.repeater.running:
            self.repeater.stop()
        else:
            self.start(use_delay)

    def on_button(self):
        self.toggle(use_delay=True)

    def _watch_hotkey(self):
        vk = HOTKEYS.get(self.hotkey_var.get())
        if vk:
            down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if down and not self._hotkey_down:
                self.toggle(use_delay=False)
            self._hotkey_down = down
        self.root.after(15, self._watch_hotkey)

    def _refresh_ui(self):
        hk = self.hotkey_var.get()
        counts = self.repeater.counts
        for row, n in zip(self.rows, counts):
            row["sent"].set(str(n))
        total = sum(counts)
        if self.repeater.running:
            self.btn.configure(text=f"■  STOP   ({hk})", style="Stop.TButton")
            self.status.configure(text=f"Running — {total} presses sent")
        else:
            self.btn.configure(text=f"▶  START   ({hk})", style="Start.TButton")
            self.status.configure(text=f"Stopped — {total} presses sent"
                                  + ("" if IS_WINDOWS else "   (preview mode: no keys sent)"))
        self.root.after(100, self._refresh_ui)

    def on_close(self):
        self.repeater.stop()
        self._save_settings()
        self.root.destroy()


def main():
    if IS_WINDOWS:
        try:  # crisp text on high-DPI screens
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    else:
        print("Preview mode: not on Windows, so no keys will be sent and the hotkey is disabled.")
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

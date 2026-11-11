"""
Key Repeater - presses a keyboard key repeatedly at a millisecond interval (Windows).

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

SETTINGS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "KeyRepeater", "settings.json"
)
DEFAULTS = {"key": "E", "interval": 100, "hold": 10, "count": 0, "delay": 3, "hotkey": "F6"}


# --------------------------------------------------------------------------
# Repeater engine
# --------------------------------------------------------------------------
class Repeater:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self.presses = 0

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, key, interval_ms, hold_ms, count, delay_s=0.0):
        if self.running:
            return
        self._stop.clear()
        self.presses = 0
        scan, ext = KEYS[key]
        self._thread = threading.Thread(
            target=self._run, args=(scan, ext, interval_ms, hold_ms, count, delay_s), daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self, scan, ext, interval_ms, hold_ms, count, delay_s):
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
                self.presses += 1
                if count and self.presses >= count:
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

        root.title("Key Repeater")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        frm = ttk.Frame(root, padding=12)
        frm.grid()

        self.key_var = tk.StringVar(value=self.settings["key"])
        self.interval_var = tk.IntVar(value=self.settings["interval"])
        self.hold_var = tk.IntVar(value=self.settings["hold"])
        self.count_var = tk.IntVar(value=self.settings["count"])
        self.delay_var = tk.IntVar(value=self.settings["delay"])
        self.hotkey_var = tk.StringVar(value=self.settings["hotkey"])
        self.topmost_var = tk.BooleanVar(value=True)

        rows = [
            ("Key to repeat", ttk.Combobox(frm, textvariable=self.key_var, values=KEY_NAMES,
                                           state="readonly", width=12)),
            ("Repeat every (ms)", ttk.Spinbox(frm, from_=1, to=3_600_000, increment=10,
                                              textvariable=self.interval_var, width=12)),
            ("Hold key down (ms)", ttk.Spinbox(frm, from_=0, to=60_000, increment=5,
                                               textvariable=self.hold_var, width=12)),
            ("Stop after (0 = never)", ttk.Spinbox(frm, from_=0, to=10_000_000, increment=1,
                                                   textvariable=self.count_var, width=12)),
            ("Start delay (s, button)", ttk.Spinbox(frm, from_=0, to=60, increment=1,
                                                    textvariable=self.delay_var, width=12)),
            ("Start/Stop hotkey", ttk.Combobox(frm, textvariable=self.hotkey_var,
                                               values=list(HOTKEYS), state="readonly", width=12)),
        ]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
            widget.grid(row=i, column=1, sticky="ew", pady=3)

        r = len(rows)
        ttk.Checkbutton(frm, text="Always on top", variable=self.topmost_var,
                        command=lambda: root.attributes("-topmost", self.topmost_var.get())
                        ).grid(row=r, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.btn = ttk.Button(frm, text="Start", command=self.on_button)
        self.btn.grid(row=r + 1, column=0, columnspan=2, sticky="ew", pady=(10, 4))

        self.status = ttk.Label(frm, text="Stopped", foreground="gray")
        self.status.grid(row=r + 2, column=0, columnspan=2, sticky="w")

        self._hotkey_down = False
        self._watch_hotkey()
        self._refresh_ui()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---- settings ----
    def _load_settings(self):
        s = dict(DEFAULTS)
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
        if s["key"] not in KEYS:
            s["key"] = DEFAULTS["key"]
        if s["hotkey"] not in HOTKEYS:
            s["hotkey"] = DEFAULTS["hotkey"]
        return s

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except OSError:
            pass

    # ---- actions ----
    def _read_inputs(self):
        try:
            interval = int(self.interval_var.get())
            hold = int(self.hold_var.get())
            count = int(self.count_var.get())
            delay = int(self.delay_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Key Repeater", "Please enter whole numbers only.")
            return None
        if interval < 1:
            messagebox.showerror("Key Repeater", "Interval must be at least 1 ms.")
            return None
        if hold < 0 or count < 0 or delay < 0:
            messagebox.showerror("Key Repeater", "Values can't be negative.")
            return None
        if hold >= interval:
            messagebox.showerror("Key Repeater", "Hold time must be shorter than the interval.")
            return None
        key = self.key_var.get()
        if key == self.hotkey_var.get():
            messagebox.showerror("Key Repeater", "The repeated key can't be the same as the hotkey.")
            return None
        self.settings.update(key=key, interval=interval, hold=hold, count=count,
                             delay=delay, hotkey=self.hotkey_var.get())
        self._save_settings()
        return key, interval, hold, count, delay

    def start(self, use_delay):
        vals = self._read_inputs()
        if vals is None:
            return
        key, interval, hold, count, delay = vals
        self.repeater.start(key, interval, hold, count, delay if use_delay else 0)

    def on_button(self):
        if self.repeater.running:
            self.repeater.stop()
        else:
            self.start(use_delay=True)

    def on_hotkey(self):
        if self.repeater.running:
            self.repeater.stop()
        else:
            self.start(use_delay=False)

    def _watch_hotkey(self):
        vk = HOTKEYS.get(self.hotkey_var.get())
        if vk:
            down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if down and not self._hotkey_down:
                self.on_hotkey()
            self._hotkey_down = down
        self.root.after(15, self._watch_hotkey)

    def _refresh_ui(self):
        if self.repeater.running:
            self.btn.config(text=f"Stop  ({self.hotkey_var.get()})")
            self.status.config(text=f"Running — {self.repeater.presses} presses", foreground="green")
        else:
            self.btn.config(text=f"Start  ({self.hotkey_var.get()})")
            self.status.config(text=f"Stopped — {self.repeater.presses} presses", foreground="gray")
        self.root.after(100, self._refresh_ui)

    def on_close(self):
        self.repeater.stop()
        self.root.destroy()


def main():
    if not IS_WINDOWS:
        print("Key Repeater only works on Windows.")
        sys.exit(1)
    try:  # crisp text on high-DPI screens
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

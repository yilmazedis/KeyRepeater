# Key Repeater (Windows)

A small Windows app that presses a key repeatedly at an interval you set in milliseconds.

It uses the same method as `keys.py` in [Sentdex/pygta5](https://github.com/Sentdex/pygta5/blob/master/keys.py): `SendInput` with DirectInput **scan codes**. That means games that ignore ordinary virtual-key input still see the presses.

## Settings

| Setting | Meaning |
|---|---|
| Key to repeat | Letters, digits, F1–F12, arrows, Space, Enter, modifiers, numpad, … |
| Repeat every (ms) | Time between presses (minimum 1 ms) |
| Hold key down (ms) | How long each press stays down (0 = instant tap). Must be less than the interval |
| Stop after | Stop after N presses (0 = run until stopped) |
| Start delay (s) | Only applies to the **Start button**, so you have time to switch to the target window |
| Start/Stop hotkey | Global hotkey (default **F6**) that toggles repeating from any window |

Settings are saved to `%APPDATA%\KeyRepeater\settings.json`.

## Build the .exe

On a Windows PC with Python 3.8+ (from python.org):

```bat
build.bat
```

The output is `dist\KeyRepeater.exe`, a single file that runs without Python installed.

**No Windows PC?** Push this folder to a GitHub repo. The included workflow (`.github/workflows/build.yml`) builds the exe on GitHub's Windows runners. Download it from the run's **Artifacts** section.

To run without building: `python key_repeater.py`

## Notes

- If the target game or app runs **as Administrator**, run Key Repeater as Administrator too. Windows blocks input from lower-privilege processes.
- Timing uses a 1 ms system timer resolution and drift-free scheduling. Intervals of about 5 ms or more are accurate. Below that, results depend on the PC.
- Some anti-cheat systems flag synthetic input. Use it at your own risk in online games.

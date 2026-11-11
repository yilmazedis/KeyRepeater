# Key Repeater (Windows)

A small Windows app that presses up to **5 keys** repeatedly, each at its own interval in milliseconds.

It uses the same method as `keys.py` in [Sentdex/pygta5](https://github.com/Sentdex/pygta5/blob/master/keys.py): `SendInput` with DirectInput **scan codes**. That means games that ignore ordinary virtual-key input still see the presses.

## Settings

Each of the 5 key rows has its own settings, and every ticked row runs on its own timer at the same time:

| Column | Meaning |
|---|---|
| On | Tick the rows you want to repeat |
| Key | Letters, digits, F1–F12, arrows, Space, Enter, modifiers, numpad, … |
| Every (ms) | Time between presses (minimum 1 ms) |
| Hold (ms) | How long each press stays down (0 = instant tap). Must be less than the interval |
| Times | Stop that key after N presses (0 = run until stopped) |
| Sent | Live count of presses sent |

General options:

| Option | Meaning |
|---|---|
| Start/Stop hotkey | Global hotkey (default **F6**) that toggles repeating from any window |
| Start delay (s) | Only applies to the **Start button**, so you have time to switch to the target window |
| Always on top | Keeps the window above other windows |
| Dark mode | Dark or light theme (dark by default) |

Settings are saved to `%APPDATA%\KeyRepeater\settings.json`.

On macOS or Linux, `python3 key_repeater.py` opens the window in **preview mode**: the UI works, but no keys are sent.

## Build the .exe

On a Windows PC with Python 3.8+ (from python.org):

```bat
build.bat
```

The output is `dist\KeyRepeater.exe`, a single file that runs without Python installed.

**No Windows PC?** Push this folder to a GitHub repo. The included workflow (`.github/workflows/build.yml`) builds the exe on GitHub's Windows runners. Download it from the run's **Artifacts** section.

To run without building: `python key_repeater.py`

## Publishing a new version

Push a version tag. The workflow builds the exe and publishes a GitHub Release with it attached:

```bash
git tag v1.1.0
git push origin v1.1.0
```

The release notes include the exe's SHA-256 checksum and a list of changes since the previous tag.

## Notes

- If the target game or app runs **as Administrator**, run Key Repeater as Administrator too. Windows blocks input from lower-privilege processes.
- Timing uses a 1 ms system timer resolution and drift-free scheduling. Intervals of about 5 ms or more are accurate. Below that, results depend on the PC.
- Some anti-cheat systems flag synthetic input. Use it at your own risk in online games.

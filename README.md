# Key Repeater

A small Windows tool that presses up to **5 keys** automatically, each at its own interval in milliseconds. It's built for **software testing** and for **making repetitive keyboard work easier**.

**[⬇ Download the latest KeyRepeater.exe](https://github.com/yilmazedis/KeyRepeater/releases/latest)**. It's a single file, and Python is not needed.

## What it's for

### Testing and development
- **Input stress testing:** check how an app behaves when a key is pressed thousands of times, or every 5–10 ms.
- **Dropped-input checks:** the live **Sent** counter shows exactly how many presses went out, so you can compare it with what your app received.
- **Repeatable QA steps:** run the same key sequence at the same pace every time, without a tester's timing changing the result.
- **Soak and long-running tests:** keep an app busy with steady input for hours.
- **Generating input data:** produce consistent keyboard input for recording, logging or training data.

### Accessibility and everyday use
- **Less strain:** for people who find repeated or held key presses tiring or painful, one hotkey takes over the repetition.
- **Hands-free paging:** step through slides, documents, records or long lists with Page Down, arrows or Enter at a steady pace.
- **Repetitive data entry:** press Tab, Enter or another key on a timer while you focus on the content.
- **Keeping a session active:** an occasional harmless key press (for example Shift every few minutes) keeps the screen or an app from going idle.

## How to use it

1. Run **KeyRepeater.exe**.
2. Tick a row, pick a key, and set how often to press it.
3. Click **START**, then switch to the target window within the start delay (3 seconds by default). Or switch first and press **F6**.
4. Press **F6** again, or click **STOP**, to stop.

On first launch Windows SmartScreen may say "Windows protected your PC". The exe isn't code-signed, so click **More info → Run anyway**.

## Settings

Each of the 5 key rows has its own settings, and every ticked row runs on its own timer at the same time:

| Column | Meaning |
|---|---|
| On | Tick the rows you want to repeat |
| Key | Letters, digits, F1–F12, arrows, Space, Enter, Tab, modifiers, numpad, … |
| Every (ms) | Time between presses (minimum 1 ms) |
| Hold (ms) | How long each press stays down (0 = instant tap). Must be less than the interval |
| Times | Stop that key after N presses (0 = run until stopped) |
| Sent | Live count of presses sent |

General options:

| Option | Meaning |
|---|---|
| Start/Stop hotkey | Global hotkey (default **F6**) that works from any window |
| Start delay (s) | Only applies to the **START button**, so you have time to switch to the target window |
| Always on top | Keeps the window above other windows |
| Dark mode | Dark or light theme (dark by default) |

Settings are saved to `%APPDATA%\KeyRepeater\settings.json`.

## How it works

Key presses are sent with the Windows `SendInput` API using hardware **scan codes** (the technique from `keys.py` in [Sentdex/pygta5](https://github.com/Sentdex/pygta5/blob/master/keys.py)). They look like a real keyboard to applications, including ones that read input at a low level and ignore ordinary simulated key events.

Timing uses a 1 ms system timer resolution and drift-free scheduling. Intervals of about 5 ms or more are accurate. Below that, results depend on the PC.

## Notes

- If the target app runs **as Administrator**, run Key Repeater as Administrator too. Windows blocks input from lower-privilege programs.
- Only use Key Repeater where automated input is allowed. Many online services and games forbid automation in their terms of use, and you are responsible for following them.

## For developers

### Run from source

```bash
python key_repeater.py
```

On macOS or Linux this opens the window in **preview mode**: the UI works, but no keys are sent.

### Build the .exe

On a Windows PC with Python 3.8+ (from python.org), run `build.bat`. The output is `dist\KeyRepeater.exe`.

Without a Windows PC, push to GitHub: the included workflow (`.github/workflows/build.yml`) builds the exe on GitHub's Windows runners on every push. Download it from the run's **Artifacts** section.

### Publish a new version

Push a version tag. The workflow builds the exe and publishes a GitHub Release with it attached:

```bash
git tag v1.2.0
git push origin v1.2.0
```

The release notes include the exe's SHA-256 checksum and a link to the changes since the previous tag.

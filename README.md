# Vispur

A local speech-to-text tool that transcribes your voice and types the result into whatever window is active. Uses the [Moonshine](https://huggingface.co/UsefulSensors/moonshine-streaming-medium) model, which runs entirely on your machine — no internet required after the first run.

## How it works

1. Press **Ctrl+Alt+L** to start recording.
2. Speak.
3. Press **Ctrl+Alt+L** again to stop — the transcribed text is automatically typed into the active window.

The script pastes via the clipboard and then restores whatever was in your clipboard before, so your clipboard contents are preserved.

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- A working microphone
- Windows (hotkey listener uses `pynput`)

## Setup

```powershell
uv venv
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.lock
```

> **Note:** Installing the CPU-only wheel of PyTorch first avoids pulling in the much larger CUDA build as a transitive dependency. `requirements.lock` contains pinned versions of all dependencies for a reproducible install. If you prefer floating versions, use `requirements.txt` instead.

The first run will download the Moonshine model (~500 MB) from Hugging Face and cache it locally. Subsequent runs load from cache and start in a few seconds.

---

## Running in development

For development and testing, run `app.py` directly:

```powershell
uv run app.py
```

Wait for `Ready. Press Ctrl+Alt+L to start/stop recording.` before using the hotkey. The process runs in the foreground — `Ctrl+C` stops it cleanly.

---

## Installing as a background task

`service.py` registers Vispur as a Windows Task Scheduler task so it starts automatically at login with no terminal window.

1. Open **PowerShell as Administrator** (Start → search "PowerShell" → right-click → *Run as administrator*)
2. Navigate to the project folder and activate the virtual environment:

```powershell
cd "C:\path\to\Vispur"
.\.venv\Scripts\Activate.ps1
```

3. Install and start the task:

```powershell
python service.py install
python service.py start
```

Vispur will now launch automatically every time you log in.

### Managing the task

Run these from an Administrator PowerShell with the venv activated:

```powershell
python service.py stop      # stop without uninstalling
python service.py start     # start again
python service.py restart   # stop and start
```

You can also manage it from **Task Scheduler** (search the Start menu) under the name `Vispur`.

### Uninstalling

```powershell
python service.py remove
```

This removes the task from Task Scheduler. Your files and the cached model are not affected.

---

## Hotkey

| Action | Hotkey |
|--------|--------|
| Start recording | Ctrl+Alt+L |
| Stop recording & transcribe | Ctrl+Alt+L |

To change the hotkey, edit the `HOTKEY` variable at the top of `app.py`. The format follows `pynput` syntax, e.g. `"<ctrl>+<alt>+l"`. If the background task is running, restart it after making changes:

```powershell
python service.py restart
```

## Notes

- Transcription happens in a background thread; you can't start a new recording while one is processing.
- Very short recordings (less than ~0.5s) may produce no output.
- Audio is padded to a multiple of 80 samples to satisfy an internal requirement of the Moonshine streaming model.

---

## Attribution

Sound effects from Pixabay:

- [Pop sound effect](https://pixabay.com/sound-effects/film-special-effects-pop-sound-423716/) by SoundReality
- [Bubble pop sound effect](https://pixabay.com/sound-effects/film-special-effects-bubble-pop-406640/) by DRAGON-STUDIO
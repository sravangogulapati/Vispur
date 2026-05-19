MODEL = "UsefulSensors/moonshine-streaming-medium"
HOTKEY = "<ctrl>+<alt>+l"
SAMPLE_RATE = 16000

import collections
import threading
import time
from pathlib import Path

import miniaudio
import numpy as np
import sounddevice as sd
import pyperclip
from pynput import keyboard
from transformers import pipeline

from overlay import StatusOverlay

_BASE = Path(__file__).parent


def _load_sound(path):
    decoded = miniaudio.decode_file(str(path))
    samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
    if decoded.nchannels > 1:
        samples = samples.reshape(-1, decoded.nchannels)
    return samples, decoded.sample_rate


def run(stop_event: threading.Event) -> None:
    sound_beep, sr_start = _load_sound(_BASE / "sounds" / "single-pop.mp3")
    sound_done, _sr_stop = _load_sound(_BASE / "sounds" / "triple-pop.mp3")

    _sfx_channels = sound_beep.shape[1] if sound_beep.ndim > 1 else 1
    _sfx_stream = sd.OutputStream(samplerate=sr_start, channels=_sfx_channels, dtype="float32")
    _sfx_stream.start()

    def play_sound(samples):
        threading.Thread(target=_sfx_stream.write, args=(samples,), daemon=True).start()

    print("Loading model...")
    asr = pipeline("automatic-speech-recognition", model=MODEL)
    overlay = StatusOverlay()
    print("Ready. Press Ctrl+Alt+L to start/stop recording.")

    audio_buffer = collections.deque()
    is_recording = False
    is_processing = False
    stream = None

    def process_audio(audio_data):
        nonlocal is_processing
        try:
            result = asr({"array": audio_data, "sampling_rate": SAMPLE_RATE})
            text = result["text"].strip()
            if text:
                original = pyperclip.paste()
                pyperclip.copy(text)
                kbd = keyboard.Controller()
                with kbd.pressed(keyboard.Key.ctrl):
                    kbd.press("v")
                    kbd.release("v")
                overlay.set_state("done")
                play_sound(sound_done)

                def restore():
                    time.sleep(0.2)
                    pyperclip.copy(original)

                threading.Thread(target=restore, daemon=True).start()
                print(f"Typed: {text}")
            else:
                overlay.set_state("idle")
                print("(no speech detected)")
        finally:
            is_processing = False

    def audio_callback(indata, frames, time_info, status):
        if is_recording:
            audio_buffer.append(indata[:, 0].copy())

    def toggle_recording():
        nonlocal is_recording, is_processing, stream, audio_buffer

        if is_processing:
            return

        if not is_recording:
            audio_buffer = collections.deque()
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=audio_callback,
            )
            stream.start()
            is_recording = True
            play_sound(sound_beep)
            overlay.set_state("recording")
            print("● Recording…")
        else:
            is_recording = False
            play_sound(sound_beep)
            stream.stop()
            stream.close()
            stream = None

            chunks = list(audio_buffer)
            audio_buffer = collections.deque()

            if chunks:
                audio_data = np.concatenate(chunks).astype(np.float32)
                remainder = len(audio_data) % 80
                if remainder:
                    audio_data = np.pad(audio_data, (0, 80 - remainder))
                is_processing = True
                overlay.set_state("processing")
                print("Processing…")
                threading.Thread(
                    target=process_audio, args=(audio_data,), daemon=True
                ).start()
            else:
                overlay.set_state("idle")
                print("(no audio captured)")

    hotkey_combo = keyboard.HotKey(keyboard.HotKey.parse(HOTKEY), toggle_recording)

    listener = keyboard.Listener(
        on_press=lambda k: hotkey_combo.press(listener.canonical(k)),
        on_release=lambda k: hotkey_combo.release(listener.canonical(k)),
    )
    listener.start()
    try:
        stop_event.wait()
    finally:
        listener.stop()
        _sfx_stream.stop()
        _sfx_stream.close()


if __name__ == "__main__":
    run(threading.Event())

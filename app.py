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

MODEL = "UsefulSensors/moonshine-streaming-medium"
HOTKEY = "<ctrl>+<alt>+l"
SAMPLE_RATE = 16000

_BASE = Path(__file__).parent


def _load_sound(path):
    decoded = miniaudio.decode_file(str(path))
    samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
    if decoded.nchannels > 1:
        samples = samples.reshape(-1, decoded.nchannels)
    return samples, decoded.sample_rate


class _RecordingSession:
    def __init__(self):
        self.sound_beep, sr_start = _load_sound(_BASE / "sounds" / "single-pop.mp3")
        self.sound_done, _ = _load_sound(_BASE / "sounds" / "triple-pop.mp3")

        channels = self.sound_beep.shape[1] if self.sound_beep.ndim > 1 else 1
        self.sfx_stream = sd.OutputStream(samplerate=sr_start, channels=channels, dtype="float32")
        self.sfx_stream.start()

        print("Loading model...")
        self.asr = pipeline("automatic-speech-recognition", model=MODEL)
        self.overlay = StatusOverlay()
        print("Ready. Press Ctrl+Alt+L to start/stop recording.")

        self.audio_buffer = collections.deque()
        self.is_recording = False
        self.is_processing = False
        self.stream = None

    def play_sound(self, samples):
        threading.Thread(target=self.sfx_stream.write, args=(samples,), daemon=True).start()

    def process_audio(self, audio_data):
        try:
            result = self.asr({"array": audio_data, "sampling_rate": SAMPLE_RATE})
            text = result["text"].strip()
            if text:
                self._paste_text(text)
                print(f"Typed: {text}")
            else:
                self.overlay.set_state("idle")
                print("(no speech detected)")
        finally:
            self.is_processing = False

    def _paste_text(self, text):
        original = pyperclip.paste()
        pyperclip.copy(text)
        kbd = keyboard.Controller()
        with kbd.pressed(keyboard.Key.ctrl):
            kbd.press("v")
            kbd.release("v")
        self.overlay.set_state("done")
        self.play_sound(self.sound_done)

        def restore():
            time.sleep(0.2)
            pyperclip.copy(original)

        threading.Thread(target=restore, daemon=True).start()

    def audio_callback(self, indata, _frames, _time_info, _status):
        if self.is_recording:
            self.audio_buffer.append(indata[:, 0].copy())

    def toggle_recording(self):
        if self.is_processing:
            return

        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self.audio_buffer = collections.deque()
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self.audio_callback,
        )
        self.stream.start()
        self.is_recording = True
        self.play_sound(self.sound_beep)
        self.overlay.set_state("recording")
        print("● Recording…")

    def _stop_recording(self):
        self.is_recording = False
        self.play_sound(self.sound_beep)
        self.stream.stop()
        self.stream.close()
        self.stream = None

        chunks = list(self.audio_buffer)
        self.audio_buffer = collections.deque()

        if chunks:
            audio_data = np.concatenate(chunks).astype(np.float32)
            remainder = len(audio_data) % 80
            if remainder:
                audio_data = np.pad(audio_data, (0, 80 - remainder))
            self.is_processing = True
            self.overlay.set_state("processing")
            print("Processing…")
            threading.Thread(
                target=self.process_audio, args=(audio_data,), daemon=True
            ).start()
        else:
            self.overlay.set_state("idle")
            print("(no audio captured)")

    def cleanup(self):
        self.sfx_stream.stop()
        self.sfx_stream.close()


def run(stop_event: threading.Event) -> None:
    session = _RecordingSession()

    hotkey_combo = keyboard.HotKey(keyboard.HotKey.parse(HOTKEY), session.toggle_recording)

    listener = keyboard.Listener(
        on_press=lambda k: hotkey_combo.press(listener.canonical(k)),
        on_release=lambda k: hotkey_combo.release(listener.canonical(k)),
    )
    listener.start()
    try:
        stop_event.wait()
    finally:
        listener.stop()
        session.cleanup()


if __name__ == "__main__":
    run(threading.Event())

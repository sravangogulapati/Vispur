import ctypes
import ctypes.wintypes
import queue
import threading
import tkinter as tk

_STATES: dict[str, tuple[str, str]] = {
    "recording":  ("#e05555", "● Recording"),
    "processing": ("#e0a020", "◌ Processing…"),
    "done":       ("#40b060", "✓ Done"),
}

_POLL_MS = 50
_DONE_LINGER_MS = 1500
_WIDTH, _HEIGHT = 230, 48


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork",    ctypes.wintypes.RECT),
        ("dwFlags",   ctypes.wintypes.DWORD),
    ]


def _active_monitor_rect() -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) of the monitor that owns the foreground window."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        r = info.rcMonitor
        return r.left, r.top, r.right, r.bottom
    except OSError:
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        return 0, 0, w, h


class StatusOverlay:
    """Thread-safe screen overlay that displays transcription pipeline state.

    All tkinter calls are confined to a dedicated daemon thread; callers
    communicate exclusively through set_state(), which is safe to call from
    any thread.

    The overlay follows the monitor that owns the foreground window at the
    moment each state transition fires.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._auto_hide_id: str | None = None
        threading.Thread(target=self._run, daemon=True).start()

    def set_state(self, state: str) -> None:
        """Transition to a new state.

        Valid states: 'recording' | 'processing' | 'done' | 'idle'
        'done' auto-hides after a short delay; 'idle' hides immediately.
        """
        if state not in _STATES and state != "idle":
            raise ValueError(f"Unknown overlay state: {state!r}")
        self._queue.put(state)

    # ------------------------------------------------------------------ #
    # private — runs entirely on the tkinter thread                        #
    # ------------------------------------------------------------------ #

    def _run(self) -> None:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.88)
        root.configure(bg="#1a1a2e")
        root.geometry(f"{_WIDTH}x{_HEIGHT}+0+0")  # placeholder; repositioned on show

        self._label = tk.Label(
            root,
            font=("Segoe UI", 13, "bold"),
            fg="white",
            bg="#1a1a2e",
            padx=16,
            pady=10,
        )
        self._label.pack(fill="both", expand=True)

        self._root = root
        root.withdraw()
        root.after(_POLL_MS, self._poll)
        root.mainloop()

    def _poll(self) -> None:
        try:
            while True:
                self._apply(self._queue.get_nowait())
        except queue.Empty:
            pass
        self._root.after(_POLL_MS, self._poll)

    def _apply(self, state: str) -> None:
        if self._auto_hide_id is not None:
            self._root.after_cancel(self._auto_hide_id)
            self._auto_hide_id = None

        if state == "idle":
            self._root.withdraw()
            return

        color, text = _STATES[state]
        self._label.configure(text=text, fg=color)
        self._root.geometry(self._overlay_geometry())
        self._root.deiconify()

        if state == "done":
            self._auto_hide_id = self._root.after(_DONE_LINGER_MS, self._root.withdraw)

    def _overlay_geometry(self) -> str:
        left, top, right, bottom = _active_monitor_rect()
        mon_w, mon_h = right - left, bottom - top
        x = left + (mon_w - _WIDTH) // 2
        y = top + mon_h * 2 // 3  # lower-third: visible but out of typical typing area
        return f"{_WIDTH}x{_HEIGHT}+{x}+{y}"

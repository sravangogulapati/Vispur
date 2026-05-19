import subprocess
import sys
from pathlib import Path

TASK_NAME = "Vispur"
_HERE = Path(__file__).parent
_VBS = _HERE / "launch.vbs"


def _python():
    pythonw = _HERE / ".venv" / "Scripts" / "pythonw.exe"
    if pythonw.exists():
        return str(pythonw)
    return str(_HERE / ".venv" / "Scripts" / "python.exe")


def _write_vbs():
    exe = _python()
    script = str(_HERE / "app.py")
    # WindowStyle=0 forces the window hidden even if pythonw.exe is a console shim.
    # bWaitOnReturn=False lets wscript exit immediately; app runs as an independent process.
    _VBS.write_text(
        f'CreateObject("WScript.Shell").Run '
        f'Chr(34) & "{exe}" & Chr(34) & " " & Chr(34) & "{script}" & Chr(34), 0, False\n',
        encoding="utf-8",
    )


def _run(args, check=True):
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip())
        sys.exit(1)
    return result


def install():
    _write_vbs()
    _run([
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", f'wscript.exe "{_VBS}"',
        "/sc", "onlogon",
        "/f",
    ])
    print("Installed. Vispur will start automatically at next login.")
    print('Run "python service.py start" to launch it now.')


def remove():
    stop()
    _run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"])
    _VBS.unlink(missing_ok=True)
    print("Removed.")


def start():
    _run(["schtasks", "/run", "/tn", TASK_NAME])
    print("Started.")


def stop():
    _run(["schtasks", "/end", "/tn", TASK_NAME], check=False)
    # wscript exits immediately (bWaitOnReturn=False), so kill pythonw.exe directly.
    # The CommandLine filter is narrow enough to avoid collateral kills in practice,
    # but any other pythonw.exe process whose path happens to contain "app.py" would
    # also be stopped.
    subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process"
            " | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*app.py*' }"
            " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
        ],
        capture_output=True, text=True,
    )
    print("Stopped.")


def restart():
    stop()
    start()


COMMANDS = {"install": install, "remove": remove, "start": start, "stop": stop, "restart": restart}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python service.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()

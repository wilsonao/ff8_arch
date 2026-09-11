"""Capture the running FF8 window (or a whole monitor) to a PNG.

Usage:
    python tools/screenshot.py [out.png] [--scale 0.5] [--monitor N]

Default: locate the FF8_EN main window via Win32, capture its client area,
downscale by --scale (default 0.5 -> 960x540 for a 1080p window) and write
out.png (default: shot.png in the scratchpad if CLAUDE_SCRATCHPAD is set,
else the cwd). --monitor N captures the Nth virtual-desktop monitor instead
(0-based, left to right) - useful when the window handle lookup fails.

The game must run windowed or borderless; exclusive fullscreen captures black.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys

from PIL import ImageGrab

user32 = ctypes.windll.user32
PROCESS_NAMES = ("FF8_EN", "FF8_FR", "FF8_DE", "FF8_ES", "FF8_IT", "FF8_JP")


def find_game_rect():
    """Return (l, t, r, b) of the FF8 main window, or None."""
    import subprocess
    cmd = (
        "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
        "ForEach-Object { $_.ProcessName + '|' + $_.MainWindowHandle }"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                         capture_output=True, text=True).stdout
    hwnd = None
    for line in out.splitlines():
        name, _, h = line.partition("|")
        if name.strip() in PROCESS_NAMES:
            hwnd = int(h.strip())
            break
    if not hwnd:
        return None
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def monitors():
    """List monitor bounds as (l, t, r, b), sorted left to right."""
    rects = []

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

    def cb(hmon, hdc, prect, lparam):
        r = prect.contents
        rects.append((r.left, r.top, r.right, r.bottom))
        return 1

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    return sorted(rects)


def clamp_to_monitor(rect):
    """Trim an off-screen window frame to the monitor that contains it."""
    l, t, r, b = rect
    cx, cy = (l + r) // 2, (t + b) // 2
    for ml, mt, mr, mb in monitors():
        if ml <= cx < mr and mt <= cy < mb:
            return (max(l, ml), max(t, mt), min(r, mr), min(b, mb))
    return rect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--monitor", type=int)
    a = ap.parse_args()

    if a.monitor is not None:
        mons = monitors()
        rect = mons[a.monitor]
    else:
        rect = find_game_rect()
        if rect is None:
            print("FF8 window not found; is the game running?", file=sys.stderr)
            return 2
        rect = clamp_to_monitor(rect)

    out = a.out or os.path.join(os.environ.get("CLAUDE_SCRATCHPAD", "."), "shot.png")
    im = ImageGrab.grab(bbox=rect, all_screens=True)
    if a.scale != 1.0:
        im = im.resize((int(im.width * a.scale), int(im.height * a.scale)))
    im.save(out)
    print(f"{out} {im.width}x{im.height} from {rect}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

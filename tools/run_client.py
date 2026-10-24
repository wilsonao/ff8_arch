"""Launch the FF8 AP client in THIS process: its window (the FF8 tab has every
command as a button, beside the text client's log) plus a console that stays
typeable (/ff8, /ff8verify, /ff8missed, /ff8check, /deathlink all work there
too).

Usage:  python tools\\run_client.py [--nogui] [--name SLOT] [--connect HOST:PORT]
Defaults to the solo-campaign slot: --name Wilson --connect localhost:38281.
--nogui keeps it to the console, as before the window existed.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Archipelago"
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import ModuleUpdate

ModuleUpdate.update_ran = True

from worlds.ff8.client import launch  # noqa: E402

args = sys.argv[1:]
if not [a for a in args if a != "--nogui"]:
    args += ["--name", "Wilson", "--connect", "localhost:38281"]
launch(*args)

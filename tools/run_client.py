"""Launch the headless FF8 AP client in THIS process so the console stays
typeable (/ff8, /ff8verify, /ff8missed, /ff8check, /deathlink all work).

Usage:  python tools\\run_client.py [--name SLOT] [--connect HOST:PORT]
Defaults to the solo-campaign slot: --name Wilson --connect localhost:38281.
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

args = sys.argv[1:] or ["--name", "Wilson", "--connect", "localhost:38281"]
launch("--nogui", *args)

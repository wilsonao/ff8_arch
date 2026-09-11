"""Jukebox trap probe: change the song playing in a running FF8_EN.exe.

Runs the same path the client's Jukebox trap uses (memory.FF8Interface.play_song:
the game's own sd_music_play on a remote thread, fed a synthesized AKAO
header). Use it to hear the effect, and to check an install WITHOUT FFNx
(vanilla DirectMusic player) — the one case not yet exercised live.

    python tools/poc_music_trap.py            # random JUKEBOX_SONGS pick, as the trap does
    python tools/poc_music_trap.py 29         # Cactus Jack
    python tools/poc_music_trap.py list       # song ids
"""
import importlib.util
import os
import sys
import time

_FF8_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ff8")
_spec = importlib.util.spec_from_file_location("ff8_memory", os.path.join(_FF8_DIR, "memory.py"))
memory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(memory)


def main(argv: list[str]) -> int:
    if argv and argv[0] == "list":
        for sid, name in sorted(memory.SONG_NAMES.items()):
            print(f"{sid:3d}  {name}{'  *' if sid in memory.JUKEBOX_SONGS else ''}")
        print("* = in the Jukebox trap's pool")
        return 0
    ff8 = memory.FF8Interface()
    if not ff8.attach():
        print(ff8.last_attach_error or "FF8_EN.exe is not running")
        return 1
    before = ff8.current_song()
    song = int(argv[0]) if argv else memory.pick_jukebox_song(before)
    print(f"module {ff8.read_u16(memory.MODULE_DISPATCH)}  ffnx music hook: {ff8.music_engine_hooked()}")
    print(f"now playing {before} ({memory.SONG_NAMES.get(before, '?')}) -> "
          f"asking for {song} ({memory.SONG_NAMES.get(song, '?')})")
    t0 = time.time()
    ok = ff8.play_song(song)
    time.sleep(0.2)
    after = ff8.current_song()
    print(f"play_song={ok} in {time.time() - t0:.3f}s; current slot now {after}")
    return 0 if ok and after == song else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

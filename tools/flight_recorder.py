"""FF8 playthrough flight recorder.

Runs alongside the game (and optionally the AP client) and logs EVERY savemap
change to an append-only JSONL file, so a single playthrough captures all the
data needed to verify offsets, pin story-moment thresholds, and diagnose any
check that misfired — without ever replaying. Purely read-only; safe to run
with the AP client attached at the same time.

Record (default):
    f:\\ff8_arch\\.venv\\Scripts\\python.exe tools\\flight_recorder.py
        [--out output/telemetry] [--hz 5]

Report (summarize a recording):
    ...python.exe tools\\flight_recorder.py --report output/telemetry/flight_XXX.jsonl
        [--offset 0x18FE944]   # history of one offset
        [--moments]            # game-moment timeline vs the story-check table
        [--battles]            # encounter log

What it records:
  - every byte change in the savemap span, annotated (grouped into runs,
    constantly-ticking offsets squelched after a threshold, squelch logged)
  - game-moment and field-ID transitions
  - battle start/end with encounter ID and win/loss classification
  - a full savemap snapshot every --snapshot-secs (default 300) and at every
    game-moment change, hex-encoded, so any later question can be answered
    from the recording

Crash-safe: every line is flushed on write; a killed recorder loses at most
one line. Restarting appends a new session header to a new file.
"""

import argparse
import base64
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import savemap_map as SM  # noqa: E402  (also loads ff8/memory.py AP-free)

M = SM.M
ROOT = SM.ROOT


class Recorder:
    def __init__(self, out_dir: Path, hz: float, snapshot_secs: float):
        self.ff8 = M.FF8Interface()
        self.period = 1.0 / hz
        self.snapshot_secs = snapshot_secs
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.path = out_dir / f"flight_{stamp}.jsonl"
        self.fh = self.path.open("a", encoding="utf-8", buffering=1)
        self.prev: bytes | None = None
        self.prev_field = None
        self.prev_moment = None
        self.battle_active = False
        self.encounter = 0
        self.party_alive_seen = False
        self.battle_wiped = False
        self.change_counts: Counter[int] = Counter()
        self.squelched: set[int] = set(SM.NOISY)
        self.last_snapshot = 0.0

    def emit(self, ev: str, **fields):
        rec = {"t": round(time.time(), 3), "ev": ev, **fields}
        self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def snapshot(self, buf: bytes, reason: str):
        self.emit("snapshot", reason=reason,
                  moment=self.prev_moment, field=self.prev_field,
                  data=base64.b64encode(buf).decode())
        self.last_snapshot = time.time()

    # ------------------------------------------------------------------
    def diff(self, old: bytes, new: bytes):
        """Emit annotated change runs; squelch offsets that never stop moving."""
        runs: list[tuple[int, int]] = []   # (start_index, end_index_exclusive)
        i, n = 0, len(new)
        while i < n:
            if old[i] == new[i]:
                i += 1
                continue
            j = i
            while j < n and old[j] != new[j]:
                j += 1
            runs.append((i, j))
            i = j
        for start, end in runs:
            base_off = M.SAVEMAP_BASE + start
            if all(M.SAVEMAP_BASE + k in self.squelched for k in range(start, end)):
                continue
            for k in range(start, end):
                self.change_counts[M.SAVEMAP_BASE + k] += 1
            newly_noisy = [off for off in (M.SAVEMAP_BASE + k for k in range(start, end))
                           if self.change_counts[off] > 200 and off not in self.squelched]
            for off in newly_noisy:
                self.squelched.add(off)
                self.emit("squelch", off=f"0x{off:X}", name=SM.annotate(off),
                          note="changed >200 times; further changes not logged")
            if all(off in self.squelched
                   for off in (M.SAVEMAP_BASE + k for k in range(start, end))):
                continue
            self.emit("change", off=f"0x{base_off:X}", name=SM.annotate(base_off),
                      old=old[start:end].hex(), new=new[start:end].hex(),
                      moment=self.prev_moment, field=self.prev_field,
                      in_battle=self.battle_active)

    def tick(self):
        buf = self.ff8.read_bytes(M.SAVEMAP_BASE, M.SAVEMAP_SIZE)
        field = self.ff8.read_u16(M.FIELD_ID)
        fighting = self.ff8.in_battle()  # module 3 (combat) or results pulse
        moment = int.from_bytes(
            buf[M.GAME_MOMENT - M.SAVEMAP_BASE:M.GAME_MOMENT - M.SAVEMAP_BASE + 2],
            "little")

        # battle tracking (mirrors the client's logic, purely observational)
        if fighting:
            self.encounter = self.ff8.read_u16(M.ENCOUNTER_ID)
            if not self.battle_active:
                self.emit("battle_start", enc=self.encounter,
                          moment=moment, field=field)
                self.party_alive_seen = False
                self.battle_wiped = False
            present = [(self.ff8.read_u16(M.BATTLE_ALLIES + i * M.ALLY_STRIDE + M.ALLY_CUR_HP),
                        self.ff8.read_u16(M.BATTLE_ALLIES + i * M.ALLY_STRIDE + M.ALLY_MAX_HP))
                       for i in range(M.ALLY_COUNT)]
            present = [(c, m) for c, m in present if m > 0]
            if any(c > 0 for c, _ in present):
                self.party_alive_seen = True
                self.battle_wiped = False
            elif present and self.party_alive_seen:
                self.battle_wiped = True
        elif self.battle_active:
            self.emit("battle_end", enc=self.encounter,
                      result="loss" if self.battle_wiped else "win",
                      moment=moment, field=field)
        self.battle_active = fighting

        if field != self.prev_field:
            self.emit("field", field=field, prev=self.prev_field, moment=moment)
            self.prev_field = field
        if moment != self.prev_moment:
            self.emit("moment", moment=moment, prev=self.prev_moment, field=field)
            self.prev_moment = moment
            self.snapshot(buf, "moment_change")

        if self.prev is not None:
            self.diff(self.prev, buf)
        else:
            self.snapshot(buf, "session_start")
        self.prev = buf

        if time.time() - self.last_snapshot > self.snapshot_secs:
            self.snapshot(buf, "periodic")

    def run(self):
        print(f"Recording to {self.path}")
        print(f"Waiting for {M.PROCESS_NAME}...")
        while True:
            if not self.ff8.attached:
                if self.ff8.attach():
                    self.emit("attach", base=f"0x{self.ff8.base:X}")
                    print("Attached. Recording. Ctrl+C to stop.")
                    self.prev = None
                else:
                    time.sleep(2)
                    continue
            try:
                self.tick()
            except Exception as e:
                self.emit("detach", error=type(e).__name__)
                print(f"Lost process ({type(e).__name__}); waiting to re-attach...")
                self.ff8.detach()
            time.sleep(self.period)


# ----------------------------------------------------------------------
def report(path: Path, offset: int | None, moments: bool, battles: bool):
    events = [json.loads(line) for line in path.open(encoding="utf-8")]
    print(f"{len(events)} events, "
          f"{sum(1 for e in events if e['ev'] == 'change')} changes, "
          f"{sum(1 for e in events if e['ev'] == 'snapshot')} snapshots")

    if moments:
        print("\n--- game-moment timeline (vs story-check table) ---")
        table = {v: name for v, name in SM.STORY_LOCATIONS}
        for e in events:
            if e["ev"] == "moment":
                stamp = time.strftime("%H:%M:%S", time.localtime(e["t"]))
                tag = ""
                for v, name in SM.STORY_LOCATIONS:
                    if (e.get("prev") or 0) < v <= e["moment"]:
                        tag += f"  <<< crosses {v} ({name})"
                print(f"{stamp}  {e.get('prev')} -> {e['moment']}"
                      f"  (field {e.get('field')}){tag}")

    if battles:
        print("\n--- battles ---")
        for e in events:
            if e["ev"] in ("battle_start", "battle_end"):
                stamp = time.strftime("%H:%M:%S", time.localtime(e["t"]))
                extra = f" result={e['result']}" if e["ev"] == "battle_end" else ""
                print(f"{stamp}  {e['ev']:12} enc={e['enc']}"
                      f" field={e.get('field')} moment={e.get('moment')}{extra}")

    if offset is not None:
        name = SM.annotate(offset)
        print(f"\n--- history of 0x{offset:X} ({name}) ---")
        for e in events:
            if e["ev"] != "change":
                continue
            start = int(e["off"], 16)
            size = len(e["new"]) // 2
            if start <= offset < start + size:
                stamp = time.strftime("%H:%M:%S", time.localtime(e["t"]))
                k = (offset - start) * 2
                print(f"{stamp}  {e['old'][k:k+2]} -> {e['new'][k:k+2]}"
                      f"  (moment {e.get('moment')}, field {e.get('field')},"
                      f" in_battle={e.get('in_battle')})")


def main():
    ap = argparse.ArgumentParser(description="FF8 playthrough flight recorder")
    ap.add_argument("--out", default=str(ROOT / "output" / "telemetry"))
    ap.add_argument("--hz", type=float, default=5.0, help="poll rate (default 5)")
    ap.add_argument("--snapshot-secs", type=float, default=300.0)
    ap.add_argument("--report", metavar="JSONL", help="summarize a recording instead")
    ap.add_argument("--offset", type=lambda s: int(s, 0),
                    help="with --report: history of one offset")
    ap.add_argument("--moments", action="store_true", help="with --report: moment timeline")
    ap.add_argument("--battles", action="store_true", help="with --report: battle log")
    args = ap.parse_args()

    if args.report:
        report(Path(args.report), args.offset, args.moments, args.battles)
        return
    Recorder(Path(args.out), args.hz, args.snapshot_secs).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nRecorder stopped.")

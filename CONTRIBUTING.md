# Contributing to FF8 Archipelago

Thanks for your interest! This project is in **open beta** — bug reports from real
playthroughs, playtesting, documentation fixes, and code contributions are all welcome.

## Ways to contribute

- **Bug reports** — use the issue templates. Always attach the client log
  (`logs/FF8Client_*.txt` in your Archipelago folder); it almost always contains the answer.
- **Playtesting** — playing a seed and reporting what felt wrong (logic, balance, pacing)
  is genuinely useful at this stage. Open a Discussion for impressions, an Issue for defects.
- **Docs** — the [Player Guide](docs/player-guide.md) and setup guide are player-facing;
  clarity fixes are easy first PRs.
- **Code** — see below.

## Development setup

1. Clone the [Archipelago source](https://github.com/ArchipelagoMW/Archipelago) at the
   **0.6.7** release tag (our declared minimum — see `ff8/archipelago.json`).
2. Junction/symlink (or copy) this repo's `ff8/` into Archipelago's `worlds/` directory.
3. From the Archipelago checkout, run `Generate.py` / `Launcher.py` from source as usual.

Run the test suite from the Archipelago checkout:

```
pytest worlds/ff8/test
```

CI runs the same suite on Python 3.11 and 3.13, plus a full apworld/tracker-pack build.
A PR must be green on all three jobs before it can merge.

## Ground rules

### Memory offsets and new checks must be evidence-backed

This is the one rule that isn't negotiable. The client works by reading the live savemap,
so a wrong offset silently corrupts someone's campaign. **Never guess an address.**

- Every existing check's field is documented in
  [docs/research/savemap-measurables.md](docs/research/savemap-measurables.md), with the
  reasons fields were accepted or rejected. Read it before proposing a new check.
- A new offset must be verified before it ships: against the offline save library
  (`tools/save_scan.py`) and/or the live self-test (`tools/live_selftest.py`) with the
  actual game. State the evidence in your PR — which saves/scenarios you verified against,
  and a source (ff8-memory, Hyne, qhimm research) if one exists.
- Fields that churn, alias between saves, or can't distinguish "earned" from "granted"
  belong in the REJECTED table with a reason, not in the location list.

### Regenerate the trackers with table changes

Any change to `ff8/items.py` or `ff8/locations.py` requires regenerating both tracker
packs in the same PR:

```
python tools/gen_tracker_pack.py
```

This rewrites the PopTracker pack (`tracker/ff8_ap_tracker/`) and the Universal Tracker
pages (`ff8/tracker/`). The test suite enforces table/tracker invariants and will fail if
they drift.

### Other conventions

- **No game assets or copyrighted data** in the repo — tables derived from community
  research are fine (credit the source), extracted game content is not.
- **Options changes** need matching updates to `ff8/docs/` (WebHost game info / setup
  guide) and the Player Guide where player-visible.
- **License**: contributions are MIT. The one exception in the tree is
  `tools/psx2steam.py` (GPL-3.0-or-later, ports Hyne's LZS codec) — don't move code
  across that boundary.

## Pull request process

1. Fork, branch from `main`, make your change.
2. Open a PR using the template. Keep PRs focused — one logical change each.
3. CI must pass (world tests on 3.11 and 3.13, apworld + tracker build).
4. **Every PR requires maintainer review and approval before merge** — `main` is
   protected. Expect review comments; contributions may also get an automated
   first-pass analysis before human review.

## Releases

Releases are maintainer-only: a version bump in `ff8/archipelago.json` plus a matching
`v*` tag triggers the CI release pipeline. Don't include version bumps or
`tracker/versions.json` entries in contribution PRs.

## Questions

Use [Discussions](https://github.com/wilsonao/ff8_arch/discussions) for setup help,
gameplay questions, and ideas that aren't yet concrete proposals. Issues are for
defects and specific, actionable suggestions.

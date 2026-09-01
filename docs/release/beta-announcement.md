# Final Fantasy VIII (Steam 2013) — Archipelago world, open beta

*Draft for the AP Discord `#future-game-design` thread / GitHub release notes. Not yet posted.*

**Game:** Final Fantasy VIII, Steam 2013 release (`FF8_EN.exe`). Not Remastered, not PSX.
**Type:** memory-hook client, no file patching — works alongside FFNx / Junction VIII
asset mods. **Status:** feature-complete for a first beta; one full campaign playthrough
in progress.

## What gets randomized

The story plays vanilla. The game's reward moments become checks and the client
intercepts what the vanilla game would hand you:

- **Core (always on):** all 16 GF acquisitions, story/boss beats, the Magical Lamp and
  Solomon Ring handouts, the five Laguna dreams.
- **Toggle groups:** draw points (99), Triple Triad (36 — wins ladder, unique cards, the
  whole CC Group, Garden wins, level sets, Random-rule abolition), optional bosses (34 —
  Odin, UFO/PuPu, castle bosses + seal ladder, Propagators, Ultima/Jumbo kills), rare
  cards (33), sidequests (63), magazines (19), stat ladders (36), **GF abilities (71 — signature abilities,
  "GF Mastered", party abilities-learned ladder; each GF's checks require that GF)**.
- **All on: 429 checks.**

Items: the 16 GFs (progression — the Disc 3 logic gate counts them, and GF ability checks
need their GF), Odin/Phoenix/Gilgamesh, the two key items, gil, consumables, magic stocks,
optional traps (Gil Snatch / Ambush / Magic Leak).

Options worth knowing: **Goal** (Ultimecia or Omega), **Starting GFs** (0–3), **GFs
Required for Disc 3**, **Magic Mode** (`checks_only`: draws yield nothing, every spell's
stock cap comes from the multiworld — the "Junction Master" preset), **Trap Chance**,
DeathLink.

## How it works / why you can trust it

- Every check is a state read of the live savemap where the game state allows it, so
  offline play catches up on reconnect; boss checks use the speedrun autosplitter's
  battle-victory pattern.
- Delivery state is stored **inside the save** (free field vars, inside the game's own
  checksum span): reload an older save or start a New Game and the client re-delivers
  exactly what that save lacks. A save from another seed is frozen, not mis-credited.
- Every savemap offset behind a check was verified offline against a 273-save library
  (GameFAQs PSX saves converted with our own tool + speedrun practice packs) before
  shipping; the client pipeline is exercised end-to-end by an automated live self-test
  (every trigger family, DeathLink both ways, win/loss credit, the Ultimecia goal).
- Trackers: a PopTracker pack (generated from the world tables — world map, region
  board, GF abilities tab) and Universal Tracker support with the same maps embedded in
  the apworld.

## Known limits (beta)

- Received items have no in-game text (no file patching in v1) — the client log and
  tracker show them.
- Research-gated content not yet included: Chocobo forests, Shumi Village, per-enemy
  scan checks (each needs one live memory diff we haven't captured yet).
- The Ultimecia goal has been verified live from a pre-castle save; the Omega goal uses
  the same battle tracker but has not had a live kill yet.

## Files

- `ff8.apworld` — drop into `custom_worlds/` (Archipelago 0.6.x, `minimum_ap_version`
  0.6.7). The FF8 Client appears in the Launcher.
- `ff8_ap_tracker.zip` — PopTracker pack.
- Setup guide and game page ship inside the apworld (WebHost).

Feedback / bug reports: GitHub issues on `wilsonao/ff8_arch`. Please include the client
log (`logs/FF8Client_*.txt`) and, for wrong/missed checks, the output of `/ff8missed`
and `/ff8verify`.

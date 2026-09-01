# Final Fantasy VIII — game-suggestion post (AP Discord format)

*Follows the server's "How to suggest a game" template. Paste as-is; Discord
renders the bold and bullets. Counts current as of 2026-09-01 (429 checks all-on).*

---

**Final Fantasy VIII (Steam 2013)**

Final Fantasy VIII, released in 1999 (PC port 2000, Steam re-release 2013), is a turn-based JRPG built around the Junction system: Guardian Forces are the real source of character power, and everything else — stats, abilities, elemental/status junctions — hangs off which GFs you own and which magic you've stocked. That makes it unusually well suited for randomization: the story is linear, but the *power* is fully modular, so shuffling GFs, key items, and magic into the multiworld changes how every fight plays without needing to touch the game's script. On top of the main line there is a huge amount of optional structure to hang checks on — ~100 draw points, a 110-card Triple Triad collection with its own questlines and rule-manipulation metagame, optional superbosses, magazines, limit-break sidequests, and a pile of lifetime counters the game already tracks.

There's an existing randomizer for the game, Maelstrom (open source, C#, file-patching), which covers boss/draw/shop shuffles but isn't multiworld-aware. The 2013 PC port is very approachable to work with: the entire live save state sits at static offsets in the game's memory (the speedrun community has documented the whole map — ff8-memory, the LiveSplit autosplitter), and the Hyne save editor is open source, so every field of the savemap is machine-readable. That means an Archipelago client can read checks and grant items externally, with no file patching, and it coexists with the FFNx / Junction VIII mod ecosystem.

**Status:** an apworld already exists and is in open beta — memory-hook client bundled in the apworld (no patching), PopTracker pack + Universal Tracker support, offsets verified against a 273-save library, one full campaign playthrough in progress. Repo: `wilsonao/ff8_arch` on GitHub.

Here's what's in as checks (429 total with every group on):
- All 16 Guardian Force acquisitions (study panel, boss draws, item GFs)
- Story and boss beats — the Dollet exam, the assassination attempt, the prison escape, the Battle of the Gardens, Adel, the five Laguna dreams, and more
- Key-item handouts (Magical Lamp, Solomon Ring)
- Draw-point-sanity — 99 named field draw points
- Triple Triad — win ladder, unique-card collection up to the full 110, the entire CC Group questline, Balamb Garden card wins, complete-the-level card sets, abolishing the Random rule region by region
- The 33 rare cards
- Optional bosses — Odin, the UFO/PuPu chain, every Ultimecia's Castle boss plus the seal ladder, the Ragnarok Propagators, Ultima Weapon and Jumbo Cactuar kills
- Sidequests — Quistis's blue magics, Zell's Duel finishers, Angelo's tricks, Timber Maniacs, Queen of Cards, Obel Lake, the SeeD written tests, weapon remodeling, the Phoenix and Gilgamesh cameos
- The 19 collectible magazines
- Stat ladders from the game's own lifetime counters — Squall's level, distinct magics drawn, enemies scanned, battles escaped, monsters felled, steps taken, Tonberries culled
- GF abilities — each GF's signature abilities, "GF Mastered", and a party-wide abilities-learned ladder

Here's what's in as items:
- The 16 Guardian Forces (progression — logic gates Disc 3 on a configurable GF count, and each GF's ability checks require that GF)
- Cameo GFs — Odin, Phoenix, Gilgamesh
- Key items — Magical Lamp, Solomon Ring
- Magic stocks (33 spell kinds; an optional "checks-only" magic mode makes the multiworld the *only* source of magic, so every spell's stock cap comes from the item pool)
- Consumables — potions, Phoenix Downs, Remedies, Elixirs, Tents/Cottages, refine materials
- Gil
- Optional traps — Gil Snatch, Ambush, Magic Leak

The goal is defeating Ultimecia at the end of her castle, with an alternate goal of beating Omega Weapon, the castle's optional superboss. DeathLink is supported both ways (a party wipe sends, a received death wipes your party at the start of your next battle).

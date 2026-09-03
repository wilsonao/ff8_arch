# FF8 Archipelago (ff8_arch)

An [Archipelago](https://archipelago.gg) multiworld randomizer world for
**Final Fantasy VIII (Steam 2013, `FF8_EN.exe`)**.

The story plays vanilla; the game's reward moments become multiworld checks, and a
bundled Python client hooks the game process to intercept vanilla rewards and deliver
multiworld items. **No game files are patched** — the client reads and writes the live
savemap, so it runs alongside FFNx / Junction VIII asset mods.

> **Players: start with the [Player Guide](docs/player-guide.md)** (requirements,
> options, how checks and items behave, saves, trackers, troubleshooting) and download
> `ff8.apworld` + the tracker pack from the [Releases](https://github.com/wilsonao/ff8_arch/releases)
> page. Status: **open beta**.

## What it randomizes

**580 checks across 10 groups** (core always on; the rest are per-player toggles,
all defaulting to on except the hidden world-map draw points):

| Group | Checks | What sends them |
|---|---|---|
| Core | 38 | all 16 GF acquisitions, story/boss beats, key-item handouts, 5 Laguna dreams |
| Draw points | 99 | first draw from every named field draw point |
| World draw points | 125 | first draw from every hidden world-map draw point — the tracker shows where they are, Islands Closest to Heaven/Hell included |
| Triple Triad | 36 | wins ladder, unique-card ladder, CC Group (all 8 incl. Joker), Garden wins, level sets, Random-rule abolition |
| Optional bosses | 34 | Odin, UFO/PuPu, castle bosses + seal ladder, Propagators, Ultima/Jumbo kills |
| Rare cards | 33 | every level 8–10 card |
| Sidequests | 67 | blue magic, Zell duels, Angelo tricks, Timber Maniacs ladder, chocobo forests, battles won, SeeD tests, weapon remodels, Obel Lake, Queen of Cards, cameos |
| Magazines | 37 | Weapons Monthly / Combat King / Pet Pals / Occult Fan / Girl Next Door, plus every Timber Maniacs issue at its pickup spot |
| Stat ladders | 40 | Squall's level, magics collected, marquee first draws, scans, escapes, kills, steps, Tonberries, SeeD rank |
| GF abilities | 71 | 49 signature abilities (Card Mod, Enc-None, Mug, the refines…), 16 "GF Mastered", party abilities-learned ladder |

Items: the 16 junctionable GFs (+ Odin/Phoenix/Gilgamesh cameos), the Magical Lamp and
Solomon Ring, gil, consumables, magic stocks (flat or progressive chains), character /
GF-ability / stat-junction / battle-command unlocks, and optional traps.

Gameplay options: **Goal** (Ultimecia or Omega Weapon), **Starting GFs**, a GF-count
logic gate for Disc 3, **Magic Mode** (`checks_only`: draws yield nothing — every spell's
cap comes from the multiworld) with **Starter Magic** and **Progressive Magic**, four
lock layers for the classic AP underdog opening (**Character**, **GF Ability**,
**Junction**, and **Command Locks** — junctions, commands, and signature abilities stay
revoked until their items arrive), **Trap Chance** (Gil Snatch / Ambush / Magic Leak),
DeathLink. WebHost presets: *All Checks*, *Core Only*, *Junction Master*, *SeeD Cadet*.

Every check is **state-based where the game state allows** (auto catch-up after offline
play), delivery state lives inside the save itself (reloads and New Game re-deliver
exactly what that save lacks), and foreign saves are frozen rather than mis-credited.

## Trackers

- **PopTracker**: `tracker/ff8_ap_tracker/` (zip in `build/`), fully generated from the
  world's own tables by `tools/gen_tracker_pack.py` — a stylized world map with inset
  panels, a region board, and a GF Abilities tab; AP autotracking reads option toggles
  and the Disc 3 threshold from slot data.
- **Universal Tracker**: supported out of the box (`ut_can_gen_without_yaml`,
  slot-data regeneration); the same three maps ship inside the apworld as UT map pages.

## Verification status

Every savemap offset behind a check was settled **offline** against a 273-save library
(`tools/save_scan.py`, PSX saves converted by `tools/psx2steam.py`) before shipping, and
the client pipeline is exercised end-to-end by `tools/live_selftest.py` against the
running game (all trigger families, DeathLink both directions, boss win/loss credit, goal
detection incl. a real Ultimecia kill). A full campaign playthrough with the flight
recorder (`tools/flight_recorder.py`) is in progress. Remaining research-gated content
and the burn-down log: [docs/verification-plan.md](docs/verification-plan.md);
the field-by-field survey of what is (and isn't) a check:
[docs/research/savemap-measurables.md](docs/research/savemap-measurables.md).

## Repository layout

```
ff8/                    the apworld package (world + client, ships as ff8.apworld)
  __init__.py           World definition (regions, rules, item pool, UT hooks, Launcher component)
  items.py              item table (GFs, key items, filler, magic roster, traps)
  locations.py          location table + client trigger metadata + hint groups
  options.py            player options, WebHost option groups + presets
  memory.py             FF8_EN.exe memory map, savemap snapshot, pymem interface
  client.py             AP client (CommonContext + game watcher + /ff8* commands)
  tracker/              generated Universal Tracker map pages
  test/                 world test suite (pytest; fill/logic/table/UT-regen invariants)
  docs/                 WebHost game info + setup guide
tracker/ff8_ap_tracker/ generated PopTracker pack
tools/                  generator, live self-test, flight recorder, save library tooling
docs/                   design doc, verification plan, sourced research
.github/workflows/      CI: world tests + apworld/tracker-pack build artifacts
```

## Development

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules
(evidence-backed offsets, tracker regeneration, PR review process).

Clone the [Archipelago source](https://github.com/ArchipelagoMW/Archipelago) (0.6.8),
junction/symlink `ff8/` into its `worlds/` directory, and run `Generate.py` / the
Launcher from source. Package with the Launcher's **Build APWorlds** component:

```
python Launcher.py "Build APWorlds" -- "Final Fantasy VIII" --skip_open_folder
```

Run the test suite from the Archipelago checkout:

```
pytest worlds/ff8/test
```

After any change to `items.py` / `locations.py`, regenerate the trackers:
`python tools/gen_tracker_pack.py` (writes the PopTracker pack, its zip, and
`ff8/tracker/` for Universal Tracker).

**Releasing:** bump `world_version` in `ff8/archipelago.json`, commit, then push a
matching tag (`git tag v0.1.1 && git push origin v0.1.1`). CI builds the apworld and
publishes a GitHub Release with `ff8.apworld` and `ff8_ap_tracker.zip` attached (a
tag with a suffix such as `v0.2.0-beta1` is marked pre-release). The release job
refuses tags that don't match `world_version`.

If the tracker pack changed, also prepend an entry to `tracker/versions.json`
(PopTracker's update feed) in the same commit: the pack's `package_version`, the
new release's `releases/download/<tag>/ff8_ap_tracker.zip` URL, a changelog, and
any placeholder `sha256`. The zip is regenerated in CI, so the release job
computes the real hash, rewrites the top entry, and pushes that back to main —
it fails (with the release left up) if the top entry's URL isn't this tag's.
PopTracker's pack list points at that file, so installed packs self-update.

## Credits

Memory research: [ff8-speedruns/ff8-memory](https://github.com/ff8-speedruns/ff8-memory),
[ff8-auto-splitter](https://github.com/ff8-speedruns/ff8-auto-splitter),
[Hyne](https://github.com/myst6re/hyne) (myst6re — save format, ability/card/monster
tables), the qhimm.com community, and the
[FF8 modding wiki](https://hobbitdur.github.io/FF8ModdingWiki/). Client architecture
follows the Kingdom Hearts 2 and FF12 Open World Archipelago clients. Save library:
GameFAQs contributors and the FF8 speedrunning community's practice packs.

## License

[MIT](LICENSE), with one exception: `tools/psx2steam.py` ports Hyne's LZS codec and
CRC table and is therefore GPL-3.0-or-later (full text in `tools/LICENSE.GPL-3.0`). It
is a development tool only and is not part of the shipped `ff8.apworld`. Final Fantasy
VIII is the property of Square Enix; this project contains no game assets.

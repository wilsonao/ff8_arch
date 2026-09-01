# Final Fantasy VIII Setup Guide

The complete player guide (every option, how checks and items behave, saves,
trackers, client commands, troubleshooting) lives on GitHub:
https://github.com/wilsonao/ff8_arch/blob/main/docs/player-guide.md — this
page is the short version.

## Requirements

- Final Fantasy VIII (Steam, **2013 release** — not Remastered), English version
  (`FF8_EN.exe`). Windows only (the client attaches to the game process).
- Archipelago 0.6.7 or newer: https://github.com/ArchipelagoMW/Archipelago/releases
- The `ff8.apworld` file for this world:
  https://github.com/wilsonao/ff8_arch/releases

## Installation

1. Open the Archipelago Launcher and choose **Install APWorld**, then select
   `ff8.apworld` (or drop the file into your Archipelago `custom_worlds` folder).
2. Restart the Launcher.

## Joining a multiworld

1. Create your options file (`Final Fantasy VIII.yaml`) via the Launcher's
   **Generate Template Options**, edit it, and give it to whoever is generating.
2. Start Final Fantasy VIII and begin a **New Game** (recommended — see below
   for existing saves).
3. In the Launcher, open **FF8 Client**, and connect it to the server
   (`/connect server:port`, then enter your slot name).
4. The client attaches to the running game automatically. `/ff8` in the client
   shows the game-connection status. If attaching fails, try running the
   Launcher as administrator.

## Good to know

- Items are delivered and checks are sent while you are on a **field screen**
  (not in menus or battles). There is no in-game message for received items —
  the client window and the tracker show them.
- Vanilla GF and key-item rewards are intercepted by the client shortly after the
  game grants them — a brief flash of the vanilla reward in menus is normal.
- Almost every check is read from the save state, so anything you earned while
  the client was closed is sent when you reconnect. The exceptions are events
  the client has to watch as they happen — **boss kills** and the **Magical
  Lamp / Solomon Ring handouts**; if it was closed then, `/ff8check <name>`
  sends the check by hand.
- Your item deliveries are tracked *inside each save file*: loading an older
  save re-delivers whatever that save is missing (GFs, key items, gil,
  consumables, magic — everything), and a New Game on the same slot receives
  everything again. A save from a different seed is frozen rather than
  credited; a save the campaign has never stamped that would send 8+ checks at
  once is held until you confirm it with `/ff8adopt`.
- **Draw Point Checks**: drawing from a named field draw point for the first
  time sends a check; one-time areas' points only hold filler.
- **Triple Triad Checks**: wins ladder, unique-card ladder up to 110, the whole
  CC Group (Discs 2-3 in Balamb Garden; the King's rematch is on the
  Ragnarok), Balamb Garden card wins, card-level sets, and abolishing the
  Random rule region by region.
- **Optional Boss Checks**: Odin, UFO sightings, UFO??, PuPu, the Ultimecia
  Castle bosses and seals, the Propagators, Ultima Weapon / Jumbo Cactuar kill
  checks. Omega Weapon only ever holds filler.
- **Rare Card Checks**: each rare card's first acquisition; losing it later
  costs nothing. Permanently-losable cards only hold filler.
- **Sidequest Checks**: blue magics, Zell's Duel finishers, Angelo's tricks,
  Timber Maniacs, the cameos, Queen of Cards, Obel Lake, battles won, SeeD
  tests, weapon remodels (ultimate weapons only hold filler).
- **Magazine Checks**: owning each magazine — they are never taken from you.
- **Stat Ladder Checks** (Squall's level, magics obtained, first draws of
  top-tier spells, scans, escapes, kills, steps, Tonberries) and **GF Ability
  Checks** (signature abilities, GF Mastered, abilities-learned ladder; a GF's
  checks need that GF) are all farmable, never missable.
- **Magic Mode `checks_only`**: magic stock comes only from multiworld items
  (each raises a spell's cap; excess drawn/refined stock is repossessed);
  `/ff8magic` shows stock vs. caps. **Trap Chance** replaces some filler with
  Gil Snatch / Ambush / Magic Leak — field-only, never lethal.
- **Point of no return**: once you commit to Disc 4, towns, Gardens, and shops
  are gone — only Ultimecia's Castle and a few wild areas remain. Collect what
  you want first.
- **DeathLink**: enabled via your options file; `/deathlink` toggles it
  mid-session. A death received while you're on the field is applied at the
  start of your next battle.
- Client commands: `/ff8` (status), `/ff8missed` (diagnose unchecked
  locations), `/ff8check <name>` (manual send for a missed watch-only check),
  `/ff8adopt` (accept a held/foreign save), `/ff8magic`, `/deathlink`,
  `/ff8verify` (raw values for bug reports).

## Tracking (optional)

A [PopTracker](https://github.com/black-sliver/PopTracker) pack with full
Archipelago autotracking is available (`ff8_ap_tracker.zip`, same release
page): drop it into PopTracker's `packs/` folder, pick **Final Fantasy VIII
(Archipelago)**, and connect the built-in **AP** autotracker with your slot
name. It marks checks and received GFs/key items automatically, follows your
story progress, and picks up your check-group options and the Disc 3
GF-requirement from your slot. Four tabs: a stylized world map, a region
board, quests & extras, and a GF Abilities grid.

[Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases)
works with no extra files: the world regenerates from your slot data, and the
same maps ship inside `ff8.apworld` as UT map pages.

# Final Fantasy VIII Setup Guide

## Requirements

- Final Fantasy VIII (Steam, **2013 release** — not Remastered), English version
  (`FF8_EN.exe`).
- Archipelago 0.6.7 or newer: https://github.com/ArchipelagoMW/Archipelago/releases
- The `ff8.apworld` file for this world.

## Installation

1. Open the Archipelago Launcher and choose **Install APWorld**, then select
   `ff8.apworld` (or drop the file into your Archipelago `custom_worlds` folder).
2. Restart the Launcher.

## Joining a multiworld

1. Create your options file (`Final Fantasy VIII.yaml`) via the Launcher's
   **Generate Template Options**, edit it, and give it to whoever is generating.
2. Start Final Fantasy VIII and load into a save (a fresh game is recommended —
   see the caveats below).
3. In the Launcher, open **FF8 Client**, and connect it to the server
   (`/connect server:port`, then enter your slot name).
4. The client attaches to the running game automatically. `/ff8` in the client
   shows the game-connection status. If attaching fails, try running the
   Launcher as administrator.

## Good to know

- Play in the same session as the client; checks and items are exchanged live while
  you are on a field screen (not in menus or battles).
- Reloading an older save: your GFs and key items are re-delivered automatically,
  but gil/consumable rewards already delivered are not re-sent (the client warns
  when it notices a save well behind your furthest progress).
- Vanilla GF and key-item rewards are intercepted by the client shortly after the
  game grants them — a brief flash of the vanilla reward in menus is normal.
- With **Draw Point Checks** on, drawing from a visible field draw point for the
  first time sends a check. Draw points in one-time areas (D-District Prison,
  Missile Base, Galbadia Garden, White SeeD Ship, Lunar Base, the Lunatic Pandora
  Laboratory dream) only ever hold filler, so missing them is harmless.
- With **Triple Triad Checks** on, card wins count toward a 5/15/30/60/100-win
  ladder, your collection counts toward a 10/20/35/50/70 unique-cards ladder,
  and each CC Group member you beat is a check (the quest runs in Balamb
  Garden on Discs 2-3; the King's rematch happens on the Ragnarok).
- With **Optional Boss Checks** on, Odin, the four UFO sightings, the UFO??
  fight, PuPu, the Ultimecia Castle bosses, and the eight Ragnarok Propagators
  are checks, and Ultima Weapon and Jumbo Cactuar give a kill check on top of
  their GF checks. Omega Weapon is included too, but only ever holds filler —
  skipping it costs nothing important.
- With **Rare Card Checks** on, obtaining each of the 33 rare cards is a check.
  The permanently-losable ones (Angelo, Shiva, Laguna, Gilgamesh) only hold
  filler. Losing a card to an NPC after its check fired costs you nothing.
- With **Sidequest Checks** on, learning Quistis's blue magics and Angelo's
  tricks, collecting Timber Maniacs issues, summoning Phoenix, and Gilgamesh's
  arrival are checks (the latter two only hold filler — they're luck- or
  Odin-gated), along with a 25/50/100/200 battles-won ladder, the SeeD written
  tests (levels 5/10/20/30, taken from the in-game Test menu), and weapon
  remodeling (each character's first remodel; the six ultimate weapons only
  hold filler — no forced grinding).
- With **Magazine Checks** on, having each collectible magazine in your
  inventory is a check (Weapons Monthly, Combat King, Pet Pals, Occult Fan,
  Girl Next Door). Magazines are never taken from you — Combat King and Pet
  Pals still teach limits as normal. Issues from one-time areas only hold
  filler.
- **Point of no return**: once you commit to Disc 4, only Ultimecia's Castle (and
  its draw points) remains reachable — collect everything else you want first.
- **DeathLink**: enabled via your options file; `/deathlink` in the client toggles
  it mid-session. A death received while you're on the field is applied at the
  start of your next battle.
- Useful client commands: `/ff8` (connection + progress status), `/deathlink`,
  `/ff8missed` (diagnose unchecked locations — shows any whose in-game
  condition already reads satisfied), `/ff8check <name>` (manually send a
  check the client provably missed, e.g. a boss killed while disconnected),
  `/ff8verify` (raw memory values, for debugging/research).
- Your multiworld item deliveries are tracked *inside each save file*: loading
  an older save re-delivers whatever that save is missing, and a new game on
  the same slot receives everything again. You never lose items to a reload.

## Tracking (optional)

A [PopTracker](https://github.com/black-sliver/PopTracker) pack with full
Archipelago autotracking is available (`ff8_ap_tracker.zip`): drop it into
PopTracker's `packs/` folder, pick **Final Fantasy VIII (Archipelago)**, and
connect the built-in **AP** autotracker to the server with your slot name. It
marks checks and received GFs/key items automatically, follows your story
progress, and picks up every check-group option and the Disc 3 GF-requirement
from your slot. Its three tabs are a stylized world map, a region board, and a
GF Abilities grid (one column per GF).

[Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases)
works with no extra files: the world regenerates from your slot data, and the
same three maps ship inside `ff8.apworld` as UT map pages.

# Final Fantasy VIII — Archipelago Player Guide

This is the full guide to playing *Final Fantasy VIII* (Steam 2013) in an
[Archipelago](https://archipelago.gg) multiworld with this apworld. The short
version ships inside the apworld as the WebHost setup page; this page has the
whole story: options, how checks and items behave in-game, saves, trackers,
client commands, and troubleshooting.

**Status: open beta.** Every check has been verified against real save data
and the client pipeline has been exercised end-to-end, but only one full
campaign playthrough has been completed. Please report anything odd (see
[Reporting problems](#reporting-problems)).

---

## 1. What this does

The story plays exactly as vanilla. What changes is what you *get*:

- The game's reward moments become **checks** — GF acquisitions, story and
  boss beats, key-item handouts, and (per your options) draw points, Triple
  Triad, optional bosses, rare cards, sidequests, magazines, stat ladders, and
  GF abilities. Up to **429 checks** with every group on.
- The rewards themselves go into the multiworld **item pool**: the 16
  Guardian Forces, the cameo GFs (Odin, Phoenix, Gilgamesh), the Magical Lamp
  and Solomon Ring, gil, consumables, magic stocks, and optional traps.
- A **client** bundled in the apworld attaches to the running game, watches
  the live save state to detect checks, intercepts the vanilla rewards, and
  writes what the multiworld sends you straight into the game.

Nothing in the game's files is patched. The client reads and writes the game
process's memory, so it runs alongside FFNx / Junction VIII asset mods.

## 2. Requirements

| | |
|---|---|
| **Game** | *Final Fantasy VIII* — the **Steam 2013 release**, English (`FF8_EN.exe`). **Remastered is not supported**, and neither are the PSX version or the non-English executables (their memory layouts differ). |
| **OS** | Windows (the client attaches to the game process with `pymem`). |
| **Archipelago** | 0.6.7 or newer — [releases](https://github.com/ArchipelagoMW/Archipelago/releases). |
| **This world** | `ff8.apworld` from the [Releases page](https://github.com/wilsonao/ff8_arch/releases). |
| **Optional** | `ff8_ap_tracker.zip` (PopTracker pack) from the same release; [PopTracker](https://github.com/black-sliver/PopTracker) or [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases). |

Mods: graphics/music/texture mods (FFNx, Junction VIII asset mods) are fine.
Avoid gameplay mods that change encounters, drops, draw points, or the save
layout — the client's check detection assumes vanilla game data.

## 3. Installation

1. Open the Archipelago **Launcher** → **Install APWorld** → pick
   `ff8.apworld`. (Or copy the file into your Archipelago `custom_worlds/`
   folder.)
2. Restart the Launcher. **FF8 Client** now appears in its list, and
   *Final Fantasy VIII* is available when generating template options.
3. Optional — PopTracker: drop `ff8_ap_tracker.zip` into PopTracker's
   `packs/` folder.

## 4. Your options file

Generate a template with the Launcher's **Generate Template Options** (or
through the WebHost's options page once the world is hosted there). Every
option, with what it actually does:

### Logic

- **Goal** — `ultimecia` (default): beat Ultimecia at the end of her castle.
  `omega`: beat Omega Weapon, the castle's optional superboss — shorter, much
  harder, and you don't have to finish the story afterwards.
- **Starting GFs** (0–3, default 2) — random GFs precollected at the start.
  With 0 you cannot junction at all until the multiworld sends one, which makes
  the opening hours genuinely hard.
- **GFs Required for Disc 3** (0–12, default 6) — a *logic* setting only. The
  generator won't expect you to do Disc 3 checks until you've received this
  many GF items; the game itself never blocks you.

### Gameplay

- **Magic Mode** — `vanilla` (default): draw points, battle draws, and
  refining stock magic as normal. `checks_only`: multiworld magic items are the
  **only** source of stock. Each magic item raises your cap for one spell and
  the client repossesses anything above a cap within a second — draw points
  still send their checks and draw-based stat ladders still count, but the
  drawn stock vanishes (unless it's refilling a spell you've cast back up to
  its cap). Refining magic is repossessed the same way and the refined items
  are still consumed, so don't. You start with a small kit (Cure, Fira,
  Blizzara, Thundara, Sleep) and the filler pool switches to a much wider
  magic roster. Your junction strength is decided by the multiworld, not the
  draw grind. `/ff8magic` in the client shows your stock vs. caps.
- **Trap Chance** (0–100 %, default 0) — the share of filler replaced by
  traps: **Gil Snatch** (up to 1500 gil), **Ambush** (whole party to 1 HP —
  heal before your next fight), **Magic Leak** (10 of your most-stocked spell
  vanish; in checks-only mode the cap stays, so it can be redrawn). Traps
  apply on the field, never mid-battle, and none can KO you or soft-lock.
- **DeathLink** — see [section 9](#9-deathlink).

### Check groups

Core checks (GF acquisitions, story/boss beats, key items, the five Laguna
dreams) are always on. Each group below is a toggle; "filler only" means those
locations are excluded from holding progression, so missing them never strands
another player.

- **Draw Point Checks** (99) — first draw from each named field-screen draw
  point. Hidden world-map points aren't included. The ones in one-window areas
  (D-District Prison, Missile Base, Galbadia Garden, White SeeD Ship, Lunar
  Base, the Lunatic Pandora Laboratory dream) are filler only.
- **Triple Triad Checks** (36) — a total-wins ladder (5–100), a unique-card
  collection ladder (10–110), all eight CC Group members (Jack through King,
  Joker included — the quest runs in Balamb Garden on Discs 2–3, the King's
  rematch on the Ragnarok), a Balamb Garden card-wins ladder (15/40/100),
  seven "Card Compendium" level sets (all 11 cards of each common level), and
  abolishing the **Random** rule in Dollet, Trabia, Centra, and Lunar Gate
  (plus a "Random Rule Extinct" capstone for all of them). Filler only: the
  110-card tier, the Level 5 set (PuPu's card is a one-chance reward), the
  Lunar Gate abolition, and the capstone.
- **Optional Boss Checks** (34) — Odin, the four UFO sightings, the UFO??
  fight, PuPu, the eight Ultimecia's Castle bosses plus a seal-broken ladder,
  the eight Ragnarok Propagators, and separate kill checks for Ultima Weapon
  and Jumbo Cactuar (their GF draws are core checks already). Omega Weapon is
  included but filler only.
- **Rare Card Checks** (33) — obtaining each level 8–10 card for the first
  time. Losing a card to an NPC afterwards costs nothing. Cards whose holder can
  leave the game for good (Angelo, Shiva, Laguna, Gilgamesh) are filler only.
- **Sidequest Checks** (63) — Quistis's blue magics, Zell's Duel finishers
  (taught by Combat King issues), Angelo's tricks (Pet Pals), a Timber Maniacs
  collection ladder, Phoenix's first summon and Gilgamesh's arrival (both
  filler only — luck- and Odin-gated), the Queen of Cards chain (filler only),
  the Obel Lake milestones, a battles-won ladder (25–200), the SeeD written
  tests (levels 5/10/20/30, taken from the in-game Test menu), and weapon
  remodeling (each main character's first remodel; the six ultimate weapons are
  filler only).
- **Magazine Checks** (19) — having each collectible magazine in your
  inventory (Weapons Monthly, Combat King, Pet Pals, Occult Fan, Girl Next
  Door). Magazines are never taken from you — Combat King and Pet Pals still
  teach limits. Issues from one-time areas are filler only.
- **Stat Ladder Checks** (36) — read straight from the game's lifetime
  counters: Squall's level (10–40), distinct magics obtained (5–40 kinds),
  first-time draws of eight top-tier spells (Ultima, Meteor, Holy, Flare,
  Quake, Tornado, Triple, Aura), enemies scanned (5–30), battles escaped
  (5–30), monsters felled (50–500), steps taken (20k–300k), and Tonberries
  culled (5–20). Everything here is farmable at any point.
- **GF Ability Checks** (71) — 49 signature abilities (the refines, Enc-None,
  Mug, Card Mod, the stat Bonuses, Tonberry's shop tricks, the Auto-abilities
  …), a **Mastered** check per GF for learning all 22 of its abilities, and a
  party-wide abilities-learned ladder (10–200; the 200 tier is filler only).
  A GF's checks are in logic only once you hold that GF. Ability-teaching
  items count.

### Presets

The WebHost offers three one-click presets: **All Checks**, **Core Only**,
and **Junction Master** (everything on, no starting GFs, Disc 3 gated behind
12 GFs, checks-only magic).

### Example

```yaml
name: YourName
game: Final Fantasy VIII

Final Fantasy VIII:
  goal: ultimecia
  starting_gfs: 2
  gfs_required_for_disc3: 6
  magic_mode: vanilla
  trap_chance: 0
  draw_point_checks: true
  triple_triad_checks: true
  optional_boss_checks: true
  rare_card_checks: true
  sidequest_checks: true
  magazine_checks: true
  stat_checks: true
  gf_ability_checks: true
  death_link: false
```

## 5. Starting a game

1. Have the multiworld's server running (or the room open on the WebHost).
2. Launch *Final Fantasy VIII* as you normally do (Steam, or through Junction
   VIII) and **start a New Game**. A fresh game is strongly recommended — see
   [Saves](#8-saves-and-reloading) for why and for what happens with an
   existing save.
3. Open the client. If the game is hosted on a WebHost (archipelago.gg or a
   self-hosted one), click **your slot name** in the room page's player list:
   the Launcher opens, asks which client to use — pick **FF8 Client** — and the
   client starts already pointed at the right server, port, and slot. Otherwise,
   Launcher → **FF8 Client**, enter the server address (`host:port`) at the top
   or type `/connect host:port`, then your slot name.

   Either way, give the client window **up to a minute** to appear: Archipelago
   starts the client as a fresh process that reloads every installed world
   first, and antivirus scans can stretch that on the first launch. The
   Launcher shows a "FF8 Client is starting" note so you know the click
   registered — don't click again while you wait, or you'll get two clients.
4. The client finds `FF8_EN.exe` on its own and attaches; if the game isn't
   running yet it keeps retrying. `/ff8` shows the connection status. If it
   can't attach, it says why (Remastered running, a non-English executable,
   only the launcher open, or blocked memory access) — follow that message.
5. Play. Your starting GFs (if any) and anything already sent to you arrive on
   your first field screen after the opening.

Keep the client running while you play. Almost everything catches up
automatically if it wasn't, but a few events are only visible as they happen —
see the next section.

## 6. How it plays

**Items arrive on field screens.** The client only touches the game when you're
on a field screen — never in a menu, a battle, or the world map's battle
transition. Walk out of a menu and pending items land within a second. The game
shows **no in-game message** for received items (no file patching in this
version): the client window and your tracker are where you see them, and the
client log colors them by importance.

**Vanilla rewards get intercepted.** When the game hands you a GF or one of the
two key items, you may see it flash into your menu for a moment before the
client removes it and sends the check. That's normal. What you actually keep
comes from the multiworld.

**Most checks catch up on their own.** Draw points, story beats, ladders,
cards, magazines, abilities, GF acquisitions — all of these are read from the
save state, so if you played for an hour with the client closed, reconnecting
sends everything you earned. The exceptions are events the client has to
*watch*: **boss kills** (optional-boss and story-boss checks) and the **two
key-item handouts** (Cid's Magical Lamp, the Solomon Ring at Tears Point). If
the client was closed at that moment, `/ff8check <name>` sends the check by
hand — it's meant exactly for this.

**Point of no return.** Once you commit to Disc 4 (after Lunatic Pandora and
Adel), towns, the Gardens, and shops are gone; only Ultimecia's Castle and a
few wild areas remain reachable. Collect what you want first. The castle's own
checks (bosses, seals, draw points, the armory magazine) stay available.

**Goal.** With the Ultimecia goal the client sends your completion the moment
the final battle ends with your party alive; with the Omega goal, when Omega
Weapon dies. No manual step.

## 7. Tips per group

- **Draw points refill.** A point you drew once has sent its check; whether it
  refills later doesn't matter. Drawing a point the client never saw (offline)
  still counts as long as it hasn't refilled to full by the time you reconnect —
  and if it has, drawing it again sends it.
- **Cards you lose still count.** Rare-card and compendium checks fire on the
  first time you *obtain* a card. Losing it to an NPC afterwards is fine.
- **Rule abolition** is detected the moment a region's Random rule is gone —
  spreading other rules there doesn't undo it, and "Random Rule Extinct" means
  no region anywhere carries Random, spread copies included.
- **Stat ladders** all read lifetime counters. Nothing decays, nothing is
  missable, and none of them can be pushed backwards by reloading a save except
  by loading a genuinely older save.
- **GF abilities** — a GF the multiworld sends you arrives with its normal
  default learned set; the checks are for what you (or ability items) teach it
  beyond that. Forgetting an ability with Amnesia Greens doesn't un-send a
  check.
- **Checks-only magic** — draw whatever you like for the draw-point checks and
  the "First Draw" checks; the stock evaporates, the checks stay. Casting
  spends stock normally, and you can draw a cast spell back up to its cap.

## 8. Saves and reloading

Your multiworld progress is stored **inside each save file** (in unused
save-variable space the game itself checksums and preserves), stamped with
your seed and slot. That gives you:

- **Reloading an older save re-delivers exactly what that save is missing** —
  GFs, key items, gil, consumables, magic, everything. You never lose items to
  a reload.
- **Starting a New Game on the same slot** receives everything again from
  item 1.
- **Checks already sent stay sent.** Reloading a save from before a check
  doesn't un-send it (Archipelago never takes checks back).

Two guard rails protect you from crediting the wrong save:

- A save stamped by a **different seed or slot** (another campaign, a test
  seed) is **frozen**: no checks sent, no items granted, and the client says
  so. Load the right save, or `/ff8adopt` to claim it for this campaign (its
  old stamp is discarded and delivery restarts from item 1).
- A save with **no stamp** that would send **8 or more checks at once** (a
  library save, someone else's file, or your own long offline session) is
  **held** and the client asks you to confirm. If it's genuinely your progress,
  `/ff8adopt` sends the held checks. This trips exactly once after a long
  offline session — that's by design.

Steam Cloud can stay on; the client never writes save files, only the running
game's memory.

## 9. DeathLink

Turn it on in your options (`death_link: true`) or toggle it mid-session with
`/deathlink`. A full party wipe in battle sends a death to the other linked
players. A death you receive wipes your party — immediately if you're in a
battle, otherwise at the start of your next one. Your own DeathLink deaths are
never credited as boss wins, and a received death never echoes back.

## 10. Trackers

**PopTracker** — install the pack (section 3), pick *Final Fantasy VIII
(Archipelago)*, then choose **AP** in the autotracking menu at the bottom and
enter the server, slot, and password. The pack marks checks as you send them,
toggles GFs and key items as they arrive, infers your story progress from the
story beats you've checked, and reads your slot's options (which check groups
are on, the Disc 3 GF requirement) so it shows exactly your world. Four tabs:
a stylized **World Map** with pins at each check's real location and inset
panels for interiors, a **Region Board** in story order, **Quests & Extras**
for the check sets that aren't places, and **GF Abilities** (one column per
GF). The World Map has per-area sub-tabs (Balamb, Galbadia, Trabia, Esthar,
Centra, Space, Castle) besides the full view — and while the client is
running, the map **follows the player**: it jumps to the area your party is
in as you travel (the `»` toggle in the item row turns this off). Everything
also works manually without a connection.

**Universal Tracker** — works with no extra files: the world regenerates from
your slot data, and the same maps ship inside `ff8.apworld` as map pages.

## 11. Client commands

| Command | What it does |
|---|---|
| `/ff8` | Connection and progress status: attached?, game moment, field, safe-to-write, checks sent, items delivered to this save, DeathLink state. |
| `/ff8missed` | Diagnoses unchecked locations: how many are simply not met yet, how many are watch-only (boss kills, handouts), and lists any whose in-game condition already reads as satisfied (those should send within a second — if they don't, that's a bug report). |
| `/ff8check <name>` | Sends a check by (partial) location name. For a watch-only event the client provably missed, e.g. a boss killed while it was closed. |
| `/ff8adopt` | Accepts a held or foreign save into this campaign (see [Saves](#8-saves-and-reloading)). |
| `/ff8magic` | Checks-only magic mode: your current stock vs. granted cap per spell. |
| `/deathlink` | Toggles DeathLink for this session. |
| `/ff8verify` | Dumps raw memory values behind the checks. For bug reports and research. |

Plus all the standard Archipelago client commands (`/connect`, `/received`,
`/missing`, `/hint`, …).

## 12. Troubleshooting

**"Not attached to FF8_EN.exe."** The game isn't running, or it isn't the
Steam 2013 English version. The client names what it actually found: FF8
Remastered, a non-English 2013 executable, or just the launcher sitting open.
If `FF8_EN.exe` *is* running but can't be opened, some antivirus/UAC setups
block reading another process's memory — the client says so, and running the
Archipelago Launcher as administrator is the usual fix.

**"Attached, but reads are failing (game closed?)"** The game just exited or is
mid-restart; the client re-attaches on its own within a few seconds ("Lost FF8
process … re-hooking").

**Items aren't showing up.** Get to a field screen and out of every menu — the
client waits for that. Then check `/ff8` for "safe=True". If the client says
the save is **HOLDING** or **frozen**, read the message: you're on a save from
another campaign or an unstamped save, and `/ff8adopt` is the answer if it's
really yours.

**A check didn't send.** `/ff8missed` first. If it lists the location as
"satisfied but unsent", report it. If the location is watch-only (a boss kill
or a key-item handout) and the client wasn't running at the time,
`/ff8check <name>`.

**"This save is well behind the furthest point this slot has reached."** Just
a heads-up that you loaded an older save; items are re-delivered
automatically, nothing to do.

**DeathLink didn't fire.** Sends happen only on a *full* party wipe in battle
(not a Game Over from a scripted timer). Received deaths land at your next
battle if you're on the field.

**Logs.** `logs/FF8Client_*.txt` inside your Archipelago folder. Attach the
current one to any bug report.

## 13. Known limitations (beta)

- No in-game text for received items — the client and trackers show them.
- English `FF8_EN.exe` only; Remastered and PSX are not supported.
- Not yet checks (research still pending): the Chocobo forests, the Shumi
  Village quest, and per-enemy Scan checks.
- The Ultimecia goal has been verified live; the Omega goal uses the same
  battle tracker but hasn't had a live kill yet.

## Reporting problems

Open an issue at https://github.com/wilsonao/ff8_arch/issues with:

- the client log (`logs/FF8Client_*.txt`),
- for a wrong or missing check: the output of `/ff8missed` and `/ff8verify`,
- what you were doing in-game at the time (screen, disc, roughly where in the
  story).

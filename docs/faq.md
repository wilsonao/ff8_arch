# Final Fantasy VIII Archipelago — FAQ

The options page keeps each setting to a sentence or two. This page is the
long version: what every option really does, why the defaults are what they
are, and the questions beta players asked most. For installation, connecting,
client commands and troubleshooting step by step, see the
[Player Guide](player-guide.md).

---

## Words you will see

- **Multiworld** — several players' games generated together. Each game's
  rewards are shuffled into one shared pool, so beating a boss in FF8 might
  send a sword to someone's Zelda, and your Ifrit might be sitting in their
  dungeon.
- **Check** (also *location*) — a spot in the game that holds one item from
  the pool. Reaching it (drawing from a draw point, beating Odin, learning
  Mug) "sends" whatever was placed there to its owner.
- **Item** — anything the pool can hand you: a Guardian Force, magic stock,
  a junction right, gil, a trap.
- **Progression item** — an item that can open up more checks (a GF, a
  junction, a key). **Filler** is everything else (consumables, gil). A check
  marked **filler only** never holds progression, so missing it costs nobody
  anything.
- **Logic** — the generator's model of what you can reach with what you
  hold. "In logic" means the generator considers a check reachable right now;
  it never stops you from going there anyway. Logic exists so nobody's
  progression gets placed somewhere unreachable.
- **Sphere** — a step of the multiworld. Sphere 1 is everything reachable
  from a fresh start; sphere 2 is what the items in sphere 1 open; and so on.
  Many small spheres means a seed that keeps unfolding; one giant sphere 1
  means most of the game is open before anyone sends you anything.
- **Seed** — one generated multiworld. **Slot** — your game inside it.
- **YAML** (options file) — the text file where you pick your settings
  before generation. The WebHost's options page writes it for you.
- **Preset** — a bundle of option values you can pick in one click.
- **Client** — the program (Launcher → FF8 Client) that attaches to the
  running game, detects your checks, and writes received items into it.
- **DeathLink** — opt-in: your party wipes are shared with other DeathLink
  players, and theirs with you.
- **Story moment** — the game's own story-progress number. Several options
  below mention it because FF8 decides from it which towns exist yet.

---

## Getting started

**Which version of the game?** The Steam 2013 release, English
(`FF8_EN.exe`). FF8 Remastered, the PlayStation version, the 2000 PC release
(`FF8.exe`) and non-English executables are not supported: the client reads
the game's memory and their layouts differ.

**Windows only?** Yes. The client attaches to the game process.

**Does it change the game's files?** No. Nothing is patched. The client reads
and writes the running game's memory, so it sits alongside FFNx, Junction
VIII, and texture or music mods. Avoid gameplay mods that change encounters,
drops, draw points, or the save layout: check detection assumes vanilla data.

**Can I use the Steam boosters (speed-up, etc.)?** Yes, and the speed-up is
recommended in a multiworld. The client does not care about game speed.

**Can I play with Maelstrom (the standalone FF8 randomizer)?** Mostly. Boss
shuffle, draw-point shuffle, shop, loot, weapon, price and music shuffles are
fine. Card shuffle needs `rare_card_checks: false`. GF ability shuffle is not
supported. Free Roam never. Run Maelstrom first with "Set Seed" checked, then
the AP client. Details in the
[Player Guide](player-guide.md#playing-with-maelstrom).

**My controller does nothing, or the buttons are scrambled.** That is the
2013 port, with or without Archipelago: it is known for poor controller
detection. What has worked for players: plug the controller in before
starting the game (one connected afterwards is ignored until a restart); in
the game's launcher, open Settings, then the Controller tab, and press Reset
to Default; and in Steam's controller settings for the game, try another
Steam Input layout if the buttons are still wrong.

**How long is a run?** A full run to Ultimecia is 30 to 40 hours even with the
speed booster. The `edea` goal is about 8 hours. In a public multiworld where
others wait on your sends, pick the **Sync** preset.

**Does the story change?** No. FF8 decides per entrance from the story moment
whether a town exists yet, so warps and an early Ragnarok get you around the
map, not around the plot. You play the whole story in order.

**Is this stable?** Open beta. Every check was verified against real save
data and the client is exercised end to end, but a handful of full
playthroughs have been done. Options marked **Experimental** have had less
live play. Report anything odd on
[GitHub issues](https://github.com/wilsonao/ff8_arch/issues).

---

## Choosing options

**Why am I so weak with the defaults?** By design. Out of the box you start
with checks-only magic and all four lock layers on (character, GF ability,
junction, command) plus progressive magic. That is the classic Archipelago
"start weak and get rebuilt by the multiworld" experience.

**I just want to play FF8 with checks.** Use the **Relaxed** preset: every
check group on, every lock off, vanilla magic, generous starter kit.

**I want it short.** **Disc One Rush** (the `edea` goal, every check group on)
or **Sync** (the `edea` goal, only on-path checks, no traps, big locks off).

**I want the hardest thing.** **SeeD Cadet**: every lock on, progressive
checks-only magic, no starter kit, one GF. **Junction Master** is a step
below: no starting GFs, Disc 3 behind 12 GFs.

**Do I need every check group on?** No, except on the `edea` goal, where the
world is Disc 1 only and still has to hold all the lock items. With too few
groups on, generation stops and says what to turn on.

---

## Options in detail

### Logic

**Goal** (`goal`: `ultimecia` / `omega` / `edea`, default `ultimecia`)

- `ultimecia`: beat Ultimecia at the end of her castle, the vanilla ending.
- `omega`: beat Omega Weapon, the castle's optional superboss. Shorter but
  much harder, and the story does not need to be finished afterwards.
- `edea`: beat Sorceress Edea at the Deling City parade. The game ends with
  Disc 1 and everything past it is removed from the world, so no Disc 2+
  checks exist. The smaller world still has to hold every lock item, so keep
  most check groups on. **GFs Required for Disc 3** is ignored on this goal.

**Starting GFs** (`starting_gfs`: 0–3, default 1)

Random GFs placed in your starting inventory. Without a GF you cannot
junction anything, so 0 makes the opening hours genuinely hard until the
multiworld sends one.

**GFs Required for Disc 3** (`gfs_required_for_disc3`: 0–12, default 6)

A logic setting only; the game never blocks you. The generator will not
expect you to do Disc 3 checks until you have received this many GF items.
With Story Gates on it anchors the whole ladder: every earlier and later
chapter's GF requirement scales from it. 12 doubles every step; 0 removes
the GF requirement entirely.

**Story Gates** (`story_gates`: `off` / `normal` / `tight`, default `normal`)

The story is split into 18 chapters: Balamb Prologue, Fire Cavern, Dollet,
SeeD, Timber, Galbadia, D-District Prison, Missile Base, Garden Revolt,
Fisherman's Horizon, Balamb Liberation, Garden War, Edea's House, Esthar,
Lunar Base, Sorceress Memorial, Lunatic Pandora, Ultimecia's Castle. Each
chapter's checks only count as in logic once you hold a few more items: GFs,
plus character, junction and command unlocks when those locks are on.

This never blocks you in the game and adds or removes no checks. It only
decides where progression can be placed, so you are never expected to reach
a chapter weaker than the ladder says, and the tracker's "available" view
matches it.

- `off`: the only gate is the Disc 3 GF count at Edea's House. About 220 of a
  default seed's checks are open from the start, so your power can arrive
  late and other players may wait a long time for anything from you.
- `normal`: about 60 checks open at the start, all in Disc 1. From Timber on
  each chapter needs a few more items, rising to the Disc 3 count at Edea's
  House. A seed plays as 8 to 13 spheres.
- `tight`: about 25 open at the start and one or two more items every
  chapter. 11 to 15 spheres.

### Gameplay

**Magic Mode** (`magic_mode`: `vanilla` / `checks_only`, default `checks_only`)

- `vanilla`: draw points, battle draws and refining stock magic as normal.
- `checks_only`: multiworld magic items are the only source of stock. Each
  one (a "<Spell> Stock" such as "Firaga Stock", or a Progressive Magic
  stage) puts that many spells into your stock and raises the spell's limit,
  its cap, by the same amount. Casting uses stock up as normal and leaves the
  cap alone, so drawing can bring a spell back up to its cap, never past it:
  anything above a cap is taken back within a second. Draw points still send
  their checks and draw-based stat ladders still count. Refined magic is
  taken back the same way and the refined items are still consumed, so don't
  refine unless **Keep Refined Magic** is on. You start with a kit (see
  **Starter Magic**), and every spell but Apocalypse has a Stock item, Scan
  included. `/ff8magic` in the client shows stock against caps.

**Magic Abundance** (`magic_abundance`: 25–300 %, default 150)

Checks-only magic only. How much magic the multiworld sends over a whole
game, as a share of what your party can hold (six characters × 32 spells ×
100 = 19,200). At 150 that is about 28,800 spells over roughly 230 items in
a default seed: around 60 to 200 per item, every copy rolled, enough to
junction everyone and still cast. Shorter goals send less (the Edea goal
about a third), and no single item carries more than 255.

**Keep Refined Magic** (`refined_magic`, default off)

Checks-only magic only. Magic refined from items with the GF …Mag-RF
abilities is yours to keep: a refine permanently raises that spell's cap by
the amount refined, so the stock sticks, junctions, and can be re-drawn
after casting. Draw points and battle draws are still repossessed, and the
refine abilities still obey **GF Ability Locks**. Off by default because
item refining is a fast lane to enormous junction power (Tents into Curagas
on Disc 1). Ignored in vanilla magic mode.

**Starter Magic** (`starter_magic`: `none` / `basic` / `generous`, default `basic`)

How much magic is precollected under checks-only magic. Vanilla magic mode
never precollects any.

- `none`: nothing. The multiworld is your only junction fuel from minute
  one.
- `basic`: Cure, Fira, Blizzara, Thundara and Sleep, or their progressive
  stage-1 equivalents.
- `generous`: the basic kit plus healing and defensive staples.

**Progressive Magic** (`progressive_magic`, default on)

Checks-only magic only. The Fire, Blizzard, Thunder, Cure and Life families
become progressive items: each copy received unlocks the next stage (Fire →
Fira → Firaga). The base-tier spells only exist through these chains.

**Tiered Magic** (`tiered_magic`, default on)

Your magic items still scatter across everyone's worlds, but after
generation they are re-sorted among the spots they landed on: weak spells
(Cure, the -ra tier, basic status magic) in early spheres, the -ga tier mid,
and endgame junction power (Holy, Flare, Meteor, Ultima, Aura, Triple,
Meltdown, Full-life, The End, …) late. About one item in three is sorted a
tier early or late, so a Firaga can turn up in the first hour. Off: magic
lands in any sphere, so Ultima can arrive in the first hour.

**Trap Chance** (`trap_chance`: 0–100 %, default 10)

The share of filler replaced by traps:

- **Gil Snatch**: up to 1500 gil. Yes, it can leave you unable to afford the
  Timber train. Go fight something.
- **Ambush**: the whole party drops to 1 HP. Heal before your next fight.
- **Magic Leak**: 10 of your most-stocked spell vanish. In checks-only mode
  the cap stays, so it can be redrawn.
- **Jukebox**: the background music becomes Shuffle or Boogie, a chocobo
  theme, or the ragtime piano from Laguna's movie shoot until the next scene
  change.

Traps apply on the field, never mid-battle, and none can KO you or soft-lock.

**Vehicle Unlocks** (`vehicle_unlocks`, default off, experimental)

Adds the **Ragnarok** as an item. When it arrives, the client makes the ship
boardable on the world map long before the story would: win or flee a random
battle, or walk out of any town, and it appears beside you. Once you own it
you keep it for the rest of the game; it re-appears after every field visit
and battle. Only the story's own scripted stretches (the space trip, the
Lunatic Pandora attack through the Disc 4 opening) are left alone.

How it works: the world map only spawns the ship once the story moment
clears a threshold, so the client briefly fakes that moment around a battle
and around each return to the world map, parks the ship beside you, then
restores the real moment. No save or field script ever sees the fake.

What logic does with it: the world-map draw points of Centra, Trabia, Esthar
and the islands sit in "travel hub" regions that open with the ship or with
the story beat that normally grants it, so an early Ragnarok can put Disc 3
islands in your second sphere. The places the game never story-gates open
the same way: the Tomb of the Unknown King, the Centra Ruins and the chocobo
forests (their draw points, the Centra Ruins magazine, the Brothers, the
Chicobo card and the first forest). With Story Keys on, the area's key is
needed too, and Winhill and Shumi Village also open early once you hold
their key. Every other field keeps its story-beat logic.

Towns the story has not reached stay shut while you fly. Since v0.9 the
client keeps the world map's own copy of the story value honest after the
ship spawns; before that an early Ragnarok could land you in Timber before
Dollet, where later-disc scenes fired story checks. If a scene ever does push
the story ahead by several chapters, the client holds those checks (see
[Saves](#saves-reloading-and-offline-play)).

Caveats: the ship only lands where its terrain allows. There is no Garden
item: a mobile Garden replaces the static one on the world map, which locked
testers out of their own home base.

**Vehicle Gates** (`vehicle_gates`, default off, experimental, needs Vehicle Unlocks)

The story's own Ragnarok is withheld until the item arrives: whenever you
leave the world map the ship is parked far out at sea (scripted flights
still play), so free flight, and Sorceress Memorial and everything after it,
is a real key-item gate rather than only a logic one. Logic requires the
item to enter that chapter, so generation always places it earlier. When it
arrives the ship comes back beside you after your next battle or field
visit. One wrinkle: a save made aboard the ship loads you aboard; the gate
only bites once you disembark.

**Fast Travel** (`fast_travel`, default off)

Adds **"Warp: <place>"** items. Each one unlocks that destination for the
client's `/ff8warp` command, which teleports you there while you are on the
world map. A warp moves you and nothing else: it never skips story, and a
town the story has not opened stays closed when you arrive. Only
destinations that exist in your seed are in the pool (an `edea` seed has no
Disc 2 or 3 warps). Warps are useful items, not progression, so nothing
hides behind one.

In-game trigger: open the menu on the world map and use a Potion on a party
member. The client reads that as a warp request (its log lists which member
goes where), gives the Potion back and moves you. Potions used in battle, in
a town, or sold stay ordinary Potions. Seifer and Edea cannot pick
destinations this way; `/ff8warp` reaches everything.

Superseded by Story Keys: with `story_keys` on, the keys carry the warps and
this option adds nothing.

**Story Keys** (`story_keys`: `off` / `areas` / `story`, default `off`, experimental)

Real doors. Adds twenty **"Key: <area>"** items (Balamb, Fire Cavern, Dollet,
Timber, Galbadia Garden, Tomb of the Unknown King, Deling City, Missile
Base, Winhill, Shumi Village, Centra Ruins, Chocobo Forests, Trabia Garden,
Edea's House, Great Salt Lake, Esthar City, Lunatic Pandora Laboratory,
Lunar Gate, Sorceress Memorial, Tears' Point). The client keeps each
world-map entrance shut until its key arrives: you walk onto the town and
nothing happens, and the client says `Locked: Key: Dollet`. The moment the
key lands the door works, right where you stand.

How: FF8 decides every step from a small entrance table which town a tile
leads to; the client rewrites one word of that table per missing key. The
story moment is never touched. A scripted arrival (the train to Timber, the
Garden crashing into FH, the Ragnarok landing) is never a door, so it is
never blocked. Each key also carries its `/ff8warp` destination.

- `areas`: every key is a door, and the checks inside an area (draw points,
  magazines, rare cards, optional bosses) need it in logic. The story path
  is never gated: while the story wants you inside, that door opens without
  the key.
- `story`: on top of that, the keys of story-required doors (Fire Cavern,
  Galbadia Garden, the Tomb, Deling City, Missile Base, Trabia Garden,
  Edea's House, the Great Salt Lake, Esthar City, Lunar Gate, Sorceress
  Memorial, Tears' Point) are required in logic before their chapter, so the
  multiworld paces the story. The doors still open while the story walks
  through them, so you can never be shut out mid-story. Key: Balamb and Key:
  Fire Cavern start in your inventory so the first hour never waits on
  another world.

Keys never open a story-gated town early. A town's interiors assume the
story state (early Deling City works mechanically, but its hotel lounge
soft-locks before the story gets there), so a town only opens early once its
interiors were surveyed. Surveyed so far: Winhill and Shumi Village, which
open with the Ragnarok item plus their key. The never-gated Tomb, Centra
Ruins and chocobo forests open early the same way.

**Triple Triad Rules** (`triple_triad_rules`: `vanilla` / `no_random` / `open_no_random`, default `vanilla`)

Card rules the client keeps in force everywhere, re-applied whenever a game
spreads a rule. `no_random` removes the Random rule from every region for
good. `open_no_random` also keeps Open (both hands visible) on everywhere.
Either non-vanilla choice drops the Random-abolition checks from the game,
since they would complete themselves.

**Enemy Power** (`enemy_power`: 25–100 %, default 100, experimental)

When a battle starts, every enemy's HP, Strength, Vitality, Magic and Spirit
are scaled to this percentage, bosses included. EXP, AP, drops and levels
stay the game's own. FF8 levels enemies to your party, and with junction or
ability locks on the party cannot keep up; this is the dial for that. New in
v0.9 and not yet played through live: report anything odd, such as an enemy
re-scaling mid-fight.

**AP Multiplier** (`ap_multiplier`: 1–4, default 1, experimental)

The AP your junctioned GFs earn from each battle won is topped up to this
multiple. An ability whose counter fills from the bonus completes at the next
battle's award, the way the game learns abilities. The results screen still
shows the normal amount: the bonus is added right after, with an
`AP x2: +N bonus AP` line in the client. `/ff8` shows the multiplier your
seed was generated with. New in v0.9.

**DeathLink** (`death_link`, default off)

A full party wipe in battle sends a death to the other linked players. A
death you receive ends your next battle: your party is wiped as soon as you
are in combat, immediately if you already are. If it lands on the killing
blow the win still counts and the death waits for the next fight. Your own
DeathLink deaths are never credited as boss wins, and a received death never
echoes back. Toggle mid-session with `/deathlink`.

### Locks

All four are on by default. The **Relaxed** and **Core Only** presets turn
them off.

**Character Junction Locks** (`character_locks`, default on)

Zell, Irvine, Quistis, Rinoa and Selphie cannot hold any junctions (GFs,
magic, commands, abilities) until you receive their **"…'s Junctions"**
item. The client strips junctions from locked characters within a second.
Locked characters still join, appear in story scenes, and can attack and
use items; they just fight unjunctioned, and nothing they carry (magic
stock, a freed GF) is lost. One random character starts unlocked. Squall,
and the temporary Seifer and Edea, are never locked. A character's unlock
can sit in your starting inventory: `/ff8` lists what is currently open.

**GF Ability Locks** (`ability_locks`, default on)

The 50 signature GF abilities (the refines, Enc-None, Mug, Card Mod, the
stat Bonuses, Tonberry's shop tricks, the Auto-abilities, …) must be
unlocked with their **"GF: Ability"** item. A GF can still learn a locked
ability, and the learn still sends its check, but the ability is revoked
within a second. Once the item arrives it sticks, and an ability the GF had
already learned comes straight back. Non-signature abilities are never
touched.

**Junction Locks** (`junction_locks`, default on)

The junction abilities every GF relies on (HP-J, Str-J, Mag-J, Elem-Atk-J,
ST-Def-J, …) are removed from all GFs until the matching item arrives, named
exactly like the ability. Until "Str-J" shows up nothing junctions to
Strength and you fight on raw stats. Elem-Def-J and ST-Def-J also govern
their x2 and x4 upgrades. Luck-J is never locked. One random junction item
is precollected, and a received junction restores itself on every GF that
knows it by default. This is the single biggest "weak until the multiworld
feeds you" lever.

**Command Locks** (`command_locks`, default on)

The **Magic**, **GF** and **Item** battle commands are items. Until each
arrives no GF offers that command, so you fight with Attack and limit
breaks. Items still work from the field menu, so you can always heal between
fights. **Draw Command starts in your inventory**: a locked Draw would gate
every draw point and draw-based stat check, which is a huge slice of an
all-checks world. Logic still guards every draw-dependent check behind Draw
Command and at least one GF, so even removing the precollect via plando
cannot strand anyone.

### Check groups

Core checks (40: GF acquisitions, story and boss beats, key-item handouts,
the five Laguna dreams) are always on. Every group below defaults to on
except World Draw Point Checks.

**Draw Point Checks** (`draw_point_checks`, 99)

First draw from each named field-screen draw point. Draw points in one-time
areas (D-District Prison, Missile Base, Galbadia Garden, White SeeD Ship,
Lunar Base, the Lunatic Pandora Laboratory dream) are filler only.

**World Draw Point Checks** (`world_draw_point_checks`, 126, default off)

First draw from each hidden world-map draw point. They are invisible
in-game, which is why the group is opt-in: the tracker map shows exactly
where each one is, including the 28 on the Island Closest to Heaven and the
33 on the Island Closest to Hell. They refill over time and the world map
stays open through Disc 3, so none are missable.

**Triple Triad Checks** (`triple_triad_checks`, 28)

A total-wins ladder (5 to 100 games), a unique-card ladder (10 to 110
distinct cards), all eight CC Group members (Jack through King, Joker
included; the quest runs in Balamb Garden on Discs 2 and 3, the King's
rematch on the Ragnarok), and seven card-level sets (all 11 cards of each
common level). Filler only: the 110-card tier and the Level 5 set, because
PuPu's card is a one-chance reward.

**Triple Triad Rule Checks** (`triple_triad_rule_checks`, 8, needs Triple Triad Checks)

The grindy ones: a Balamb Garden card-wins ladder (15/40/100, the game's own
count of games won against card players inside Balamb Garden: CC members
count, Joker and King do not) and abolishing the Random rule in the
four regions that start with it (Dollet, Trabia, Centra, Lunar Gate) plus a
"Random Rule Extinct" capstone. Filler only: the Lunar Gate abolition and
the capstone. Turn it off if you would rather play cards than manage rules.

**Optional Boss Checks** (`optional_boss_checks`, 34)

Odin, the four UFO sightings, the UFO?? fight, PuPu, the eight Ultimecia's
Castle bosses plus a seals-broken ladder, the eight Ragnarok Propagators,
and separate kill checks for Ultima Weapon and Jumbo Cactuar (their GF draws
are core checks already). Omega Weapon is included but filler only.

**Rare Card Checks** (`rare_card_checks`, 33)

Obtaining each level 8 to 10 card for the first time. Losing it to an NPC
afterwards costs nothing. Cards whose holder can leave the game for good
(Angelo, Shiva, Laguna, Gilgamesh) are filler only.

**Sidequest Checks** (`sidequest_checks`, 67)

Quistis's blue magics, Zell's Duel finishers (taught by Combat King issues),
Angelo's tricks (Pet Pals), a Timber Maniacs collection ladder, a
chocobo-forests ladder (solve 1/3/5/7 of the seven forests, any order),
Phoenix's first summon and Gilgamesh's arrival (filler only: luck- and
Odin-gated), the Queen of Cards chain (filler only), the Obel Lake
milestones, a battles-won ladder (25 to 200), the SeeD written tests (levels
5/10/20/30, from the in-game Test menu), and weapon remodeling (each main
character's first remodel; the six ultimate weapons are filler only). A
remodel counts once the character holds the new weapon. Up to v0.9.0 the
check went out as soon as the junk shop listed the recipe, so the remodel
itself then sent nothing.

**Magazine Checks** (`magazine_checks`, 37)

Having each of the 23 collectible magazines in your inventory (Weapons
Monthly, Combat King, Pet Pals, Occult Fan, Girl Next Door), plus each of
the 14 Timber Maniacs issues, checked at its pickup spot. Shop-only issues
count too: Pet Pals Vol. 3 and 4 at the Timber pet shop, Vol. 5 and 6 and
Combat King 004 at the Esthar pet shop. Combat King 003 comes from the Zell
library-girl quest or the Esthar shops, so it is never missable. Magazines
are never taken from you: Combat King and Pet Pals still teach limits.
Filler only: issues from one-time windows (D-District Prison, occupied
Balamb, Lunatic Pandora, the Forest Owls train, the White SeeD Ship) and
both Balamb Timber Maniacs issues, since only one of the two (hotel or
station) can be collected per playthrough.

**Stat Ladder Checks** (`stat_checks`, 40)

Read straight from the game's own lifetime counters, the ones the save file
carries. These have nothing to do with Steam achievements, and a fresh New
Game starts them all at zero. Squall's level (10 to 40), distinct magics
obtained (5 to 40 kinds), first-time draws of eight top-tier spells (Ultima,
Meteor, Holy, Flare, Quake, Tornado, Triple, Aura), enemies scanned (5 to
25 kinds of enemy, from the Scan spell; each kind counts once and your own
party members count too), battles escaped (5 to 30),
monsters felled (50 to 500), steps taken (100k to 400k; the world map counts
about 30 per second of walking, fields about 7), Tonberries culled (5 to
20), and SeeD rank (5/10/20/A). SeeD rank is the one counter that can go
down: a tier counts at the highest rank you hold while the client is
connected, and rank A is filler only. Everything is farmable at any point.

**GF Ability Checks** (`gf_ability_checks`, 72)

The 50 signature abilities, a **Mastered** check per GF for learning all 22
of its abilities, and a party-wide abilities-learned ladder (10 to 200; the
200 tier is filler only). A GF's checks are in logic only once you hold that
GF. Ability-teaching items count. Some abilities only appear after another
is learned (Leviathan's GFRecov Med-RF after Supt Mag-RF, Quezacotl's Card
Mod after Card, Diablos's Enc-None after Enc-Half, the stat +% abilities
after their junction); with the lock options on, logic waits for the unlock
items along that chain.

### Presets

The default (no preset) is already the challenging experience.

- **Relaxed**: every check group on, all locks off, vanilla magic, generous
  starter kit. Full content, no handicap.
- **Core Only**: just the core checks, no locks, vanilla magic. The fastest
  way to play.
- **All Checks**: every check group on; locks stay at their default (on).
- **Disc One Rush**: the `edea` goal with every check group on so the
  Disc-1-only world stays dense. Locks and magic keep their challenging
  defaults.
- **Sync**: for public multiworlds where others should not wait on you. The
  `edea` goal, story gates on, only on-path check groups (core, draw points,
  optional bosses, sidequests, magazines), no traps, and the character,
  ability and junction locks off so about half of the 70 Disc 1 checks hold
  other players' items.
- **Staircase**: `story_gates: tight` plus Vehicle Unlocks and every check
  group. Many small spheres; the Ragnarok item opens the world when it shows
  up.
- **Story Keys**: Staircase plus `story_keys: story`. Every town entrance is
  a key item and the story-required ones gate the story.
- **Junction Master**: no starting GFs, Disc 3 behind 12 GFs (and the whole
  ladder scaled with it), checks-only magic, character, ability and junction
  locks.
- **SeeD Cadet**: the hardest. Every lock on, progressive checks-only magic,
  no starter kit, one starting GF.

---

## While playing

**Nothing shows up in-game when I receive an item.** Correct. No file
patching means no toast message. The client window and your tracker are
where received items appear, and the client log colors them by importance.
Draw points and magazine pickups do show what they hold by name (see next).

**The draw point says "Hookshot" instead of a spell.** While the client is
connected, an unchecked draw point's spell is renamed to the multiworld item
it holds, so the prompt reads "Found a draw point! Hookshot found." Draw it
or leave the screen and the name reverts. Magazines, the Magical Lamp and
the Solomon Ring are renamed in the item menu the same way until their check
is sent. A Lamp that still says "Magical Lamp" is the real one. Names revert
when the client closes. The main menu and battles always show the real spell
names.

**Two draw points gave me one check.** A few draw points share one slot in
the save file, so the game itself treats them as a single point: drawing one
empties the other. The Cure in Laguna's second dream is Timber City Square's
Cure, and the Cure at Galbadia Garden's gate is the one at Balamb Garden's
front gate. Whichever you draw first sends the check.

**Items are not arriving.** The client only touches the game on a field
screen, never in a menu, a battle, or the world map. Walk out of the menu
and pending items land within a second. If the client says the save is
HOLDING or frozen, read the message (see Saves below).

**My magic keeps vanishing.** Checks-only magic mode. Each spell has a cap
set by the magic items you have received; anything above it is removed
within a second. Draw whatever you like for the draw-point and First Draw
checks; the stock evaporates, the checks stay. `/ff8magic` shows stock
against caps. Switch `magic_mode` to `vanilla` if that is not for you.

**An ability I just learned disappeared.** GF Ability Locks. The learn still
sent its check; the ability comes back for good, by itself, when its "GF:
Ability" item arrives. `/ff8` lists which abilities, junctions and
commands are unlocked.

**My party members lost their junctions.** Character Junction Locks. Only
Squall plus one random character start unlocked; the rest fight
unjunctioned until their item arrives. Nothing they carried is lost.

**I cannot junction to Strength / HP / …** Junction Locks. Each junction is
an item named like the ability. One random one starts unlocked.

**I walk onto a town and nothing happens.** Story Keys. The client says
`Locked: Key: <area>` and the door opens the moment the key arrives. A town
the story is about to walk you into always opens on its own.

**I warped to Esthar on Disc 1 and it is empty.** Warps and the Ragnarok move
you, not the story. A town the story has not reached stays as vanilla, which
for Esthar is an empty map. The exceptions surveyed safe to enter early are
Winhill, Shumi Village and the Centra Ruins.

**Why no in-game boosters like Remastered?** The client has its own: Battle
Assist. `/ff8assist oneshot` leaves every enemy in a wild fight at 1 HP so
the first hit ends it (bosses stay real), `atb` keeps the ATB full, `hp`
keeps HP full, `enc` turns off random encounters. `/ff8assist on` turns on
all four. None of it changes your options, logic or save.

**Do limit breaks count when learned or when used?** When learned. Opening
the Combat King or feeding Angelo the Pet Pals is enough.

**"First Draw: <spell>" did not fire for a spell the multiworld sent me.**
By design. First Draw fires the first time the game itself hands you the
spell: a draw point (field or world map), an enemy draw, or a refine. A
spell sent by the multiworld does not count, but drawing or refining it
afterwards does. Before v0.9.1 only an enemy draw could count once the
multiworld had sent the spell; on an older client, `/ff8check First Draw:
<spell>` sends it by hand.

**"First Draw: <spell>" fired when an enemy cast it at me.** It did on
v0.9.x and earlier: the game marks a spell as seen whenever anyone casts it
with the Magic command, enemies included. The client now switches that off
in the game while it is attached, so only your own draws and refines count.

**The Balamb Garden card-wins check is slow to come.** It reads the game's
own counter of wins against Balamb Garden card players. Wins against the CC
members count; Joker (outside the Training Center) and King do not, so ten
games with Joker add nothing to it.

**The Lunar Gate asked for Key: Sorceress Memorial.** A bug in v0.6.0 to
v0.9.x: the two doors were crossed. The client now opens each with its own
key, on old seeds too.

**A battle on top of a locked town took me inside it.** The world map
reloads its doors from the game files after every battle, and the client
used to need up to half a second to shut them again. It now re-locks them
within a few milliseconds.

**The tracker shows checks in logic that I cannot reach yet.** Logic says
what your items allow over the whole story; the tracker also follows how far
the story has got (the client sends it the story position). A Disc 2 check
stays out of logic until you reach Disc 2, even if you won one of its cards
early.

**I got a Timber Maniacs check at the Centra Ruins without seeing a
magazine.** Vanilla behaviour: the game hands that issue over silently the
first time you arrive.

**Both Odin and Gilgamesh showed up.** Two independent items. In vanilla
Gilgamesh replaces Odin at the Seifer fight in Lunatic Pandora; here you
keep both until that fight, after which the game's own swap applies.

**A Card Club member did not count.** Jack through Heart count when the game
marks them beaten. Dr. Kadowaki, the King (Quistis) and Joker count when you
win a card game against them after they reveal themselves. The game stores
no "beaten" mark for those three, so a win while the client was closed is
caught on your next rematch.

**Are the stat ladders Steam achievements?** No. They are the save file's
own counters. Nothing in Steam matters.

**Monsters Felled fires late.** The game's own total updates when you enter
a town; the client counts kills as they happen, world-map fights included.

**Gil Snatch left me with no gil before the Timber train.** That is the trap
working as intended. Fight a few battles.

**When is the point of no return?** Once you commit to Disc 4 (after Lunatic
Pandora and Adel) the towns, the Gardens and the shops are gone. Only
Ultimecia's Castle and a few wild areas remain. Collect what you want first.
The castle's own checks stay available.

**A boss kill did not send.** Boss kills and the two key-item handouts
(Cid's Magical Lamp, the Solomon Ring at Tears Point) are the only events
the client has to watch live. If it was closed at that moment,
`/ff8check <name>` sends the check by hand. Everything else (draw points,
story beats, ladders, cards, magazines, abilities, GFs) is read from the
save state and catches up on reconnect.

**Which Triple Triad cards and checks are missable?** Cards whose holder can
leave (Angelo, Shiva, Laguna, Gilgamesh), the 110-card tier and the Level 5
set are filler only, so missing them costs nobody. Rare-card checks fire on
first obtaining a card, so losing it later is fine.

---

## Saves, reloading and offline play

**Can I use an existing save?** Start a New Game. Your multiworld progress
is stored inside each save file, stamped with your seed and slot. A save
from another campaign is frozen (no checks, no items) until you `/ff8adopt`
it. An unstamped save that would send 8 or more checks at once is held
until you confirm with `/ff8adopt`; this trips once after a long offline
session, by design.

**I reloaded an older save. Did I lose items?** No. Reloading re-delivers
exactly what that save is missing. Starting a New Game on the same slot
receives everything again from item 1. Checks already sent stay sent;
Archipelago never takes checks back.

**I played for an hour with the client closed.** Reconnect. Everything read
from the save state is sent on catch-up. Only boss kills and the two
handouts need `/ff8check`.

**The client says the story jumped and is holding checks.** A later-disc
scene played out of order (usually a town reached early by the Ragnarok).
The client holds the story checks past that point and the goal. Best fix:
reload a save from before you went in; the hold lifts by itself. To keep
playing from where you are, `/ff8keepstory`. v0.9.0 also raised this by
mistake during Laguna's first dream on the Timber train. Later versions do
not, and they lift a hold v0.9.0 left behind; on v0.9.0 itself,
`/ff8keepstory` clears it.

**Steam Cloud?** Fine. The client never writes save files, only the running
game's memory.

**Two client windows.** Only one may drive the game. The second stands down
and takes over when the first closes. Close the one you do not want.

**"Not attached to FF8_EN.exe."** The game is not running, or is not the
Steam 2013 English version. If it is running but cannot be opened, it is
usually running as administrator (Junction VIII often launches it that way);
run the Archipelago Launcher as administrator too.

---

## Trackers

**PopTracker**: `ff8_ap_tracker.zip` from the Releases page, dropped into
PopTracker's `packs/` folder. It reads your slot's options so its
availability matches the generator's ladder, shows every check's real
location on a stylised world map, and follows the party while the client
runs. **Universal Tracker** works with no extra files. **Visual Tracker**
has a mapping preset in `build/ff8_visual_tracker.zip`. Setup details in the
[Player Guide](player-guide.md#10-trackers).

---

## Not yet checks

Research still pending: the Shumi Village quest, the Winhill vase pieces,
the Master Fisherman, the Garden faction battle, the D-District Prison
crates and Moomba gifts, the Battle Meter upgrades, per-enemy Scan checks,
and per-forest chocobo checks (the solved-count ladder is in).

## Reporting a problem

Open an issue at <https://github.com/wilsonao/ff8_arch/issues> with the
client log (`logs/FF8Client_*.txt` in your Archipelago folder), the output
of `/ff8missed` and `/ff8verify` for a wrong or missing check, and what you
were doing in-game at the time. Setup help and gameplay questions go in
[Discussions](https://github.com/wilsonao/ff8_arch/discussions).

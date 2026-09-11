"""Player options for the Final Fantasy VIII apworld."""

from dataclasses import dataclass

from Options import (Choice, DeathLink, DefaultOnToggle, OptionGroup,
                     PerGameCommonOptions, Range, Toggle)


class Goal(Choice):
    """What ends the game.

    ultimecia: defeat Ultimecia at the end of her castle (the vanilla ending).
    omega: defeat Omega Weapon, the castle's optional superboss — a shorter but
    much harder finish; the story does not need to be completed afterwards.
    edea: defeat Sorceress Edea at the Deling City parade — the game ends with
    Disc 1. Everything past Disc 1 is removed from the world (no Disc 2+
    checks exist), so this is a genuinely short run; with few check groups
    enabled the shrunken world may not fit all the lock items (generation
    will say so).
    """
    display_name = "Goal"
    option_ultimecia = 0
    option_omega = 1
    option_edea = 2
    default = 0


class StartingGFs(Range):
    """Number of random GFs precollected at the start.

    Without any GFs you cannot junction, so the early game is much harder at 0.
    """
    display_name = "Starting GFs"
    range_start = 0
    range_end = 3
    default = 1


class GFsRequiredForDisc3(Range):
    """How many GF items logic expects you to have before Disc 3 checks are considered
    reachable (a party-power proxy — the game itself never blocks you). With
    Story Gates on, this is the anchor of the whole ladder: every earlier and
    later story beat's GF requirement scales from it (6 = the written ladder;
    12 doubles every step; 0 removes the GF column entirely).
    Ignored on the edea goal: that world ends before Disc 3 exists."""
    display_name = "GFs Required for Disc 3 (logic)"
    range_start = 0
    range_end = 12
    default = 6


class StoryGates(Choice):
    """Logic gates on the story beats, so the seed plays as a staircase instead
    of two big plateaus. The story is split into 18 beats (Balamb Prologue ...
    D-District Prison, Missile Base, Garden Revolt, Fisherman's Horizon,
    Balamb Liberation, Garden War, Edea's House, Esthar, Lunar Base,
    Sorceress Memorial, Lunatic Pandora, Ultimecia's Castle); each beat's
    checks count as reachable only once you hold a few multiworld items — a
    rising ladder of GFs, plus character, junction, and command unlocks when
    those lock options are on. Like the Disc 3 GF count, these are LOGIC gates:
    the game never physically stops you, they shape where progression can be
    placed and what the tracker shows as in-logic.

    off: only the classic Disc 3 GF-count gate (pre-0.4 behaviour).
    normal: the first four beats are free (about 25 checks), Timber needs one
    GF, and the ladder climbs to the Disc 3 anchor by Edea's House (Disc 3).
    tight: every step asks for one or two more items; sphere 1 is very small.
    """
    display_name = "Story Gates"
    option_off = 0
    option_normal = 1
    option_tight = 2
    default = 1


class VehicleGates(Toggle):
    """EXPERIMENTAL, needs Vehicle Unlocks. The client WITHHOLDS the story's
    own Ragnarok until the item arrives: whenever you leave the world map, the
    ship is parked far out at sea (the story's own scripted flights still
    play), so free flight — Sorceress Memorial and everything after it — is a
    real key-item gate, not only a logic one. Logic requires the item to enter
    that beat, so generation always places it earlier. When the item arrives
    the ship comes back beside you after your next battle or field visit.
    Live-verified 2026-09-09; off by default while it settles. Known wrinkle: a
    save made ABOARD the ship loads you aboard (the gate only bites once you
    disembark and re-enter the world map)."""
    display_name = "Vehicle Gates (Experimental)"


class MagicMode(Choice):
    """How magic stocking works.

    vanilla: draw points, battle draws, and refining stock magic as normal.

    checks_only: multiworld magic items are the only source of stock. Each
    magic item raises your cap for that spell, and the client repossesses
    anything above a cap within a second — draw points still send their
    checks and draw-based stat ladders still count, but the drawn stock
    vanishes, and refining magic is repossessed the same way (the refined
    items are still spent, so don't — unless refined_magic is on). Casting
    spends stock as normal, and drawing or refining can refill a spell back
    up to its granted cap. A starter kit of magic is precollected, and the
    filler pool draws from a much wider spell roster.
    """
    display_name = "Magic Mode"
    option_vanilla = 0
    option_checks_only = 1
    default = 1


class RefinedMagic(Toggle):
    """Checks-only magic mode: magic refined from items (the GF ...Mag-RF
    abilities) is yours to keep. A refine permanently raises that spell's cap
    by the amount refined, so the stock sticks, junctions, and can even be
    re-drawn after casting. Draw points and battle draws are still repossessed
    as normal, and the refine abilities themselves still obey ability_locks.
    Off by default: item refining is a fast lane to enormous junction power,
    and this world aims for a challenging opening. Ignored in vanilla magic
    mode, where refining already works."""
    display_name = "Keep Refined Magic"


class StarterMagic(Choice):
    """How much magic is precollected at the start (checks-only magic mode;
    vanilla magic mode never precollects any).

    none: nothing — the multiworld is your only junction fuel from minute one.
    Expect a genuinely lean opening.

    basic: a small kit (Cure, the -ra elemental trio, Sleep — or their
    progressive stage-1 equivalents).

    generous: the basic kit plus healing and defensive staples.
    """
    display_name = "Starter Magic"
    option_none = 0
    option_basic = 1
    option_generous = 2
    default = 1


class ProgressiveMagic(DefaultOnToggle):
    """Five spell families (Fire, Blizzard, Thunder, Cure, Life) become
    progressive items: each copy received unlocks the next stage (Fire ->
    Fira -> Firaga), so elemental and healing power ramps with the multiworld
    instead of arriving fully formed. The base-tier spells only exist through
    these chains. On by default. Only meaningful in checks-only magic mode
    (ignored in vanilla magic mode, where drawing provides everything
    anyway)."""
    display_name = "Progressive Magic"


class TieredMagic(DefaultOnToggle):
    """Paces your magic by multiworld progression. Your magic items still
    scatter across everyone's worlds, but after generation they are re-sorted
    among the spots they landed on so weak spells (Cure, the -ra tier, basic
    status magic) sit in early logical spheres, the -ga tier mid, and endgame
    junction power (Holy, Flare, Meteor, Ultima, Aura, Triple, Meltdown,
    Full-life) in late spheres. Off: magic lands in any sphere, so top-tier
    spells can arrive in the first hour."""
    display_name = "Tiered Magic"


class CharacterLocks(DefaultOnToggle):
    """Party members must be unlocked. Zell, Irvine, Quistis, Rinoa, and
    Selphie can't hold any junctions (GFs, magic, commands, abilities) until
    you receive their "...'s Junctions" item from the multiworld — the client
    strips junctions from locked characters within a second. Locked characters
    still join, appear in story scenes, and can attack and use items; they
    just fight unjunctioned. One random character comes unlocked from the
    start, and Squall (plus the temporary Seifer/Edea) is never locked. On by
    default — this world aims for a challenging opening; turn it off (or use
    the Relaxed preset) to keep your whole party junctioned from the start."""
    display_name = "Character Junction Locks"


class AbilityLocks(DefaultOnToggle):
    """The 49 signature GF abilities (the refines, Enc-None, Mug, Card Mod,
    the stat Bonuses, Tonberry's shop tricks, the Auto- abilities...) must be
    unlocked. A GF can still learn a locked ability — learning it still sends
    its check — but the ability is revoked within a second until you receive
    the matching "GF: Ability" item from the multiworld; after that it sticks
    (relearn it if it was revoked, AP willing). Non-signature abilities are
    never touched. On by default; turn it off to learn every ability freely."""
    display_name = "GF Ability Locks"


class JunctionLocks(DefaultOnToggle):
    """Stat junctions must be unlocked. The junction abilities (HP-J, Str-J,
    Mag-J, Elem-Atk-J, ST-Def-J...) are removed from every GF until you
    receive the matching multiworld item — until "Str-J" arrives, nothing can
    be junctioned to Strength, so early fights are fought on raw stats. The
    Elem-Def-J and ST-Def-J items also govern their x2/x4 upgrades; Luck-J is
    never locked. One random junction item comes precollected, and receiving
    an item restores it on every GF that knows it by default. This is the
    'feel weak until the multiworld feeds you' lever, and it's on by default;
    turn it off to junction freely from the start."""
    display_name = "Junction Locks"


class CommandLocks(DefaultOnToggle):
    """The Magic, GF, and Item battle commands must be unlocked; until each
    command's item arrives no GF offers it, leaving Attack and limit breaks.
    Items still work from the field menu, so healing between fights always
    works. Draw Command comes precollected — a locked Draw would gate every
    draw point and draw-based stat check, leaving too much of the world dark
    and self-drought too easy (logic still guards all of it, so removing the
    precollect via plando stays safe). On by default; turn it off to keep all
    four battle commands from the start."""
    display_name = "Command Locks"


class VehicleUnlocks(Toggle):
    """EXPERIMENTAL — off by default. Adds the "Ragnarok" item to the pool: when
    it arrives, the client makes the ship boardable on the world map long
    before the story would, and it flies anywhere it can land. How it works:
    the world map only spawns the ship once the story moment clears its
    threshold, so the client briefly fakes that moment around a BATTLE and
    around every return to the world map from a field (a few seconds each,
    while it parks the ship beside you), then restores the real moment. The
    story moment stays honest during all normal play, and no save or field
    script ever sees the fake. To make the ship appear, win or flee a random
    battle or walk out of any town; it re-appears beside you after every field
    visit, and once you own it you keep it for the whole game (the story's
    own scripted stretches — the space trip, the Lunatic Pandora attack — are
    left alone). Logic routes only the world-map draw points of Centra,
    Trabia, Esthar and the islands through the item (an early Ragnarok pulls
    those into an early sphere); every field location keeps its story-beat
    logic. Caveat: the ship only lands where its terrain allows (unpatched
    game). Live-verified on Disc 1 and Disc 3, 2026-09-09."""
    display_name = "Vehicle Unlocks (Experimental)"


class FastTravel(Toggle):
    """Adds fast-travel warp destinations to the item pool. Each "Warp: <place>"
    item you receive unlocks that place as a destination for the client's
    /ff8warp command, which teleports you there on the world map. Warps move
    you, nothing else: they never skip story, and a town the story has not
    opened yet stays closed when you arrive. Only destinations that exist in
    your seed are in the pool (the edea goal drops the Disc 2/3 ones).
    Destinations are useful items (logic doesn't route through them), so
    nothing hides behind an early warp. Off by default."""
    display_name = "Fast Travel"


class TrapChance(Range):
    """Percentage of filler items replaced by traps. Gil Snatch takes up to
    1500 gil, Ambush drops the whole party to 1 HP (heal up before the next
    fight), Magic Leak removes 10 of your most-stocked spell (in checks-only
    magic mode the cap stays, so it can be redrawn). Traps apply on the field,
    never mid-battle, and none can knock you out or soft-lock."""
    display_name = "Trap Chance"
    range_start = 0
    range_end = 100
    default = 10


class DrawPointChecks(DefaultOnToggle):
    """Adds the ~100 named field-screen draw points as checks (drawing from one for
    the first time sends it). World-map draw points have their own toggle.
    One-window draw points (D-District Prison, Missile Base, Galbadia Garden,
    White SeeD Ship, Lunar Base, Lunatic Pandora Laboratory) can only hold filler.
    """
    display_name = "Draw Point Checks"


class WorldDrawPointChecks(Toggle):
    """Adds the 125 hidden world-map draw points as checks (drawing from one
    for the first time sends it). These are invisible in-game — the tracker
    map shows where they are, including the Islands Closest to Heaven and Hell
    (28 and 33 points of top-tier magic). They refill over time and the world
    map stays open through Disc 3, so none are missable."""
    display_name = "World Draw Point Checks"


class TripleTriadChecks(DefaultOnToggle):
    """Adds Triple Triad checks: a total-wins ladder (5-100 games), a
    unique-card-collection ladder (10-110 distinct cards), all eight CC Group
    members (Jack through King, Joker included; the quest runs in Balamb
    Garden on Discs 2-3), a Balamb Garden card-wins ladder (15/40/100), seven
    card-level set collections (all 11 cards of each common level), and
    abolishing the Random rule in the four regions that start with it. The
    110-card tier, the Level 5 set (PuPu's card is a one-chance reward), and
    the Lunar Gate / everywhere abolitions only ever hold filler."""
    display_name = "Triple Triad Checks"


class OptionalBossChecks(DefaultOnToggle):
    """Adds optional battle checks: Odin, the four UFO sightings, the UFO??
    fight, PuPu, eight Ultimecia Castle bosses, the eight Ragnarok Propagators,
    and separate kill checks for Ultima Weapon and Jumbo Cactuar (their GF
    draws are already core checks). Omega Weapon is included but only ever
    holds filler."""
    display_name = "Optional Boss Checks"


class RareCardChecks(DefaultOnToggle):
    """Adds the 33 rare (level 8-10) Triple Triad cards as checks — winning or
    receiving one for the first time sends it. Cards whose holder can leave the
    game for good (Angelo, Shiva, Laguna, Gilgamesh) only ever hold filler."""
    display_name = "Rare Card Checks"


class SidequestChecks(DefaultOnToggle):
    """Adds sidequest checks: Quistis's blue magics, Zell's Duel finishers
    (taught by Combat King issues), Angelo's tricks, a Timber Maniacs
    collection ladder, a chocobo-forests solved ladder (1/3/5/7 of the seven
    forests, any order), Phoenix's first summon, Gilgamesh's arrival, a
    battles-won ladder (25/50/100/200), the SeeD written tests (levels
    5/10/20/30), and weapon remodeling (first remodel per character; ultimate
    weapons only ever hold filler)."""
    display_name = "Sidequest Checks"


class StatChecks(DefaultOnToggle):
    """Adds stat-ladder checks read from the game's own lifetime counters:
    Squall's level (10-40), distinct magics obtained (5-40 kinds), first-time
    draws of eight top-tier spells, enemies scanned (5-30), battles escaped
    (5-30), monsters felled (50-500), steps taken (20k-300k), Tonberries
    culled (5-20), and SeeD rank (5/10/20/A). Every ladder is farmable at any
    point, so nothing here is permanently missable. SeeD rank is the one
    counter that can go down; a rank tier counts at the highest rank you hold
    while the client is connected, and rank A only ever holds filler."""
    display_name = "Stat Ladder Checks"


class GFAbilityChecks(DefaultOnToggle):
    """Adds GF ability checks: 49 signature abilities (the refines, Enc-None,
    Mug, Card Mod, the stat Bonuses, Tonberry's shop tricks, the Auto-
    abilities...), a Mastered check per GF for learning all 22 of its
    abilities, and a party-wide ladder of abilities learned (10-200). A GF's
    checks require having that GF; ability-teaching items count. The 200 tier
    only ever holds filler."""
    display_name = "GF Ability Checks"


class MagazineChecks(DefaultOnToggle):
    """Adds the 23 collectible magazines (Weapons Monthly, Combat King, Pet
    Pals, Occult Fan, Girl Next Door) as checks — having one in the inventory
    sends its check — plus the 14 Timber Maniacs issues, each checked at its
    pickup spot. Shop-only issues (Pet Pals Vol.3-6, Combat King 004) count
    too: buy them at the Timber and Esthar pet shops. Magazines are never
    taken from you: Combat King and Pet Pals still teach limits as normal.
    Issues from one-time windows (D-District Prison, occupied Balamb, Lunatic
    Pandora, the Forest Owls train, the White SeeD Ship, and both mutually
    exclusive Balamb Timber Maniacs) only ever hold filler."""
    display_name = "Magazine Checks"


@dataclass
class FF8Options(PerGameCommonOptions):
    goal: Goal
    starting_gfs: StartingGFs
    gfs_required_for_disc3: GFsRequiredForDisc3
    story_gates: StoryGates
    magic_mode: MagicMode
    refined_magic: RefinedMagic
    starter_magic: StarterMagic
    progressive_magic: ProgressiveMagic
    tiered_magic: TieredMagic
    character_locks: CharacterLocks
    ability_locks: AbilityLocks
    junction_locks: JunctionLocks
    command_locks: CommandLocks
    vehicle_unlocks: VehicleUnlocks
    vehicle_gates: VehicleGates
    fast_travel: FastTravel
    trap_chance: TrapChance
    draw_point_checks: DrawPointChecks
    world_draw_point_checks: WorldDrawPointChecks
    triple_triad_checks: TripleTriadChecks
    optional_boss_checks: OptionalBossChecks
    rare_card_checks: RareCardChecks
    sidequest_checks: SidequestChecks
    magazine_checks: MagazineChecks
    stat_checks: StatChecks
    gf_ability_checks: GFAbilityChecks
    death_link: DeathLink


# WebHost options-page layout.
OPTION_GROUPS = [
    OptionGroup("Logic", [Goal, StartingGFs, GFsRequiredForDisc3, StoryGates]),
    OptionGroup("Gameplay", [MagicMode, RefinedMagic, StarterMagic,
                             ProgressiveMagic, TieredMagic, TrapChance,
                             VehicleUnlocks, VehicleGates, FastTravel]),
    OptionGroup("Locks", [CharacterLocks, AbilityLocks, JunctionLocks,
                          CommandLocks]),
    OptionGroup("Check Groups", [DrawPointChecks, WorldDrawPointChecks,
                                 TripleTriadChecks,
                                 OptionalBossChecks, RareCardChecks,
                                 SidequestChecks, MagazineChecks, StatChecks,
                                 GFAbilityChecks]),
]

# WebHost one-click presets.
OPTION_PRESETS = {
    "All Checks": {
        "draw_point_checks": True,
        "world_draw_point_checks": True,
        "triple_triad_checks": True,
        "optional_boss_checks": True,
        "rare_card_checks": True,
        "sidequest_checks": True,
        "magazine_checks": True,
        "stat_checks": True,
        "gf_ability_checks": True,
    },
    "Core Only": {  # minimal, quick, and easy: just the core checks, no locks
        "draw_point_checks": False,
        "world_draw_point_checks": False,
        "triple_triad_checks": False,
        "optional_boss_checks": False,
        "rare_card_checks": False,
        "sidequest_checks": False,
        "magazine_checks": False,
        "stat_checks": False,
        "gf_ability_checks": False,
        "magic_mode": "vanilla",
        "progressive_magic": False,
        "character_locks": False,
        "ability_locks": False,
        "junction_locks": False,
        "command_locks": False,
    },
    "Relaxed": {  # the full check list without the handicap — the easy button
        "magic_mode": "vanilla",       # draw and junction like the base game
        "starter_magic": "generous",
        "progressive_magic": False,
        "character_locks": False,
        "ability_locks": False,
        "junction_locks": False,
        "command_locks": False,
        "draw_point_checks": True,
        "world_draw_point_checks": True,
        "triple_triad_checks": True,
        "optional_boss_checks": True,
        "rare_card_checks": True,
        "sidequest_checks": True,
        "magazine_checks": True,
        "stat_checks": True,
        "gf_ability_checks": True,
    },
    "Disc One Rush": {  # the short run: the game ends at the Deling City
        "goal": "edea",  # parade, so every check group is on to keep the
        "draw_point_checks": True,  # shrunken world dense enough for the
        "world_draw_point_checks": True,  # default lock items
        "triple_triad_checks": True,
        "optional_boss_checks": True,
        "rare_card_checks": True,
        "sidequest_checks": True,
        "magazine_checks": True,
        "stat_checks": True,
        "gf_ability_checks": True,
    },
    "Junction Master": {  # everything on, nothing given, Disc 3 hard-gated,
        "starting_gfs": 0,  # and all magic AND party junction rights come
        "gfs_required_for_disc3": 12,  # from the multiworld
        "magic_mode": "checks_only",
        "character_locks": True,
        "ability_locks": True,
        "junction_locks": True,
        "draw_point_checks": True,
        "world_draw_point_checks": True,
        "triple_triad_checks": True,
        "optional_boss_checks": True,
        "rare_card_checks": True,
        "sidequest_checks": True,
        "magazine_checks": True,
        "stat_checks": True,
        "gf_ability_checks": True,
    },
    "Sync": {  # public multiworlds where the other players must not wait
        "goal": "edea",  # on you: the short goal, only checks that sit on
        "story_gates": "normal",  # the story path (no grind ladders, no
        "trap_chance": 0,  # card hunting), no traps, and the big lock
        "character_locks": False,  # tables off so about half of the 70
        "ability_locks": False,  # Disc 1 locations hold OTHER players'
        "junction_locks": False,  # items instead of our own
        "command_locks": True,
        "draw_point_checks": True,
        "world_draw_point_checks": False,
        "triple_triad_checks": False,
        "optional_boss_checks": True,
        "rare_card_checks": False,
        "sidequest_checks": True,
        "magazine_checks": True,
        "stat_checks": False,
        "gf_ability_checks": False,
    },
    "Staircase": {  # the tightest sphere ladder plus early vehicles: the
        "story_gates": "tight",  # seed plays as many small steps and the
        "vehicle_unlocks": True,  # the Ragnarok item opens the world
        "draw_point_checks": True,
        "world_draw_point_checks": True,
        "triple_triad_checks": True,
        "optional_boss_checks": True,
        "rare_card_checks": True,
        "sidequest_checks": True,
        "magazine_checks": True,
        "stat_checks": True,
        "gf_ability_checks": True,
    },
    "SeeD Cadet": {  # the classic AP underdog opening: every power system
        "starting_gfs": 1,  # starts locked and the multiworld feeds it back —
        "gfs_required_for_disc3": 6,  # junctions, commands, abilities, party,
        "magic_mode": "checks_only",  # and magic (progressive, no starter kit)
        "starter_magic": "none",
        "progressive_magic": True,
        "character_locks": True,
        "ability_locks": True,
        "junction_locks": True,
        "command_locks": True,
        "draw_point_checks": True,
        "world_draw_point_checks": True,
        "triple_triad_checks": True,
        "optional_boss_checks": True,
        "rare_card_checks": True,
        "sidequest_checks": True,
        "magazine_checks": True,
        "stat_checks": True,
        "gf_ability_checks": True,
    },
}

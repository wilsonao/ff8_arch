"""Player options for the Final Fantasy VIII apworld."""

from dataclasses import dataclass

from Options import Choice, DeathLink, OptionGroup, PerGameCommonOptions, Range, Toggle


class Goal(Choice):
    """What ends the game.

    ultimecia: defeat Ultimecia at the end of her castle (the vanilla ending).
    omega: defeat Omega Weapon, the castle's optional superboss — a shorter but
    much harder finish; the story does not need to be completed afterwards.
    """
    display_name = "Goal"
    option_ultimecia = 0
    option_omega = 1
    default = 0


class StartingGFs(Range):
    """Number of random GFs precollected at the start.

    Without any GFs you cannot junction, so the early game is much harder at 0.
    """
    display_name = "Starting GFs"
    range_start = 0
    range_end = 3
    default = 2


class GFsRequiredForDisc3(Range):
    """How many GF items logic expects you to have before Disc 3 checks are considered
    reachable (a party-power proxy — the game itself never blocks you)."""
    display_name = "GFs Required for Disc 3 (logic)"
    range_start = 0
    range_end = 12
    default = 6


class MagicMode(Choice):
    """How magic stocking works.

    vanilla: draw points, battle draws, and refining stock magic as normal.

    checks_only: multiworld magic items are the only source of stock. Each
    magic item raises your cap for that spell, and the client repossesses
    anything above a cap within a second — draw points still send their
    checks and draw-based stat ladders still count, but the drawn stock
    vanishes, and refining magic is repossessed the same way (the refined
    items are still spent, so don't). Casting spends stock as normal, and
    drawing or refining can refill a spell back up to its granted cap. A
    starter kit of magic is precollected, and the filler pool draws from a
    much wider spell roster.
    """
    display_name = "Magic Mode"
    option_vanilla = 0
    option_checks_only = 1
    default = 0


class TrapChance(Range):
    """Percentage of filler items replaced by traps. Gil Snatch takes up to
    1500 gil, Ambush drops the whole party to 1 HP (heal up before the next
    fight), Magic Leak removes 10 of your most-stocked spell (in checks-only
    magic mode the cap stays, so it can be redrawn). Traps apply on the field,
    never mid-battle, and none can knock you out or soft-lock."""
    display_name = "Trap Chance"
    range_start = 0
    range_end = 100
    default = 0


class DrawPointChecks(Toggle):
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


class TripleTriadChecks(Toggle):
    """Adds Triple Triad checks: a total-wins ladder (5-100 games), a
    unique-card-collection ladder (10-110 distinct cards), all eight CC Group
    members (Jack through King, Joker included; the quest runs in Balamb
    Garden on Discs 2-3), a Balamb Garden card-wins ladder (15/40/100), seven
    card-level set collections (all 11 cards of each common level), and
    abolishing the Random rule in the four regions that start with it. The
    110-card tier, the Level 5 set (PuPu's card is a one-chance reward), and
    the Lunar Gate / everywhere abolitions only ever hold filler."""
    display_name = "Triple Triad Checks"


class OptionalBossChecks(Toggle):
    """Adds optional battle checks: Odin, the four UFO sightings, the UFO??
    fight, PuPu, eight Ultimecia Castle bosses, the eight Ragnarok Propagators,
    and separate kill checks for Ultima Weapon and Jumbo Cactuar (their GF
    draws are already core checks). Omega Weapon is included but only ever
    holds filler."""
    display_name = "Optional Boss Checks"


class RareCardChecks(Toggle):
    """Adds the 33 rare (level 8-10) Triple Triad cards as checks — winning or
    receiving one for the first time sends it. Cards whose holder can leave the
    game for good (Angelo, Shiva, Laguna, Gilgamesh) only ever hold filler."""
    display_name = "Rare Card Checks"


class SidequestChecks(Toggle):
    """Adds sidequest checks: Quistis's blue magics, Zell's Duel finishers
    (taught by Combat King issues), Angelo's tricks, a Timber Maniacs
    collection ladder, a chocobo-forests solved ladder (1/3/5/7 of the seven
    forests, any order), Phoenix's first summon, Gilgamesh's arrival, a
    battles-won ladder (25/50/100/200), the SeeD written tests (levels
    5/10/20/30), and weapon remodeling (first remodel per character; ultimate
    weapons only ever hold filler)."""
    display_name = "Sidequest Checks"


class StatChecks(Toggle):
    """Adds stat-ladder checks read from the game's own lifetime counters:
    Squall's level (10-40), distinct magics obtained (5-40 kinds), first-time
    draws of eight top-tier spells, enemies scanned (5-30), battles escaped
    (5-30), monsters felled (50-500), steps taken (20k-300k), Tonberries
    culled (5-20), and SeeD rank (5/10/20/A). Every ladder is farmable at any
    point, so nothing here is permanently missable. SeeD rank is the one
    counter that can go down; a rank tier counts at the highest rank you hold
    while the client is connected, and rank A only ever holds filler."""
    display_name = "Stat Ladder Checks"


class GFAbilityChecks(Toggle):
    """Adds GF ability checks: 49 signature abilities (the refines, Enc-None,
    Mug, Card Mod, the stat Bonuses, Tonberry's shop tricks, the Auto-
    abilities...), a Mastered check per GF for learning all 22 of its
    abilities, and a party-wide ladder of abilities learned (10-200). A GF's
    checks require having that GF; ability-teaching items count. The 200 tier
    only ever holds filler."""
    display_name = "GF Ability Checks"


class MagazineChecks(Toggle):
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
    magic_mode: MagicMode
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
    OptionGroup("Logic", [Goal, StartingGFs, GFsRequiredForDisc3]),
    OptionGroup("Gameplay", [MagicMode, TrapChance]),
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
    "Core Only": {
        "draw_point_checks": False,
        "world_draw_point_checks": False,
        "triple_triad_checks": False,
        "optional_boss_checks": False,
        "rare_card_checks": False,
        "sidequest_checks": False,
        "magazine_checks": False,
        "stat_checks": False,
        "gf_ability_checks": False,
    },
    "Junction Master": {  # everything on, nothing given, Disc 3 hard-gated,
        "starting_gfs": 0,  # and all magic comes from the multiworld
        "gfs_required_for_disc3": 12,
        "magic_mode": "checks_only",
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

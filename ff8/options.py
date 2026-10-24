"""Player options for the Final Fantasy VIII apworld."""

from dataclasses import dataclass

from Options import (Choice, DeathLink, DefaultOnToggle, OptionGroup,
                     PerGameCommonOptions, Range, Toggle)


class Goal(Choice):
    """What ends the game.

    ultimecia: beat Ultimecia (the vanilla ending).
    omega: beat Omega Weapon in her castle. Shorter and much harder.
    edea: beat Edea at the Deling City parade. The game ends with Disc 1 and
    no Disc 2+ checks exist."""
    display_name = "Goal"
    option_ultimecia = 0
    option_omega = 1
    option_edea = 2
    default = 0


class StartingGFs(Range):
    """Random GFs you start with. At 0 you can't junction or draw until the
    multiworld sends a GF, so only a handful of Balamb Garden checks are in
    logic at the start."""
    display_name = "Starting GFs"
    range_start = 0
    range_end = 3
    default = 1


class GFsRequiredForDisc3(Range):
    """Logic only, never enforced in-game: how many GF items the generator
    expects before Disc 3 checks count as reachable. Anchors the Story Gates
    ladder. Ignored on the edea goal."""
    display_name = "GFs Required for Disc 3 (logic)"
    range_start = 0
    range_end = 12
    default = 6


class StoryGates(Choice):
    """Logic only, never enforced in-game: how many items the generator expects
    you to hold before each of the 18 story chapters' checks count as
    reachable. You always play the whole story in order.

    off: about 220 checks open from the start.
    normal: about 60 open; each chapter from Timber on needs a few more.
    tight: about 25 open; one or two more items every chapter."""
    display_name = "Story Gates"
    option_off = 0
    option_normal = 1
    option_tight = 2
    default = 1


class VehicleGates(Toggle):
    """Experimental; needs Vehicle Unlocks. The story's own Ragnarok is parked
    out of reach until the Ragnarok item arrives, so free flight is a real
    gate instead of a logic one."""
    display_name = "Vehicle Gates (Experimental)"


class MagicMode(Choice):
    """Where magic stock comes from.

    vanilla: draw and refine as normal.
    checks_only: magic comes from multiworld items. Each one puts spells in
    your stock and raises that spell's limit by the same amount. Casting
    uses stock as normal; drawing or refining can bring a spell back up to
    its limit, never past it. Draw points still send their checks."""
    display_name = "Magic Mode"
    option_vanilla = 0
    option_checks_only = 1
    default = 1


class MagicAbundance(Range):
    """Checks-only magic: how much magic the multiworld sends over a whole
    game, as a percentage of what your party can hold (six characters x 32
    spells x 100 = 19,200). Every magic item carries a share, give or take
    half. 150 leaves room to cast as well as junction. Shorter goals send
    proportionally less."""
    display_name = "Magic Abundance"
    range_start = 25
    range_end = 300
    default = 150


class RefinedMagic(Toggle):
    """Checks-only magic: magic refined from items (the ...Mag-RF abilities) is
    kept and raises that spell's cap. Off: refined magic is removed like
    drawn magic."""
    display_name = "Keep Refined Magic"


class StarterMagic(Choice):
    """Magic you start with (checks-only magic mode only).

    none: nothing.
    basic: Cure, Fira, Blizzara, Thundara, Sleep.
    generous: basic plus healing and defensive staples."""
    display_name = "Starter Magic"
    option_none = 0
    option_basic = 1
    option_generous = 2
    default = 1


class ProgressiveMagic(DefaultOnToggle):
    """Checks-only magic: Fire, Blizzard, Thunder, Cure and Life are
    progressive items (Fire -> Fira -> Firaga)."""
    display_name = "Progressive Magic"


class TieredMagic(DefaultOnToggle):
    """Weak spells mostly land early, -ga spells mid, endgame spells (Ultima,
    Meteor, Holy, Flare, Aura, Triple...) late; about one spell in three
    lands a tier early or late. Off: any spell can arrive in the first
    hour."""
    display_name = "Tiered Magic"


class CharacterLocks(DefaultOnToggle):
    """Zell, Irvine, Quistis, Rinoa and Selphie fight unjunctioned until their
    "...'s Junctions" item arrives. One random character starts unlocked;
    Squall is never locked."""
    display_name = "Character Junction Locks"


class AbilityLocks(DefaultOnToggle):
    """The 50 signature GF abilities (refines, Enc-None, Mug, Card Mod, stat
    Bonuses, Auto-abilities...) are revoked until their "GF: Ability" item
    arrives. Learning one still sends its check, and once its item arrives
    an ability the GF already learned comes straight back."""
    display_name = "GF Ability Locks"


class JunctionLocks(DefaultOnToggle):
    """Stat junctions (HP-J, Str-J, Mag-J, Elem-Atk-J...) are removed from
    every GF until the matching item arrives. One random junction starts
    unlocked; Luck-J is never locked."""
    display_name = "Junction Locks"


class CommandLocks(DefaultOnToggle):
    """The Magic, GF and Item battle commands are items. Until each arrives you
    fight with Attack and limit breaks. Draw is always available."""
    display_name = "Command Locks"


class VehicleUnlocks(Toggle):
    """Experimental. Adds the Ragnarok as an item. Once received, the ship
    appears beside you on the world map after any battle or field exit, at
    any point in the story. Logic opens the world-map draw points and the
    never-gated areas (Tomb, Centra Ruins, chocobo forests) with it."""
    display_name = "Vehicle Unlocks (Experimental)"


class FastTravel(Toggle):
    """Adds "Warp: <place>" items. Each unlocks a world-map destination for
    /ff8warp. Warps never skip story. Does nothing when Story Keys is on
    (keys carry the warps)."""
    display_name = "Fast Travel"


class StoryKeys(Choice):
    """Experimental. Adds "Key: <area>" items and keeps each world-map entrance
    shut until its key arrives. Keys also carry /ff8warp destinations. A
    door the story walks through always opens.

    areas: only the checks inside an area need its key in logic.
    story: story-required keys are also needed in logic before their
    chapter, so the multiworld paces the story."""
    display_name = "Story Keys (Experimental)"
    option_off = 0
    option_areas = 1
    option_story = 2
    default = 0


class TrapChance(Range):
    """Percentage of filler replaced by traps: Gil Snatch (up to 1500 gil),
    Ambush (party to 1 HP), Magic Leak (10 of your most-stocked spell),
    Jukebox (music swap). Field only; never fatal."""
    display_name = "Trap Chance"
    range_start = 0
    range_end = 100
    default = 10


class DrawPointChecks(DefaultOnToggle):
    """99 named field draw points: the first draw sends the check. Draw points
    in one-time areas hold filler only."""
    display_name = "Draw Point Checks"


class WorldDrawPointChecks(Toggle):
    """126 hidden world-map draw points: the first draw sends the check.
    Invisible in-game; the tracker map shows them. None are missable."""
    display_name = "World Draw Point Checks"


class TripleTriadChecks(DefaultOnToggle):
    """28 checks: total wins (5-100), unique cards (10-110), the eight CC Group
    members, and seven card-level sets."""
    display_name = "Triple Triad Checks"


class OptionalBossChecks(DefaultOnToggle):
    """34 checks: Odin, the UFO sightings and PuPu, the Ultimecia's Castle
    bosses and seals, the Propagators, and Ultima Weapon and Jumbo Cactuar
    kills. Omega Weapon holds filler only."""
    display_name = "Optional Boss Checks"


class RareCardChecks(DefaultOnToggle):
    """33 checks: obtaining each level 8-10 card for the first time. Losing it
    afterwards is fine."""
    display_name = "Rare Card Checks"


class SidequestChecks(DefaultOnToggle):
    """67 checks: blue magic, Duel finishers, Angelo tricks, Timber Maniacs
    ladder, chocobo forests, Obel Lake, Queen of Cards, battles won, SeeD
    tests, weapon remodels."""
    display_name = "Sidequest Checks"


class StatChecks(DefaultOnToggle):
    """40 checks from the save's own lifetime counters: Squall's level, magics
    obtained, first draws, enemies scanned, escapes, kills, steps,
    Tonberries, SeeD rank. Nothing is missable."""
    display_name = "Stat Ladder Checks"


class GFAbilityChecks(DefaultOnToggle):
    """72 checks: the 50 signature GF abilities, a Mastered check per GF, and a
    party-wide abilities-learned ladder."""
    display_name = "GF Ability Checks"


class MagazineChecks(DefaultOnToggle):
    """37 checks: the 23 magazines (having one in your inventory) and the 14
    Timber Maniacs issues at their pickup spots. Magazines stay yours. One-
    time issues hold filler only."""
    display_name = "Magazine Checks"


class TripleTriadRuleChecks(DefaultOnToggle):
    """8 grindier checks (needs Triple Triad Checks): Balamb Garden wins
    (15/40/100; the game's own count of wins against Garden card players,
    where Joker and King don't count) and abolishing the Random rule in
    Dollet, Trabia, Centra and Lunar Gate."""
    display_name = "Triple Triad Rule Checks"


class TripleTriadRules(Choice):
    """Card rules the client keeps in force everywhere.

    vanilla: rules spread as normal.
    no_random: Random is removed everywhere, for good.
    open_no_random: the same, plus Open everywhere. Either non-vanilla
    choice drops the Random-abolition checks."""
    display_name = "Triple Triad Rules"
    option_vanilla = 0
    option_no_random = 1
    option_open_no_random = 2
    default = 0


class EnemyPower(Range):
    """Enemy HP, Str, Vit, Mag and Spr as a percentage of normal, bosses
    included. EXP, AP, drops and levels are unchanged. Experimental."""
    display_name = "Enemy Power"
    range_start = 25
    range_end = 100
    default = 100


class APMultiplier(Range):
    """Multiplies the AP your GFs earn per battle. The results screen still
    shows the normal amount; the client adds the rest right after.
    Experimental."""
    display_name = "AP Multiplier"
    range_start = 1
    range_end = 4
    default = 1


@dataclass
class FF8Options(PerGameCommonOptions):
    goal: Goal
    starting_gfs: StartingGFs
    gfs_required_for_disc3: GFsRequiredForDisc3
    story_gates: StoryGates
    magic_mode: MagicMode
    magic_abundance: MagicAbundance
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
    story_keys: StoryKeys
    trap_chance: TrapChance
    draw_point_checks: DrawPointChecks
    world_draw_point_checks: WorldDrawPointChecks
    triple_triad_checks: TripleTriadChecks
    triple_triad_rule_checks: TripleTriadRuleChecks
    triple_triad_rules: TripleTriadRules
    enemy_power: EnemyPower
    ap_multiplier: APMultiplier
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
    OptionGroup("Gameplay", [MagicMode, MagicAbundance, RefinedMagic, StarterMagic,
                             ProgressiveMagic, TieredMagic, TrapChance,
                             VehicleUnlocks, VehicleGates, FastTravel,
                             StoryKeys, TripleTriadRules, EnemyPower,
                             APMultiplier]),
    OptionGroup("Locks", [CharacterLocks, AbilityLocks, JunctionLocks,
                          CommandLocks]),
    OptionGroup("Check Groups", [DrawPointChecks, WorldDrawPointChecks,
                                 TripleTriadChecks, TripleTriadRuleChecks,
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
    "Story Keys": {  # the Staircase plus real doors: every town entrance
        "story_gates": "tight",  # is a key item and the story-required ones
        "vehicle_unlocks": True,  # gate the story beats
        "story_keys": "story",
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

# Savemap measurables — the full check-candidate survey

> Compiled 2026-08-31 from Hyne `SaveData.h` (local checkout at
> `thirdparty/hyne-src`) cross-verified against the 273-save library with
> `tools/save_scan.py`. This is the systematic answer to "what can we measure
> and turn into checks" — every persistent field in the savemap, with a
> verdict. Fields already carrying checks before this pass (game moment, GF
> unlocks, draw points, TT counters, rare cards, blue magic, Angelo, Timber
> Maniacs, seals, weapons, quest bytes) are not re-litigated here.

Verdicts: **CHECK** (has checks now), **FUTURE** (viable, needs more research),
**REJECTED** (measured, decided against — with the reason).

## MISC2 (battle-engine stats, base `0x18FE928`, 144 bytes)

| Field | Offset | Verdict | Notes |
|---|---|---|---|
| `game_time` | +0 | REJECTED | real-time playtime ladder rewards idling, not play |
| `countdown` | +4 | REJECTED | transient timer |
| `victory_count` | +12 | CHECK | battles-won ladder (pre-existing, sidequest group) |
| `battle_escaped` | +18 | CHECK | escapes ladder 5/15/30 (stats group) |
| `tomberry_vaincus` | +24 | CHECK | Tonberries-culled ladder 5/10/20 (stats group) |
| `tomberry_sr_vaincu` | +28 | CHECK | Tonberry King flag (pre-existing backup trigger) |
| `ufo_battle_encountered` | +32 | CHECK | UFO?? kill (pre-existing backup trigger) |
| `elmidea/succube/trex` battle vars | +36..47 | REJECTED | one-off battle-script scratch vars |
| `battle_irvine` | +48 | REJECTED | single tutorial-battle flag, covered by story beats |
| `magic_drawn_once[8]` | +52 | CHECK | bit = spell id − 1, set on first obtain via draw (draw points included; verified: all 20 library saves that drew the FH Ultima point carry Ultima's bit). Multiworld magic filler writes inventory directly and never sets bits — the ladder can't self-fire. Powers the 5/10/20/30/40-kinds ladder + eight marquee "First Draw" checks |
| `ennemy_scanned_once[20]` | +60 | CHECK | scanned-enemies ladder 5/10/20/30; median player never scans (library median 0), so tiers stay modest. Per-enemy single checks are FUTURE (needs the bit→enemy table from the kernel) |
| `renzokuken_auto/indicator` | +80/81 | REJECTED | config toggles, not counters |
| `dream` | +82 | CHECK | cameo GF bits (pre-existing) |
| `tutorial_infos[16]` | +83 | REJECTED | menu-tutorial-seen flags; "read 10 tutorials" is not gameplay |
| `testLevel` | +99 | CHECK | SeeD written tests (pre-existing) |
| `party[4]`, coords, module | +104.. | REJECTED | transient position state |

## MISC3 (engine vars 0–255 of the field-var block, base `0x18FE9B8`)

Packing anchored two ways: `seedExp` (+16) == the ff8-memory README's
"SeeD test points" `0x18FE9C8` row; `last_field_id` (+84) == its
"previous map ID" `0x18FEA0C` row.

| Field | Var | Verdict | Notes |
|---|---|---|---|
| `steps` | 4 | CHECK | lifetime u32 (fresh save ~4k, every Disc 2 save ≥147k). Ladder 20k/60k/150k/300k |
| `payslip` | 8 | REJECTED | semantics murky — values ~0..24.5k on every disc, neither a payment count (steps/payslip ratio swings 4..17k) nor obviously total gil. Revisit only with a live diff across one salary tick |
| `seedExp` | 16 | REJECTED | SeeD rank points DECAY (rank drops on bad conduct/every 3rd payslip), so a `>=` check can silently become unreachable for a player who peaked offline; the SeeD written tests already cover this axis monotonically |
| `victory_count` / `battle_escaped` | 20/26 | REJECTED | duplicates of the MISC2 pair (equal in 270/273 saves); MISC2 is the written-first copy |
| `kills[8]` | 28+ | REJECTED | per-character kill ladders would multiply near-identical checks; `monster_kills` covers the axis. Could return as flavor ("Zell: 100 punches landed") if the pool ever needs padding |
| `ko[8]` | 44+ | REJECTED | rewarding getting KO'd invites deliberate wipes — bad incentive next to DeathLink |
| `monster_kills` | 68 | CHECK | total enemies felled (≥ sum of kills[8] in all 273 saves, ~1.8× battles won). Ladder 50/150/300/500 |
| `gils` / `dream_gils` | 72/76 | REJECTED | current wallet, not lifetime earnings — spending un-satisfies it, and AP gil filler self-fires it |
| `current_frame`, `last_field_id`, car rent, music | 80+ | REJECTED | transient |

## LIMITB (limit-break knowledge, base `0x18FE76C`, 16 bytes)

| Field | Verdict | Notes |
|---|---|---|
| `quistis` u16 | CHECK | blue magic (pre-existing) |
| `zell` u16 (+2) | CHECK | Duel finishers. Bit order = Hyne's ZellLBs list; innate mask 0x004F set in all 273 saves, learned bits 4/5/7/8/9 strictly ⊆ Combat King 001–005 ownership. Five checks in the sidequest group; missability mirrors the magazine table (only CK004/Different Beat is renewable) |
| `irvine` u8 (+4) | REJECTED | Shot uses ammo items, nothing is learned; byte constant in the library |
| `selphie` u8 (+5) | REJECTED | Slot list is innate; byte constant in the library |
| `angel_completed/known/pts` | CHECK / — | tricks known = pre-existing checks; `angel_pts` (walk-to-learn progress 0–255 per trick) is transient grind state, REJECTED |

## Character records (8 × 0x98 at `0x18FE0E8`)

| Field | Verdict | Notes |
|---|---|---|
| `exp` (+4) | CHECK | Squall level ladder 10/15/20/30/40 via `u32_ge` on (L−1)×1000. Flat 1000 EXP/level confirmed: Hyne PersoEditor writes `(level−1)*1000`, and every legit maxed save sits at exactly 99000. **The save-header "level" byte is the party average, NOT Squall's** — headers 58–61 coexist with a maxed Squall; do not use it for verification |
| other characters' exp | REJECTED | Squall is never benched and eats most EXP; per-character level ladders would be near-duplicates. "Party max level" was considered and dropped — scaled joiners (Disc 2 min jumps to 13) make it fire without the player leveling anyone |
| `weaponID` (+9) | CHECK | remodels via misc1.unlocked_weapons (pre-existing) |
| `magies[32]` (+0x10) | REJECTED | "distinct spells stocked" self-fires from AP magic filler and un-satisfies on use; `magic_drawn_once` measures the same idea cleanly |
| junction bytes, `compatibility[16]` | REJECTED | junction state is loadout, not progress; compatibility is slow drift + items, and readable only as 16×16 u16 noise |
| `kills`/`KOs` (+0x90/0x92) | REJECTED | duplicates of MISC3 kills/ko |

## GF records (16 × 0x44 at `0x18FDCA8`)

| Field | Verdict | Notes |
|---|---|---|
| `exists` (+17) | CHECK | GF acquisitions (pre-existing) |
| `exp`, `HPs` | REJECTED | GF levels shadow character EXP gain; no independent play axis |
| `completeAbilities[16]` (+20) | CHECK | 2026-09-01 pass: the blocker dissolved — every GF's not-yet-owned mask is unanimous across the library (records are pre-initialized), so the default set is a constant (memory.GF_ABILITY_DEFAULTS) and an AP-granted GF arrives at exactly default. Bit = Hyne ability id. Now: 49 signature-ability checks (`flag_bit`), 16 Mastered checks (`bits_all` on the 22-ability learn list), party ladder 10-200 (`gf_abilities_ge`, beyond-default sum, max 244). All gated on the GF item |
| `APs[24]`, `kills`, `KOs`, `learning` | REJECTED | AP totals/kill counts move with the ability system anyway; learning state is transient |

## Field/world vars (vars 256–1023, worldmap 1280+)

| Cluster | Verdict | Notes |
|---|---|---|
| Chocobo forests (vars 616–622, candidates) | FUTURE | six forests + sanctuary; the var cluster is scouted but the per-forest solved flag is unpinned — needs one live forest-solve diff (`tools/savemap_diff.py`) or a `save_scan corr` pass against saves with the Chicobo card |
| Shumi Village quest (vars 607–623 cluster) | FUTURE | multi-stage statue quest; same treatment as chocobo — one live diff per stage pins it |
| Obel Lake / PuPu / Queen / CC / seals | CHECK | pre-existing |
| Winhill vase (var 387 = dream 3 progress) | FUTURE | var 387 tracks the dream itself, not the four shards; shard flags likely field-local — low priority |
| vars 753–1023 | — | verified free; AP client state lives at 1000+ |

## TTCARDS + TT fields in FIELD (2026-08-31 TT pass)

| Field | Verdict | Notes |
|---|---|---|
| `cards[77]` level ranges | CHECK | 11 commons per level (Hyne card-list order); "all 11 of level N seen" = Card Compendium sets 1-7. Library completion: 175 saves (L1) down to 35 (L5). Level 5 is missable — PuPu (card 47) is a one-chance reward |
| `cards_rare[5]` extended | CHECK | unique-card tiers 85/100/110 (92/54/30 library saves). 100 stays reachable without the four missable-holder rares; 110 does not → filler-only, Disc 4 |
| `card_locations[33]` | REJECTED | which NPC holds each rare — churns with every win/loss; diagnostics at best |
| `tt_defeat_count` / `tt_egality_count` (+118/+120) | REJECTED | losses and draws are trivially throwable — perverse incentive (and the draws u16 sits exactly at the snapshot span's end) |
| `FIELD.tt_rules[8]` (`+0x18FEAC8`) | CHECK | bit3 = Random per Hyne (b0 Open/b1 Same/b2 Plus/b4 Sudden Death/b6 Same Wall/b7 Elemental). Virgin bytes unanimous across every early save (01/02/0C/0E/88/90/DF/C0); rule spreading only ADDS bits, so a cleared virgin bit is a clean abolition signal. Checks: Random abolished in Dollet (60/273 saves), Trabia (54), Centra (29), Lunar Gate (15, filler-only) + "Random Rule Extinct" capstone over all 8 bytes (12 saves, filler-only). New `bits_clear` trigger with a moment>=20 init guard |
| `FIELD.tt_traderules[8]` | REJECTED | "trade rule All" means winner-takes-all games most players actively avoid |
| `FIELD.tt_bgu_victory_count` (var 478, `+0x18FEB96`) | CHECK | wins vs Balamb Garden players — the CC quest's own pacing counter. Bimodal in the library: 0 without card play, 30-129 on every CC-progress save. Ladder 15/40/100 |
| `tt_lastrules/lastregion`, queen tmp vars, `tt_degeneration` | REJECTED | transient rule-carrying state / RNG internals |

## Draw-point state (`0x18FEA2C`)

Already a check group. Two research notes from this pass:

- The ~20 unmapped "???" slots stay unmapped; most are believed to sit in
  one-window areas, which would make them filler-only anyway.
- **Anomaly:** 4 library saves show slot 49 ("Quake, Odine's Laboratory")
  drawn while `magic_drawn_once` lacks Quake's bit — yet the same
  cross-check validates perfectly for slot 44 (FH Ultima, 20/20). Slot 49's
  identity is suspect; worth a live visit before trusting that row. (The
  check still fires on *some* draw point — it may just be misnamed.)

## Not in the savemap at all

Battle-module memory (ally/enemy structs, encounter id) is transient and
already used edge-wise; Chocobo World transfer data and real-time counters
break the state-based catch-up property every check group relies on — both
stay out by design (see `docs/design.md`).

## Net result of these passes

Stat pass, 41 new locations (299 → 340): 5 Zell Duel finishers (sidequest
group) and a new option-gated **stats** group of 36 — Squall level (5),
magic kinds (5), marquee first-draws (8), enemies scanned (4), escapes (3),
monsters felled (4), steps (4), Tonberries (3).

TT pass, 18 more (340 → 358, `tt` group 18 → 36): unique-card tiers
85/100/110, Balamb Garden card-wins 15/40/100, Random-rule abolition ×4 +
extinction capstone, Card Compendium level sets 1-7.

Every trigger is state-based (auto catch-up) and every offset was verified
offline against the library before shipping. Live `VERIFY` items remaining:
the exact action that sets `ennemy_scanned_once` bits, and the slot-49
draw-point identity.

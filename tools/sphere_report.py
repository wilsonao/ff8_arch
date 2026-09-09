"""Item-gated sphere report for the FF8 apworld.

Archipelago's own sphere count treats every free "Cleared: <beat>" story
event as a sphere of its own, which makes an FF8 seed look 12 spheres deep
when it is really two plateaus. This tool collapses the free events: a
sphere here is "every location that becomes reachable once the items of the
previous spheres are in hand, with all free story beats swept". It is the
acceptance test for the sphere-gating work (docs/plan-sphere-gating.md).

Run from the repo root with the venv Python (needs the Archipelago checkout
that the test suite uses, i.e. ./Archipelago with worlds/ff8 linked):

    python tools/sphere_report.py                    # default options, 3 seeds
    python tools/sphere_report.py --preset "SeeD Cadet" --seeds 5
    python tools/sphere_report.py --opt story_gates=off --opt starting_gfs=0
"""

import argparse
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Archipelago"))

from test.bases import WorldTestBase  # noqa: E402
from Fill import distribute_items_restrictive  # noqa: E402
from worlds.ff8.locations import LOCATION_DATA_BY_NAME  # noqa: E402
from worlds.ff8.options import OPTION_PRESETS  # noqa: E402
from worlds.ff8.test import item_spheres  # noqa: E402


class _Harness(WorldTestBase):
    game = "Final Fantasy VIII"
    player = 1
    auto_construct = False

    def runTest(self):
        pass


def generate(options: dict, seed: int):
    harness = _Harness()
    harness.options = options
    harness.world_setup(seed)
    distribute_items_restrictive(harness.multiworld)
    return harness.multiworld


def report(options: dict, seed: int, verbose: bool) -> tuple[int, int]:
    multiworld = generate(options, seed)
    spheres = item_spheres(multiworld, 1)
    unreachable = spheres.pop()
    total = sum(len(s) for s in spheres) + len(unreachable)
    print(f"\n=== seed {seed}: {total} checks, {len(spheres)} item-gated spheres, "
          f"{len(unreachable)} unreachable")
    for index, sphere in enumerate(spheres, 1):
        regions = collections.Counter(loc.parent_region.name for loc in sphere)
        line = f" sphere {index:2d}: {len(sphere):3d} checks"
        if verbose:
            groups = collections.Counter(LOCATION_DATA_BY_NAME[loc.name].group for loc in sphere)
            unlocks = collections.Counter(loc.item.name for loc in sphere if loc.item.advancement)
            print(line)
            print("    regions:", ", ".join(f"{r} {n}" for r, n in regions.most_common()))
            print("    groups: ", ", ".join(f"{g} {n}" for g, n in groups.most_common()))
            print("    unlocks:", ", ".join(f"{i}" for i, _ in unlocks.most_common(10)))
        else:
            top = ", ".join(f"{r} {n}" for r, n in regions.most_common(4))
            print(f"{line}   {top}")
    return len(spheres[0]) if spheres else 0, len(spheres)


def parse_opt(text: str):
    key, _, value = text.partition("=")
    if value.lower() in ("true", "false"):
        return key, value.lower() == "true"
    try:
        return key, int(value)
    except ValueError:
        return key, value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--preset", choices=sorted(OPTION_PRESETS))
    parser.add_argument("--opt", action="append", default=[],
                        help="option override, key=value (repeatable)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    options = dict(OPTION_PRESETS[args.preset]) if args.preset else {}
    for text in args.opt:
        key, value = parse_opt(text)
        options[key] = value
    print("options:", options or "(defaults)")

    firsts, depths = [], []
    for seed in range(args.first_seed, args.first_seed + args.seeds):
        first, depth = report(options, seed, args.verbose)
        firsts.append(first)
        depths.append(depth)
    print(f"\nsphere 1 size: min {min(firsts)} / max {max(firsts)};"
          f" depth: min {min(depths)} / max {max(depths)}")


if __name__ == "__main__":
    main()

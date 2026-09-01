"""Map-area detection data shared by the client and the tracker generator.

The savemap's MISC2.location (memory.CURRENT_LOCATION) is the save-preview
location-name id (0..250, Hyne Locations::fillList order — e.g. 1 "Balamb-
Alcauld Plains", 67 "B-Garden- Cafeteria", 248 "Ultimecia Castle"). The client
maps it to one of the AREAS keys below and publishes changes to Archipelago
data storage (key "ff8_area_<team>_<slot>"), where the PopTracker pack's
autotracking picks it up and activates the matching world-map area tab.

Ids that don't pin the party to one map area (trains, the SeeD exam ship,
chocobo forests, "Wilderness") are deliberately unmapped: the tracker simply
stays on the last area rather than guessing.
"""

# area key -> tab title in the PopTracker pack (tools/gen_tracker_pack.py
# derives the world-map view tabs and the Lua AREA_TABS table from this).
AREAS: dict[str, str] = {
    "balamb":   "Balamb",     # Balamb isle, Balamb Garden, Fire Cavern
    "galbadia": "Galbadia",   # Dollet/Timber/Deling/Winhill continent + G-Garden
    "trabia":   "Trabia",     # Trabia snowfields, T-Garden, Shumi
    "esthar":   "Esthar",     # Esthar continent, FH + Horizon Bridge, lunar sites
    "centra":   "Centra",     # Centra ruins/excavation, orphanage, ocean spots
    "space":    "Space",      # Lunar Base, outer space, the Ragnarok
    "castle":   "Castle",     # Ultimecia's Castle
}


def _spans(area: str, *spans: tuple[int, int] | int) -> dict[int, str]:
    out = {}
    for s in spans:
        lo, hi = (s, s) if isinstance(s, int) else s
        for i in range(lo, hi + 1):
            out[i] = area
    return out


# location-name id -> area key. Unlisted ids (0, blanks, trains 89-91,
# Mystery Dome 196, chocobo forests 227-228, 247/250) intentionally absent.
AREA_BY_LOCATION: dict[int, str] = {
    **_spans("balamb", (1, 4), (64, 88), 92),
    **_spans("galbadia", (5, 25), (93, 145)),
    **_spans("trabia", (26, 37), (190, 195), (197, 204)),
    # 146-158 is Fisherman's Horizon + the Horizon Bridge + Great Salt Lake —
    # all drawn inside the Esthar view. 159-181 is Esthar city and the lunar-
    # side sites (Lunar Gate, Sorceress Memorial, Tears' Point, Lunatic Pandora).
    **_spans("esthar", (38, 49), (51, 53), (146, 168), (170, 181)),
    # 50 Kashkabald Desert and 59 Cactuar Island sit in the Centra view's
    # south-east ocean corner (the pyramid-UFO / Jumbo Cactuar pins).
    **_spans("centra", 50, (54, 63), (182, 189), (205, 207), (215, 218)),
    **_spans("space", (208, 214), (219, 226)),
    **_spans("castle", (229, 246), (248, 249)),
}

assert set(AREA_BY_LOCATION.values()) <= set(AREAS)

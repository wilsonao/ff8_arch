"""PROOF OF CONCEPT: make world-map vehicles (Ragnarok / Garden) boardable
anywhere by patching one engine check at runtime — no game files modified.

Background (static RE of FF8_EN.exe, 2026-09-08; see docs/research notes):

The world-map module decides vehicle boarding in sub_54B860 ("can the player
board this vehicle object here?"), reached from every vehicle touch path:

    1. |vehicle.y - ground.y| < 200
    2. sub_53E730(triangle_bits, VEHICLE type)  -> terrain class allows vehicle
    3. sub_53E730(triangle_bits, AVATAR type)   -> always true on foot
    4. sub_53EAF0(...) < 0                      -> no blocking object

Check 2 is the "location lock" that defeated every save-edit/memory-seeding
attempt: each walkmesh triangle carries per-vehicle traversability bits in
its bytes +0xD..+0xF (bit16 -> type 0x31, bit17 -> type 0x30 [Ragnarok/
Garden tier], bit18 -> chocobo, bit15 -> car), and the triangle under the
PLAYER must carry the touched vehicle's bit. Story park spots always sit on
compliant terrain; arbitrary seeded park spots don't, so the boarding
trigger never fired.

sub_53E730 (module+0x13E730) has exactly two callers, both inside
sub_54B860 — the world-map *movement* traversability test is a separate
inline copy at 0x53E7A0. Forcing sub_53E730 to `return 1` therefore
affects boarding eligibility ONLY:

    original: 55 8b ec a1 f4 5c c7 00 ...   (push ebp; mov ebp,esp; ...)
    patched:  b8 01 00 00 00 c3             (mov eax,1; ret)

Combined with the already-proven pieces (moment windowing for spawn +
seeding ragnarok_pos/bgu_pos + WM flag bits), this should complete the
chain: spawn the vehicle at the player, walk into it, board.

Usage (game running, ideally standing on the world map):
    python tools/poc_ragnarok_board.py status     # verify bytes / dump wm state
    python tools/poc_ragnarok_board.py patch      # apply boarding patch
    python tools/poc_ragnarok_board.py revert     # restore original bytes
    python tools/poc_ragnarok_board.py ragnarok   # full PoC: patch + moment
                                                  # window + seed Ragnarok at
                                                  # player, then interactive
                                                  # restore
    python tools/poc_ragnarok_board.py garden     # same for Balamb Garden

The 'ragnarok'/'garden' modes fake GAME_MOMENT only while you confirm the
test is done, then restore it — NEVER save the game while the fake moment
is applied (quit to title / revert first).
"""
import ctypes
import importlib.util
import os
import struct
import sys

# load ff8/memory.py + ff8/warp.py standalone (the ff8 package __init__ needs
# Archipelago, which we don't want to import just to poke process memory)
_FF8_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "ff8")


def _load(mod: str, fname: str):
    spec = importlib.util.spec_from_file_location(
        mod, os.path.join(_FF8_DIR, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


memory = _load("ff8_memory", "memory.py")
warp = _load("ff8_warp", "warp.py")

# --- static analysis results (FF8_EN.exe, module-relative offsets) ---
PATCH_SITE = 0x13E730            # sub_53E730: per-vehicle terrain-class check
PATCH_ORIG = bytes.fromhex("558beca1f45cc700")   # push ebp; mov ebp,esp; mov eax,[..]
PATCH_NEW = bytes.fromhex("b801000000c3") + b"\x90\x90"  # mov eax,1; ret; nop nop

WM_OBJ_TABLE = 0x1C426C0         # 40-byte records built each wm rebuild
WM_OBJ_STRIDE = 40
WM_OBJ_COUNT = 0x1C45C40         # live object count
WM_AVATAR_TYPE = 0x1C409E0       # 0..9/0x80 on foot, 0x30/0x31/0x32.. riding
WM_CACHED_MOMENT = 0x1C36BDE     # u16 copy of GAME_MOMENT the wm scripts test
WM_TOUCHED_OBJ = 0x875D10        # index of object the player collided with
VEH_INDEX_GLOBALS = {            # object-table index per vehicle object type
    "type1": 0x87664C, "type2": 0x876648 - 4, "type3": 0x876648,
    "type40": 0x876654, "type41": 0x876658,
}
WMSETUS_BUF = 0x1A9DC3C          # wmsetus.obj loaded whole at fixed address
SEC9_SPAWN_SCRIPT = 0x18D0       # placement script (moment-windowed spawn lists)

# spawn thresholds from wmsetus section 9 (windows that first include the
# vehicle objects): Garden-era objects at moment >= 740, Ragnarok at >= 3100
MOMENT_GARDEN = 750
MOMENT_RAGNAROK = 3150

PAGE_EXECUTE_READWRITE = 0x40


def attach() -> memory.FF8Interface:
    ff8 = memory.FF8Interface()
    if not ff8.attach():
        sys.exit("FF8_EN.exe not running (or attach blocked): "
                 + str(ff8.last_attach_error))
    return ff8


def write_code(ff8: memory.FF8Interface, offset: int, data: bytes) -> None:
    """Write into an executable page: unprotect, write, restore protection."""
    addr = ff8.base + offset
    old = ctypes.c_ulong(0)
    handle = ff8.pm.process_handle
    if not ctypes.windll.kernel32.VirtualProtectEx(
            handle, ctypes.c_void_p(addr), len(data),
            PAGE_EXECUTE_READWRITE, ctypes.byref(old)):
        sys.exit("VirtualProtectEx failed")
    ff8.write_bytes(offset, data)
    ctypes.windll.kernel32.VirtualProtectEx(
        handle, ctypes.c_void_p(addr), len(data), old.value,
        ctypes.byref(ctypes.c_ulong(0)))


def code_state(ff8: memory.FF8Interface) -> str:
    cur = ff8.read_bytes(PATCH_SITE, len(PATCH_ORIG))
    if cur == PATCH_ORIG:
        return "original"
    if cur[:len(PATCH_NEW) - 2] == PATCH_NEW[:-2]:
        return "patched"
    return f"UNEXPECTED ({cur.hex(' ')})"


def dump_status(ff8: memory.FF8Interface) -> None:
    print(f"attached, base 0x{ff8.base:X}")
    print(f"boarding terrain check @+0x{PATCH_SITE:X}: {code_state(ff8)}")
    module = ff8.read_u16(memory.MODULE_DISPATCH)
    print(f"module dispatch: {module} ({'worldmap' if module == 2 else 'not worldmap'})")
    print(f"game moment: {ff8.game_moment()}  "
          f"(wm cached copy: {ff8.read_u16(WM_CACHED_MOMENT)})")
    print(f"avatar type: 0x{ff8.read_u32(WM_AVATAR_TYPE):x}")
    count = ff8.read_u32(WM_OBJ_COUNT)
    print(f"live wm objects: {count}")
    if 0 < count <= 40:
        raw = ff8.read_bytes(WM_OBJ_TABLE, count * WM_OBJ_STRIDE)
        for i in range(count):
            rec = raw[i * WM_OBJ_STRIDE:(i + 1) * WM_OBJ_STRIDE]
            x, y, z = struct.unpack_from("<3i", rec, 0)
            print(f"  obj[{i:2}] type 0x{rec[16]:02x} flags3={rec[3]} "
                  f"pos ({x}, {y}, {z})")
    print(f"savemap ragnarok_pos: {ff8.read_bytes(memory.WM_RAGNAROK_POS, 12).hex(' ')}")
    print(f"savemap bgu_pos:      {ff8.read_bytes(memory.WM_BGU_POS, 12).hex(' ')}")
    print(f"savemap vehicle flags: 0x{ff8.read_u8(memory.WM_VEHICLE_FLAGS):02x}")


def apply_patch(ff8: memory.FF8Interface) -> None:
    state = code_state(ff8)
    if state == "patched":
        print("already patched")
        return
    if state != "original":
        sys.exit(f"refusing to patch: bytes at site are {state}")
    write_code(ff8, PATCH_SITE, PATCH_NEW)
    print("boarding terrain check patched (always-boardable)")


def revert_patch(ff8: memory.FF8Interface) -> None:
    if code_state(ff8) == "original":
        print("already original")
        return
    write_code(ff8, PATCH_SITE, PATCH_ORIG)
    print("original bytes restored")


def seed_vehicle(ff8: memory.FF8Interface, pos_off: int, flag: int,
                 moment: int, name: str) -> None:
    if ff8.read_u16(memory.MODULE_DISPATCH) != memory.MODULE_WORLDMAP:
        sys.exit("stand on the WORLD MAP first (module dispatch != 2)")
    print("!! The AP client must be DISCONNECTED: story checks trigger on "
          "GAME_MOMENT thresholds and a faked moment would fire them all. !!")
    if input("AP client stopped? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")
    true_moment = ff8.game_moment()
    if true_moment >= moment:
        print(f"moment {true_moment} already >= {moment}; no faking needed")
        true_moment = None
    apply_patch(ff8)
    # park the vehicle at the player's savemap world position
    char = ff8.read_bytes(memory.WM_CHAR_POS, memory.WM_POS_LEN)
    ff8.write_bytes(pos_off, char)
    ff8.set_bits(memory.WM_VEHICLE_FLAGS, flag)
    if true_moment is not None:
        ff8.write_u16(memory.GAME_MOMENT, moment + 17)
        print(f"moment windowed {true_moment} -> {moment + 17}")
    print(f"{name} parked at your position.")
    print("Trigger a world-map rebuild (enter+exit a battle or location), "
          "then walk into the vehicle. It should board.")
    print("!! Do NOT save while the moment is faked !!")
    try:
        input("Press Enter when done to restore moment + code patch... ")
    except KeyboardInterrupt:
        pass
    if true_moment is not None:
        ff8.write_u16(memory.GAME_MOMENT, true_moment)
        print(f"moment restored to {true_moment}")
    revert_patch(ff8)


# --- Disc-3 relocate test (no moment fake): prove the terrain patch by
# boarding the natively-live Ragnarok on terrain where it normally can't be. ---

def rag_object_pos(ff8: memory.FF8Interface):
    """Live (x, y, z) of the Ragnarok object in the wm object table, or None
    if it isn't currently spawned. Index lives in the type-01 vehicle global."""
    idx = ff8.read_u32(VEH_INDEX_GLOBALS["type1"])
    count = ff8.read_u32(WM_OBJ_COUNT)
    if idx == 0xFFFFFFFF or idx >= count:
        return None
    rec = ff8.read_bytes(WM_OBJ_TABLE + idx * WM_OBJ_STRIDE, WM_OBJ_STRIDE)
    return struct.unpack_from("<3i", rec, 0)


def cmd_warp(ff8: memory.FF8Interface, dest_key: str) -> None:
    if ff8.read_u16(memory.MODULE_DISPATCH) != memory.MODULE_WORLDMAP:
        sys.exit("stand on the WORLD MAP first")
    d = warp.WARP_BY_KEY.get(dest_key)
    if d is None:
        sys.exit("unknown dest; choose from: "
                 + ", ".join(warp.WARP_BY_KEY))
    ff8.write_bytes(memory.WORLD_POS, struct.pack("<3i", d.x, d.y, d.z))
    print(f"warped to {d.name} ({d.x}, {d.y}, {d.z}). "
          "Move one step so the engine reloads the segment.")


def cmd_seedrag(ff8: memory.FF8Interface, dy: int = 1200) -> None:
    """Park the Ragnarok near the player's current savemap world position, in a
    proper Ragnarok position record (savemap qint16[6] = [X, 0, Y, field4=0,
    height, 1]; the player record's field4 is -1, which is wrong for a
    vehicle). Offsets +dy on Y so it sits adjacent, not on top. Sets the
    availability bit. Needs a wm rebuild (enter+flee a battle) to spawn."""
    if ff8.read_u16(memory.MODULE_DISPATCH) != memory.MODULE_WORLDMAP:
        sys.exit("stand on the WORLD MAP first")
    x, _, y, _, h, _ = struct.unpack("<6h", ff8.read_bytes(memory.WM_CHAR_POS, 12))

    def clamp(v):
        return max(-32768, min(32767, v))

    rec = struct.pack("<6h", clamp(x), 0, clamp(y + dy), 0, h, 1)
    ff8.write_bytes(memory.WM_RAGNAROK_POS, rec)
    ff8.set_bits(memory.WM_VEHICLE_FLAGS, memory.WM_FLAG_RAGNAROK)
    print(f"Ragnarok parked at savemap ({clamp(x)}, {clamp(y + dy)}), "
          f"player at ({x}, {y}). Trigger a rebuild (enter+flee a battle) "
          "to spawn the model, then walk to it.")


def cmd_watch(ff8: memory.FF8Interface) -> None:
    """Live telemetry for the boarding test. Prints a compact status line
    ~2 Hz. Stop with Ctrl+C or by creating the stop-file; reverts the code
    patch on exit so the game is never left patched."""
    import time
    stop_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             ".poc_watch_stop")
    if os.path.exists(stop_file):
        os.remove(stop_file)
    print("watching (Ctrl+C or create tools/.poc_watch_stop to stop)...",
          flush=True)
    last_key = None
    last_beat = 0.0
    try:
        while not os.path.exists(stop_file):
            module = ff8.read_u16(memory.MODULE_DISPATCH)
            av = ff8.read_u32(WM_AVATAR_TYPE)
            rag = rag_object_pos(ff8)
            patch = code_state(ff8)
            # a "state key" that ignores small position jitter: report only when
            # module / riding-state / vehicle-presence / patch changes
            ridden = av in (0x30, 0x31, 0x32)
            key = (module, ridden, rag is not None, patch)
            now = time.time()
            if key != last_key or now - last_beat > 10:
                pos = ff8.world_pos()
                tag = "RIDING" if ridden else "on-foot"
                flag = "  <<< " + ("BOARDED!" if ridden else "") if key != last_key else ""
                print(f"[{time.strftime('%H:%M:%S')}] mod={module} "
                      f"avatar=0x{av:<3x} {tag:>7} player={pos} "
                      f"rag_obj={rag} patch={patch}{flag}", flush=True)
                last_key = key
                last_beat = now
            time.sleep(0.4)
    except KeyboardInterrupt:
        pass
    finally:
        revert_patch(ff8)
        if os.path.exists(stop_file):
            os.remove(stop_file)
        print("watch stopped; patch reverted.", flush=True)


def cmd_disc1(ff8: memory.FF8Interface) -> None:
    """Full Disc-1 boarding test with SAFE moment windowing.

    Fakes GAME_MOMENT up to the Ragnarok spawn threshold ONLY while the player
    is on the open world map (or in the transient battle/results modules, so a
    map->battle->map round-trip keeps the vehicle spawned). The instant a menu
    opens (in_menu) or a FIELD/title module loads, or the player is riding, the
    true moment is restored — so no save and no story field-script ever sees
    the fake. The code patch and the true moment are both restored on exit.

    Only ever writes the fake back over its OWN value: if the game changes
    GAME_MOMENT itself (a legit story advance), that new value is adopted as
    the truth instead of being clobbered.
    """
    import time
    if ff8.read_u16(memory.MODULE_DISPATCH) != memory.MODULE_WORLDMAP:
        sys.exit("stand on the WORLD MAP of slot1_save12 first")
    true_moment = ff8.game_moment()
    if true_moment >= MOMENT_RAGNAROK:
        sys.exit(f"moment {true_moment} is already Ragnarok-era; this is the "
                 "Disc-1 test — load slot1_save12")
    fake = MOMENT_RAGNAROK + 17
    print(f"AP client MUST be closed. True moment = {true_moment}, "
          f"will window to {fake} on the world map only.")
    if input("AP client stopped and on slot1_save12 world map? [y/N] "
             ).strip().lower() != "y":
        sys.exit("aborted")

    # seed the Ragnarok next to the player (disc-1 ragnarok_pos is all-zero, so
    # this is the only source and it sticks) using a proper vehicle record
    x, _, y, _, h, _ = struct.unpack("<6h", ff8.read_bytes(memory.WM_CHAR_POS, 12))
    ff8.write_bytes(memory.WM_RAGNAROK_POS,
                    struct.pack("<6h", x, 0, min(32767, y + 1200), 0, h, 1))
    ff8.set_bits(memory.WM_VEHICLE_FLAGS, memory.WM_FLAG_RAGNAROK)
    print(f"Ragnarok seeded near player ({x}, {y}).")
    apply_patch(ff8)

    stop_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             ".poc_watch_stop")
    if os.path.exists(stop_file):
        os.remove(stop_file)
    print("windowing live. Walk into a battle+flee to spawn the vehicle, then "
          "walk into it. Ctrl+C (or tools/.poc_watch_stop) to end.", flush=True)
    faked = False
    last_key = None
    last_beat = 0.0
    try:
        while not os.path.exists(stop_file):
            module = ff8.read_u16(memory.MODULE_DISPATCH)
            in_menu = ff8.read_u8(memory.IN_MENU)
            av = ff8.read_u32(WM_AVATAR_TYPE)
            cur = ff8.game_moment()
            ridden = av in (0x30, 0x31, 0x32)
            # windowing decision: fake only on the open world map / transient
            # battle modules, never in a menu, field, title, or while riding
            want_fake = (module in (memory.MODULE_WORLDMAP, 3, 4, 5)
                         and in_menu == 0 and not ridden)
            if faked and cur != fake:
                # the game moved the moment itself -> adopt it, don't clobber
                true_moment = cur
                faked = False
            if want_fake and not faked:
                ff8.write_u16(memory.GAME_MOMENT, fake)
                faked = True
            elif not want_fake and faked:
                ff8.write_u16(memory.GAME_MOMENT, true_moment)
                faked = False
            rag = rag_object_pos(ff8)
            patch = code_state(ff8)
            key = (module, in_menu, ridden, rag is not None, faked, patch)
            now = time.time()
            if key != last_key or now - last_beat > 10:
                tag = "RIDING" if ridden else "on-foot"
                extra = "  <<< BOARDED!" if ridden and key != last_key else ""
                print(f"[{time.strftime('%H:%M:%S')}] mod={module} menu={in_menu} "
                      f"avatar=0x{av:<3x} {tag:>7} moment={cur} faked={faked} "
                      f"rag_obj={rag} patch={patch}{extra}", flush=True)
                last_key = key
                last_beat = now
            time.sleep(0.15)
    except KeyboardInterrupt:
        pass
    finally:
        # restore truth no matter how we exit
        if faked:
            ff8.write_u16(memory.GAME_MOMENT, true_moment)
        revert_patch(ff8)
        if os.path.exists(stop_file):
            os.remove(stop_file)
        print(f"ended; moment restored to {true_moment}, patch reverted. "
              "Quit slot1_save12 WITHOUT saving.", flush=True)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    ff8 = attach()
    if cmd == "status":
        dump_status(ff8)
    elif cmd == "patch":
        apply_patch(ff8)
    elif cmd == "revert":
        revert_patch(ff8)
    elif cmd == "warp":
        cmd_warp(ff8, sys.argv[2] if len(sys.argv) > 2 else "")
    elif cmd == "seedrag":
        cmd_seedrag(ff8)
    elif cmd == "watch":
        cmd_watch(ff8)
    elif cmd == "disc1":
        cmd_disc1(ff8)
    elif cmd == "ragnarok":
        seed_vehicle(ff8, memory.WM_RAGNAROK_POS, memory.WM_FLAG_RAGNAROK,
                     MOMENT_RAGNAROK, "Ragnarok")
    elif cmd == "garden":
        seed_vehicle(ff8, memory.WM_BGU_POS, memory.WM_FLAG_BGU,
                     MOMENT_GARDEN, "Balamb Garden")
    else:
        sys.exit(f"unknown command {cmd!r} "
                 "(status/patch/revert/warp/seedrag/watch/ragnarok/garden)")


if __name__ == "__main__":
    main()

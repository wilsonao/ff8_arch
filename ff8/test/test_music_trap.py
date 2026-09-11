"""Jukebox trap: the stub handed to the game and the safety gate around it.

The live effect (sd_music_play on a remote thread) can only be seen in the
real process; these tests pin the bytes we hand it and that a mismatched
executable is never called into.
"""

import random
import struct
import unittest

from ..items import TRAP_TABLE
from ..memory import (CURRENT_MUSIC, JUKEBOX_SONGS, PLAY_MIDI, SD_MUSIC_PLAY,
                      SD_MUSIC_PLAY_PROLOGUE, SONG_NAMES, FF8Interface,
                      akao_header, music_call_code, pick_jukebox_song)


class FakeProcess(FF8Interface):
    """Code bytes at sd_music_play/play_midi plus the current-music slots,
    backed by a dict of ranges; records remote calls instead of running them."""

    def __init__(self, prologue: bytes = SD_MUSIC_PLAY_PROLOGUE, hooked: bool = False):
        super().__init__()
        self.base = 0x400000
        self.regions = {
            SD_MUSIC_PLAY: bytearray(prologue),
            PLAY_MIDI: bytearray(b"\xe9\0\0\0\0" if hooked else b"\x51\x55\x8b\x6c\x24"),
            CURRENT_MUSIC: bytearray(8),
        }
        self.calls: list[tuple[bytes, bytes]] = []

    def read_bytes(self, offset: int, size: int) -> bytes:
        for start, buf in self.regions.items():
            if start <= offset and offset + size <= start + len(buf):
                return bytes(buf[offset - start:offset - start + size])
        raise AssertionError(f"unexpected read at {offset:#x}")

    def write_bytes(self, offset: int, data: bytes) -> None:
        for start, buf in self.regions.items():
            if start <= offset and offset + len(data) <= start + len(buf):
                buf[offset - start:offset - start + len(data)] = data
                return
        raise AssertionError(f"unexpected write at {offset:#x}")

    def read_u8(self, offset: int) -> int:
        return self.read_bytes(offset, 1)[0]

    def read_u32(self, offset: int) -> int:
        return struct.unpack("<I", self.read_bytes(offset, 4))[0]

    def _remote_call(self, data: bytes, code_for) -> None:
        self.calls.append((data, code_for(0x7F0000)))


class TestStub(unittest.TestCase):
    def test_akao_header_carries_id_plus_one(self):
        h = akao_header(29)
        self.assertEqual(len(h), 16)
        self.assertEqual(h[:4], b"AKAO")
        self.assertEqual(h[4], 30)

    def test_akao_header_rejects_ids_outside_the_byte(self):
        with self.assertRaises(ValueError):
            akao_header(512)     # streamed .wav tracks aren't reachable this way
        with self.assertRaises(ValueError):
            akao_header(-1)

    def test_call_stub_pushes_cdecl_args_and_cleans_up(self):
        fn, hdr = 0x46B530, 0x7F0000
        code = music_call_code(fn, hdr)
        self.assertEqual(code[:2], b"\x6a\x7f")                       # push 127
        self.assertEqual(code[2], 0x68)
        self.assertEqual(struct.unpack_from("<I", code, 3)[0], hdr)   # push header
        self.assertEqual(code[7:9], b"\x6a\x00")                      # push channel 0
        self.assertEqual(code[9], 0xB8)
        self.assertEqual(struct.unpack_from("<I", code, 10)[0], fn)   # mov eax, fn
        self.assertEqual(code[14:16], b"\xff\xd0")                    # call eax
        self.assertEqual(code[16:19], b"\x83\xc4\x0c")                # add esp, 12
        self.assertEqual(code[-1], 0xC3)                              # ret
        self.assertLessEqual(len(code), 32)   # fits the code half of the 64-byte block


class TestTrapSong(unittest.TestCase):
    def test_pool_is_the_auditioned_five(self):
        self.assertEqual(set(JUKEBOX_SONGS), {70, 64, 81, 91, 92})
        for s in JUKEBOX_SONGS:
            self.assertIn(s, SONG_NAMES)
            self.assertLessEqual(s, 254)          # fits the AKAO id byte
            self.assertNotIn(s, (0, 93))          # FFNx special-cases these
        self.assertEqual(len([t for t in TRAP_TABLE if t.grant[0] == "trap_music"]), 1)

    def test_pick_avoids_the_current_song(self):
        rng = random.Random(1)
        seen = set()
        for _ in range(200):
            s = pick_jukebox_song(70, rng)
            self.assertNotEqual(s, 70)
            seen.add(s)
        self.assertEqual(seen, set(JUKEBOX_SONGS) - {70})
        self.assertIn(pick_jukebox_song(41, rng), JUKEBOX_SONGS)


class TestPlaySong(unittest.TestCase):
    def test_matching_prologue_runs_the_stub_once(self):
        ff8 = FakeProcess()
        self.assertTrue(ff8.play_song(29))
        self.assertEqual(len(ff8.calls), 1)
        data, code = ff8.calls[0]
        self.assertEqual(data, akao_header(29))
        self.assertEqual(code, music_call_code(0x400000 + SD_MUSIC_PLAY, 0x7F0000))

    def test_foreign_prologue_is_never_called(self):
        ff8 = FakeProcess(prologue=b"\x55\x8b\xec" + b"\0" * 11)
        self.assertFalse(ff8.play_song(29))
        self.assertEqual(ff8.calls, [])

    def test_engine_hook_probe(self):
        self.assertFalse(FakeProcess().music_engine_hooked())
        self.assertTrue(FakeProcess(hooked=True).music_engine_hooked())

    def test_current_song_reads_channel_slot(self):
        ff8 = FakeProcess()
        ff8.write_bytes(CURRENT_MUSIC, struct.pack("<II", 41, 0))
        self.assertEqual(ff8.current_song(), 41)
        self.assertEqual(ff8.current_song(1), 0)

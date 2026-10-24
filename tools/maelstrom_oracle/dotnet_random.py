"""Port of .NET Framework 4.x System.Random (Knuth subtractive generator)."""
MBIG = 2147483647
MSEED = 161803398
def _i32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v
class DotNetRandom:
    def __init__(self, seed):
        self.seed_array = [0] * 56
        subtraction = MBIG if seed == -2147483648 else abs(seed)
        mj = _i32(MSEED - subtraction)
        self.seed_array[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            self.seed_array[ii] = mk
            mk = _i32(mj - mk)
            if mk < 0:
                mk += MBIG
            mj = self.seed_array[ii]
        for _ in range(1, 5):
            for i in range(1, 56):
                self.seed_array[i] = _i32(self.seed_array[i] - self.seed_array[1 + (i + 30) % 55])
                if self.seed_array[i] < 0:
                    self.seed_array[i] += MBIG
        self.inext = 0
        self.inextp = 21
    def _internal_sample(self):
        loc_next = self.inext + 1
        loc_nextp = self.inextp + 1
        if loc_next >= 56: loc_next = 1
        if loc_nextp >= 56: loc_nextp = 1
        ret = _i32(self.seed_array[loc_next] - self.seed_array[loc_nextp])
        if ret == MBIG: ret -= 1
        if ret < 0: ret += MBIG
        self.seed_array[loc_next] = ret
        self.inext = loc_next
        self.inextp = loc_nextp
        return ret
    def _sample(self):
        return self._internal_sample() * (1.0 / MBIG)
    def _large_sample(self):
        ret = self._internal_sample()
        if self._internal_sample() % 2 == 0:
            ret = -ret
        d = ret + (MBIG - 1)
        d /= 2 * 2147483647.0 - 1  # 2*int.MaxValue - 1
        return d
    def next(self, *args):
        if not args:
            return self._internal_sample()
        if len(args) == 1:
            return int(self._sample() * args[0])
        lo, hi = args
        rng = hi - lo
        if rng <= MBIG:
            return int(self._sample() * rng) + lo
        return int(self._large_sample() * rng) + lo
if __name__ == "__main__":
    for s in (0, 1, 2, 3, 4, 5, 12345, -7, 2147483647, -2147483648, 161803398, 98400790):
        r = DotNetRandom(s)
        out = [r.next(245) for _ in range(12)] + [r.next(0, 61) for _ in range(12)] + [r.next() for _ in range(4)] + [r.next(-1, MBIG) for _ in range(4)]
        print(f"{s}: " + " ".join(map(str, out)))

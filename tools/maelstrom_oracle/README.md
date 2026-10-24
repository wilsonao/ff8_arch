# Maelstrom oracle (plan-maelstrom-compat.md, Phase 0)

`dotnet_random.py` is a port of .NET Framework 4.x `System.Random` (Knuth
subtractive generator, 32-bit wraparound), the generator every Maelstrom
shuffle draws from. `Oracle.cs` prints reference sequences from the real
thing; `oracle_vectors.txt` is its output for 12 seeds, including both int32
extremes. Verified identical on 2026-10-10.

Rebuild the oracle with the compiler that ships with Windows (from Git Bash
set `MSYS_NO_PATHCONV=1` so the switches survive):

    C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe -nologo -out:Oracle.exe Oracle.cs
    ./Oracle.exe > oracle_vectors.txt
    python dotnet_random.py | diff - oracle_vectors.txt

Phase 0 moves the port to `ff8/maelstrom/dotnet_random.py` and adds a second
harness here that drives the release `Maelstrom.exe` by reflection for the
shuffle fixtures.

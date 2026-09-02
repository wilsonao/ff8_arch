# Drafted upstream PR — Archipelago launcher URI popup feedback

Branch: `launcher-uri-popup-feedback` in the local `Archipelago/` checkout
(commit `ce14e23`, one commit on top of upstream main @ `1d8a6a5`).
Not yet pushed anywhere. To publish: fork ArchipelagoMW/Archipelago (or use an
existing fork), push the branch, open the PR against `main` with the text below.

---

**Title:** `Launcher: dismiss the URI client-picker popup and confirm the launch`

**Labels:** `is: enhancement`, `affects: core`

**Body:**

## What is this fixing or adding?

When a player clicks their slot on a WebHost room page, the Launcher opens the
"Connect to Multiworld" popup to pick a client. Picking one currently gives no
feedback at all: the popup stays open and nothing visibly changes until the
client window appears — which can take a long while, since the spawned client
process re-imports every installed world (slow disks and antivirus scans
stretch this well past a minute on some machines).

In beta testing a third-party world, two out of two testers read that silence
as "the click did nothing", reported the client as broken, and clicked
repeatedly (each landed click launches another client).

This PR makes the popup behave like the main component list already does:

- the popup **dismisses** when a client is chosen, and
- the same **"Opening in a new window..." snackbar** shown by
  `component_action` confirms the launch.

## How was this tested?

On Windows 11, from source (main) and against the frozen 0.6.7 flow it
backports to:

- `Launcher.py "archipelago://slot:@host:port?game=Final Fantasy VIII"` (a
  third-party world with `supports_uri=True`), clicking each popup entry:
  popup closes, snackbar appears, exactly one client process spawns and
  auto-connects with the URI.
- Main-list component buttons are unaffected (they go through
  `component_action`, not this popup).

While testing this on current main I also hit a pre-existing, unrelated crash
in the URI flow: `main()` imports `worlds` (via `handle_uri`) before
`run_gui()`, so the lazy-loading thread dies on
`assert "worlds" not in sys.modules` in `do_loading` and the Launcher sits on
the loading screen forever. Filed separately (see linked issue); this PR
neither causes nor fixes it.

## If this makes graphical changes, please attach screenshots.

(before: popup open, no reaction after click / after: popup closed + snackbar —
screenshots to be attached when opening the PR)

---

# Drafted upstream issue — URI flow breaks lazy world loading on main

**Title:** `Launcher: archipelago:// URI flow crashes the WorldLoading thread (assert "worlds" not in sys.modules)`

**Body:**

On current main (tested at `1d8a6a5`, Windows 11, from source), launching the
Launcher with a WebHost `archipelago://...` link leaves the GUI stuck on the
loading screen:

```
Exception in thread WorldLoading:
  File "Launcher.py", line 312, in do_loading
    assert "worlds" not in sys.modules, "worlds module already loaded."
AssertionError: worlds module already loaded.
```

`main()` calls `handle_uri()` for `archipelago://` arguments, which does
`from worlds.LauncherComponents import components` — importing `worlds` —
before `run_gui()` starts. `Launcher.on_start` then spawns the `WorldLoading`
thread, whose first line asserts `worlds` has not been imported yet. The
thread dies, `finish_loading` is never scheduled, and the Launcher never
leaves the loading screen (the client-picker popup still works on top of it,
but the component list is never built).

Any world-specific client link reproduces it; a plain launch (no URI) is fine.
0.6.7 (eager world loading) is unaffected.

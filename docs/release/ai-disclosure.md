# AI usage disclosure — FF8 Archipelago

*Draft for Discord. Fits in a single message.*

---

**AI disclosure for the FF8 (Steam 2013) Archipelago world**

In the interest of transparency, here's how AI was and wasn't used in making this mod.

**How AI was used:** This project was built with Claude Code (Anthropic's AI coding assistant), with me directing the work. The AI wrote the majority of the code — the apworld, the memory-hook client, the test suite, the PopTracker pack generator — as well as first drafts of the documentation. It also helped analyze the game's savemap: we built a scanner together and ran it over a library of 273 saves to locate and cross-check memory offsets.

**What stayed human:** All design decisions (what gets randomized, the check list, options, presets, logic) are mine. Every offset and check was verified by a human before shipping — offline against the save library, then live in-game via an automated self-test and full playthroughs that I ran and watched myself. Bugs found in live play were diagnosed and fixed the same way. I review the code, cut the releases, and I'm the one answering bug reports.

**What contains no AI:** There is zero AI-generated art or writing in the game itself. The mod patches no files. It reads memory, grants the game's own items, and (since v0.5.0) rewrites a handful of the game's own text strings in memory — draw-point and item names, the pickup lines — so they name the multiworld item a check holds. Those are fixed templates ("Sent [item] to [player]!"), not generated prose. The Community Art tracker variant uses artwork contributed by caedesender (human-made); game assets remain the property of Square Enix and are not redistributed.

If you have concerns or questions about any of this, ask away — happy to go into detail.

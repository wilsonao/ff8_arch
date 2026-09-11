# Discord reply to Hdot and Hukos (draft, post with the v0.6.0 announcement)

Thanks for the full write-up, that sync report is the most useful feedback
the project has had. What came out of it:

**Fixed in v0.5.0**
- DeathLink can no longer be dodged. A received death now sticks until your
  party actually wipes: if it lands on the killing blow the win still counts
  and it takes your next fight, and Phoenix Downs on the field only delay it
  the same way.
- Warp items now only exist for places that are in your seed (an edea seed
  was shipping Disc 2/3 warps), and the option text says plainly that warps
  move you, they never skip story.
- New "Sync" preset: edea goal, only on-path check groups, no traps, and the
  big lock tables off so about half of the Disc 1 checks hold other players'
  items instead of your own. Plus two beat-end checks that were missing
  (FH Garden repaired, Ragnarok landing) and a guide note recommending the
  speed booster.

**Story Keys (shipped in v0.6.0, off by default)**
You're right that everything was soft-gated. v0.6.0 adds key items that
physically lock the world-map entrances (towns, dungeons, Lunar Gate,
Tears' Point); in `story` mode the story-required ones are hard gates, so a
rushed story still needs items other players hold. The keys also carry the
warp, so the standalone warp items go away. Details in the release post
above.

**On sequence breaking (Hukos)**
Spot on: FF8 decides per entrance, from the story moment, whether a town
exists yet, which is why an early Ragnarok can't get you into Deling. Story
order stays fixed (faking the moment is proven to crash). The other
direction works mechanically: flipping those entrance records let a Disc 1
save walk into Deling City with the Ragnarok. But the town's interiors
assume the story state (the hotel lounge soft-locked), so early entry only
ships per town once its interiors are surveyed. Check access, not plot
skips.

**Maelstrom**
Good pointer. It patches files once and doesn't run during play, so it can
sit under our client. Boss, draw point, GF ability and card shuffles will
collide with our check detection; shop, loot, weapon and music shuffles
should be safe. A compatibility matrix is on the list; if anyone is already
running both, tell me what breaks.

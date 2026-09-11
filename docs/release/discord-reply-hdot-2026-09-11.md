# Discord reply to Hdot and Hukos (draft, post with v0.5.0)

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

**Next: Story Keys**
You're right that everything is soft-gated today. The next feature is key
items that physically lock world-map entrances (towns, dungeons, Lunar
Gate, Tears' Point), with the story-required ones as hard gates so a rushed
story still needs items other players hold. The keys also carry the warp,
so the standalone warp items go away.

**On sequence breaking (Hukos)**
Spot on: FF8 decides per entrance, from the story moment, whether a town
exists yet, which is why an early Ragnarok can't get you into Deling. Story
order will stay fixed (faking the moment is proven to crash). What we are
testing is the other direction: flipping those entrance records so an early
Ragnarok plus the right key lets you into a Disc 2 town for its draw points,
cards and pickups. Check access, not plot skips.

**Maelstrom**
Good pointer. It patches files once and doesn't run during play, so it can
sit under our client. Boss, draw point, GF ability and card shuffles will
collide with our check detection; shop, loot, weapon and music shuffles
should be safe. A compatibility matrix is on the list; if anyone is already
running both, tell me what breaks.

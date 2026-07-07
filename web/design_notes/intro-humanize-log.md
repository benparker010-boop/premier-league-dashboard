# Intro humanize loop — iteration log

Persistent memory for the recurring "humanize-intro-parker-kit" task. Every
iteration: analyze → self-prompt → execute → verify → record here. Never
re-attempt an idea marked FAILED/REVERTED without a genuinely new approach.

## Standing user directives

- 2026-07-06: Focus on APPEARANCE, not the kick. Spend iterations on visual
  anatomy and rendering (silhouette, proportions, musculature, head/face,
  hands, kit detail, shading, ground shadows). The kick animation is accepted
  as-is — do not rework biomechanics/timing/easing; touch motion code only if
  it visibly breaks appearance (detached or interpenetrating limbs). This
  supersedes the motion-related ideas queued below (foot roll, toe point,
  shoulder counter-rotation, forward-lean scaling) — SKIP those.

## Iteration 1 — 2026-07-06

Analysis: figure reads as a capsule mannequin. Tube limbs (no musculature),
straight-sided trunk (no spine curve, chest or lumbar profile), featureless
ball head, flat single-color fills.

Self-prompts:
1. Replace capsule limbs with bezier muscle segments — thigh (quad/ham mass),
   calf bulge tapering to the ankle, deltoid/bicep upper arm, forearm taper.
   Accept when legs/arms read athletic, not tubular.
2. Reshape the trunk: asymmetric bezier outline — fuller chest curve on the
   front, scapula-to-lumbar hollow down the back, spine curvature coming from
   the pose stations. Accept when the backswing frame shows a visibly arched
   back.
3. Give the head a face: cranium + jaw/chin wedge oriented by the head-track
   facing direction, plus a hair crescent over the top-back of the skull.
   Accept when the head reads as a directed face, not a ball.
4. Volume shading: consistent upper-left key light via cross-axis gradients
   on every mass (keep the teal rim). Accept when the figure reads rounded.

Results: ALL FOUR SHIPPED.
1. DONE — muscle() bezier segments (quad/ham thigh, calf bulge → slim ankle,
   deltoid/bicep, forearm taper). Legs/arms clearly athletic in every frame.
2. DONE — asymmetric trunk (chest 1.18x front curve, 0.92/0.84 scapula→lumbar
   back). Backswing frame shows the arched back.
3. DONE — cranium + jaw wedge + hair crescent, all rotating with the
   head-track tilt. Head reads as a directed face.
4. DONE — crossGrad() upper-left key light on every mass + kept teal rim.
FIXED IN-FLIGHT: first cuff attempt (w 0.024 @ lerp 0.46-0.56) rendered as
glowing shoulder blobs — slimmed to 0.017/0.015 @ 0.5-0.56. Don't re-widen.
Verified: behavior contract (once-ever, replay, skip, FLIP landing ≤0.07px),
production build clean.

Ideas queued for next iteration (appearance-only per the standing directive):
- Fingers/fist hint at desktop scale (curled hand path instead of a circle).
- Shirt-hem and sleeve secondary lag (one-frame cloth follow) — risky, test
  carefully, revert on jitter.
- Ground contact shadows under the feet (soft ellipse, fades with dissolve).
- SKIP per standing directive (motion, not appearance): foot articulation/
  heel-strike roll, toe plantarflex, forward-lean-with-speed, shoulder
  counter-rotation against hips.

## Iteration 2 — 2026-07-06 (out-of-band, run manually by Ben mid-session)

Context: Ben generated an AI reference photo of a back-view "PARKER AI" kit
(dark teal shirt/shorts/socks, bright teal collar/cuffs/sock-top trim, a
glowing constellation-ball graphic on the upper back, "PARKER AI" printed
across the shoulders). It's a BACK-VIEW STANDING photo — doesn't match the
intro's SIDE-PROFILE kick camera angle, so it was used as a kit/appearance
style reference only, not a photo-cutout rig. This is squarely on-directive
(appearance, not kick mechanics).

Self-prompts:
1. Add a small glowing constellation-ball badge on the shirt back, matching
   the reference photo's graphic and echoing the football/logo mesh motif.
   Accept when it reads as a deliberate kit graphic, not clutter.
2. Reposition "PARKER AI" higher on the back (just under the collar, per the
   reference's name-band placement) instead of mid-torso.
3. Give the socks a double-stripe top (reference shows two bands) instead of
   a single trim band.

Results: ALL THREE SHIPPED.
1. DONE — shirtBadge(): 8-node constellation ball + bright core, additive
   glow, positioned below the wordmark, rotates with torso lean. Reads
   clearly as a kit graphic at the design's canvas scale.
2. DONE — wordmark moved to lerpPt(neck, chest, 0.62).
3. DONE — sock stripes split into two thin trim bands (0.44-0.485 and
   0.53-0.575 of the knee-ankle segment) over the sock body.
BUGS FOUND AND FIXED (not part of the self-prompts, found during verify):
- Wordmark maxW (0.15fh) was WIDER than the actual chest span (~0.116fh),
  so "PARKER AI" silently overflowed off the chest onto the arm at larger
  scales. Fixed: maxW → 0.1fh, base fpx → 0.032fh. Verified by direct
  measureText against fh=340 (34px text vs 34px cap, fits exactly) — don't
  widen maxW again without re-checking against the real chest width (n2*2).
- The arm cuff band (lerp 0.5-0.56 of sh-el, radius 0.017/0.015fh) was
  SHORTER along its own axis than its radius, so it rendered as a solid
  blob instead of a band. Fixed: widened to lerp 0.44-0.6, radius reduced to
  0.013/0.011fh. General lesson for future limb()/muscle() trim bands: keep
  the lerp-range length clearly greater than the radius, or it collapses
  into a circle.
Verified: behavior contract (once-ever, replay, skip, FLIP landing exact),
production build clean.

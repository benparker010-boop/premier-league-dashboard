# Intro humanize loop — iteration log

Persistent memory for the recurring "humanize-intro-parker-kit" task. Every
iteration: analyze → self-prompt → execute → verify → record here. Never
re-attempt an idea marked FAILED/REVERTED without a genuinely new approach.

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

Ideas queued for next iteration:
- Foot articulation: heel-strike/toe-off roll during the run steps; point the
  toe (plantarflex) through the strike.
- Fingers/fist hint at desktop scale (curled hand path instead of a circle).
- Shirt-hem and sleeve secondary lag (one-frame cloth follow) — risky, test
  carefully, revert on jitter.
- Slight forward lean scaling with run speed; shoulders counter-rotating
  against hips during the swing (rotate shoulder x-offsets procedurally).
- Ground contact shadows under the feet (soft ellipse, fades with dissolve).

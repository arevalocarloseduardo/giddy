# Giddy Avatar System V2

Giddy V2 is a versioned performance system for the 240x240 RGB565 display. It keeps the existing firmware emotion names stable while allowing the visual character to evolve independently.

## Character direction

- Friendly, attentive and capable. Never infantile or hyperactive.
- Emotion comes from gaze, timing and posture before decorative effects.
- Motion confirms what the product is doing: listening, thinking, speaking, connecting or resting.
- Idle motion is quiet. Strong motion is reserved for a meaningful state change.
- The face remains readable from one meter away and under imperfect viewing conditions.

## Variants

- `core`: balanced default for the product and commercial photography.
- `soft`: rounder and warmer for hospitality, care and home use.
- `focus`: quieter and more precise for work environments.

All variants implement the same emotion contract. A future avatar team can add a new variant without changing assistant logic.

## Motion rules

- Start feedback immediately when state changes.
- Use eased or spring-like transitions instead of linear movement.
- Keep idle motion below two logical pixels when possible.
- Preserve a stable face center so loops do not look shaky.
- Use anticipation and settle frames for one-shot lifecycle animations.
- Avoid flashing, full-screen brightness changes and constant decorative particles.

## Output contract

Each generated variant contains firmware-ready GIFs, `manifest.json`, `review-sheet.jpg` and `motion-reel.gif`. Emotion filenames match the current firmware contract, including the `robot_2` alias.

Generate the default variant:

```powershell
python generate_giddy_v2.py --variant core
```

Generate every art direction for review:

```powershell
python generate_giddy_v2.py --variant all
```

Validate the exact collection that will be packaged in firmware:

```powershell
python validate_giddy_v2.py ../../firmware/custom_emoji/giddy-v2-core-240
```

The current production collection must only be changed after the review sheet and motion reel have been inspected on desktop and on the physical display.

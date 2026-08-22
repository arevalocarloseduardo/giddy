# Giddy V3 Selected Design

The active Giddy face is the second tile in
`concepts/giddy-leaf-focus-reference.png`.

## Identity

- Two mirrored organic blue leaf shapes.
- Inner tips slope downward toward the center.
- Dark oval pupils sit low and inward.
- One small white reflection sits near each inner lower pupil edge.
- The neutral mouth is a short blue horizontal signal.
- Black background, cyan upper rim and deep-blue lower volume.

## Production

- Generator: `../v2/generate_giddy_v2.py --variant leaf`
- Review: `../v2/output/giddy-v2-leaf-240/review-sheet.jpg`
- Firmware collection: `../../firmware/custom_emoji/giddy-v3-leaf-240`

## Refinement 2.4.18

- Eyes are taller and rounder, with fully curved outer corners and centered pupils.
- The feline wedge silhouette is intentionally excluded from the identity.
- The `music` state is a complete guitar performance with animated arms, strumming and notes.

## Image Creation 2.4.19

- The `painting` state shows Giddy working at an easel with a moving brush and palette.
- Image previews use display-native 240x240 PNG files so the ESP32 can decode them reliably.
- Firmware selector: `../../firmware/main/CMakeLists.txt`

The geometric Signal direction remains archived for comparison. It is not the
active firmware face.

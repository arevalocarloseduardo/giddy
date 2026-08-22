# Giddy Signal V3

> Archived direction. This is not the selected or active Giddy face. See
> `SELECTED_DESIGN.md` for the approved organic leaf design.

Giddy Signal uses two same-direction open light modules as its proprietary face signature. The right module sits higher and carries a slight tilt, matching the selected second concept. It avoids human eye anatomy, gender coding and generic emoji construction.

## Direction

- Adult, friendly and capable.
- Abstract rather than humanoid.
- Expressive through aperture, spacing, tilt, asymmetry and timing.
- No pupils, irises, eyelashes, eyebrows or decorative emotion icons.
- Limited OLED palette with restrained glow.

## Motion language

- Elasticity stays between zero and four percent.
- State changes use anticipation and a controlled settle.
- Idle movement remains below two logical pixels.
- Primary action communicates state; secondary action only reinforces it.
- Loops keep a stable center and avoid mechanical constant-speed motion.

## Contract

The collection preserves all 31 firmware emotion filenames. `robot_2.gif` remains an alias of `neutral.gif` for compatibility.

```powershell
python generate_giddy_signal.py
python validate_giddy_signal.py output/giddy-v3-signal-240
```

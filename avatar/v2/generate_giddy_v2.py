"""Generate the Giddy V2 avatar system for the 240x240 RGB565 display.

The renderer keeps the firmware emotion contract stable while giving designers
three interchangeable visual directions: core, soft and focus.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


LOGICAL_SIZE = 240
SCALE = 3
CANVAS = LOGICAL_SIZE * SCALE


@dataclass(frozen=True)
class Variant:
    name: str
    eye_width: float
    eye_height: float
    eye_radius: float
    eye_gap: float
    pupil_width: float
    pupil_height: float
    glow: float
    mouth_y: float
    shape: str = "rounded"


VARIANTS = {
    "core": Variant("core", 62, 48, 19, 25, 14, 23, 0.78, 169),
    "soft": Variant("soft", 68, 55, 23, 21, 15, 25, 0.86, 173),
    "focus": Variant("focus", 66, 40, 17, 27, 13, 20, 0.68, 165),
    "leaf": Variant("leaf", 59, 58, 25, 24, 20, 31, 0.76, 169, "leaf"),
}

PALETTE = {
    "ink": (0, 0, 0, 255),
    "edge": (23, 112, 238, 255),
    "deep": (9, 43, 111, 255),
    "mid": (28, 139, 255, 255),
    "light": (113, 232, 255, 255),
    "white": (222, 252, 255, 255),
    "pupil": (3, 17, 54, 245),
    "detail": (97, 210, 255, 210),
    "warm": (255, 126, 112, 235),
    "gold": (255, 196, 84, 240),
}


def p(value: float) -> int:
    return int(round(value * SCALE))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def spring(value: float, overshoot: float = 0.08) -> float:
    value = clamp(value)
    return 1.0 - math.exp(-7.2 * value) * math.cos((8.0 + overshoot * 12.0) * value)


def rgb565_palette(palette: list[int]) -> list[int]:
    snapped: list[int] = []
    for index in range(0, len(palette), 3):
        red, green, blue = palette[index : index + 3]
        r5, g6, b5 = red >> 3, green >> 2, blue >> 3
        snapped.extend(
            ((r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2))
        )
    return snapped


def rounded_mask(width: int, height: int, radius: int) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, width - 1, height - 1), radius=max(1, radius), fill=255
    )
    return mask


def leaf_mask(width: int, height: int, side: int) -> Image.Image:
    """Soft organic eye with a subtle inward taper and no feline corners."""
    def cubic(start, control_a, control_b, end, steps=28):
        result = []
        for index in range(steps + 1):
            t = index / steps
            inv = 1 - t
            x = inv**3 * start[0] + 3 * inv**2 * t * control_a[0] + 3 * inv * t**2 * control_b[0] + t**3 * end[0]
            y = inv**3 * start[1] + 3 * inv**2 * t * control_a[1] + 3 * inv * t**2 * control_b[1] + t**3 * end[1]
            result.append((int(x), int(y)))
        return result

    top_outer = (width * 0.12, height * 0.18)
    top_inner = (width * 0.79, height * 0.10)
    bottom_inner = (width * 0.86, height * 0.82)
    bottom_outer = (width * 0.24, height * 0.88)
    points = cubic(
        top_outer,
        (width * 0.30, height * 0.02),
        (width * 0.66, height * 0.02),
        top_inner,
    )
    points += cubic(
        top_inner,
        (width * 0.93, height * 0.18),
        (width * 0.97, height * 0.60),
        bottom_inner,
    )[1:]
    points += cubic(
        bottom_inner,
        (width * 0.69, height * 0.97),
        (width * 0.36, height * 0.98),
        bottom_outer,
    )[1:]
    points += cubic(
        bottom_outer,
        (width * 0.06, height * 0.76),
        (width * 0.03, height * 0.38),
        top_outer,
    )[1:]
    if side > 0:
        points = [(width - 1 - x, y) for x, y in points]
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def quadratic_points(
    start: tuple[float, float], control: tuple[float, float], end: tuple[float, float], steps: int = 48
) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for index in range(steps + 1):
        t = index / steps
        inv = 1.0 - t
        x = inv * inv * start[0] + 2 * inv * t * control[0] + t * t * end[0]
        y = inv * inv * start[1] + 2 * inv * t * control[1] + t * t * end[1]
        points.append((p(x), p(y)))
    return points


class FaceFrame:
    def __init__(self, variant: Variant):
        self.variant = variant
        self.emissive = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        self.accents = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    def _paste_center(self, piece: Image.Image, center: tuple[float, float]) -> None:
        left = p(center[0]) - piece.width // 2
        top = p(center[1]) - piece.height // 2
        self.emissive.alpha_composite(piece, (left, top))

    def eye(
        self,
        center: tuple[float, float],
        *,
        side: int,
        openness: float = 1.0,
        width_scale: float = 1.0,
        height_scale: float = 1.0,
        rotation: float = 0.0,
        gaze_x: float = 0.0,
        gaze_y: float = 0.0,
        smile: float = 0.0,
        lid: float = 0.0,
        warmth: float = 0.0,
    ) -> None:
        width = max(p(18), p(self.variant.eye_width * width_scale))
        open_value = max(0.055, openness)
        height = max(p(3.2), p(self.variant.eye_height * height_scale * open_value))
        radius = min(p(self.variant.eye_radius), width // 2, max(2, height // 2))
        mask = leaf_mask(width, height, side) if self.variant.shape == "leaf" else rounded_mask(width, height, radius)

        if smile > 0.0 and height > p(9):
            cut = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(cut)
            depth = int(height * (0.38 + 0.26 * clamp(smile)))
            draw.ellipse((-width // 5, height - depth, width + width // 5, height + depth), fill=255)
            mask = Image.composite(Image.new("L", mask.size, 0), mask, cut)

        if lid > 0.0:
            draw = ImageDraw.Draw(mask)
            draw.rectangle((0, 0, width, int(height * 0.5 * clamp(lid))), fill=0)

        fill = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(fill)
        for y in range(height):
            t = y / max(1, height - 1)
            if t < 0.48:
                local = t / 0.48
                top, bottom = PALETTE["light"], PALETTE["mid"]
            else:
                local = (t - 0.48) / 0.52
                top, bottom = PALETTE["mid"], PALETTE["deep"]
            color = tuple(int(top[i] + (bottom[i] - top[i]) * local) for i in range(4))
            if warmth:
                warm = PALETTE["warm"]
                color = tuple(int(color[i] * (1 - warmth * 0.22) + warm[i] * warmth * 0.22) for i in range(4))
            draw.line((0, y, width, y), fill=color)
        fill.putalpha(mask)

        outline = Image.new("RGBA", (width, height), (130, 241, 255, 0))
        if self.variant.shape == "leaf":
            inset = mask.filter(ImageFilter.MinFilter(7))
            edge = ImageChops.subtract(mask, inset).point(lambda value: int(value * 0.62))
            outline.putalpha(edge)
        else:
            ImageDraw.Draw(outline).rounded_rectangle(
                (p(0.7), p(0.7), width - p(0.7), height - p(0.7)),
                radius=max(1, radius - p(0.7)),
                outline=(128, 235, 255, 150),
                width=max(1, p(0.9)),
            )
            outline.putalpha(Image.composite(outline.getchannel("A"), Image.new("L", mask.size, 0), mask))
        fill.alpha_composite(outline)

        # Closed smiling eyes read as a clean gesture. A clipped pupil makes the
        # expression look accidental, especially on the physical 1.54" panel.
        if height > p(12) and openness > 0.25 and smile < 0.35:
            pupil_w = max(p(5), p(self.variant.pupil_width * width_scale))
            pupil_h = min(height - p(5), p(self.variant.pupil_height * height_scale))
            pupil = Image.new("RGBA", (pupil_w, pupil_h), (0, 0, 0, 0))
            if self.variant.shape == "leaf":
                ImageDraw.Draw(pupil).ellipse((0, 0, pupil_w - 1, pupil_h - 1), fill=PALETTE["pupil"])
            else:
                ImageDraw.Draw(pupil).rounded_rectangle(
                    (0, 0, pupil_w - 1, pupil_h - 1),
                    radius=max(1, pupil_w // 2),
                    fill=PALETTE["pupil"],
                )
            glint_r = max(p(1.5), pupil_w // 6)
            glint_x = pupil_w * 0.16 if self.variant.shape == "leaf" else pupil_w * 0.18
            glint_y = pupil_h * 0.12
            ImageDraw.Draw(pupil).ellipse(
                (glint_x, glint_y, glint_x + glint_r, glint_y + glint_r),
                fill=PALETTE["white"],
            )
            if self.variant.shape == "leaf":
                pupil_center = width * (0.57 if side < 0 else 0.43)
                px = int(pupil_center - pupil_w / 2 + p(clamp(gaze_x, -1, 1) * 5))
                py = int(height * 0.54 - pupil_h / 2 + p(clamp(gaze_y, -1, 1) * 3))
            else:
                px = width // 2 - pupil_w // 2 + p(clamp(gaze_x, -1, 1) * 7)
                py = height // 2 - pupil_h // 2 + p(clamp(gaze_y, -1, 1) * 5)
            pupil_masked = Image.new("RGBA", fill.size, (0, 0, 0, 0))
            pupil_masked.alpha_composite(pupil, (px, py))
            pupil_masked.putalpha(Image.composite(pupil_masked.getchannel("A"), Image.new("L", mask.size, 0), mask))
            fill.alpha_composite(pupil_masked)

        sheen = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(sheen).ellipse(
            (width * 0.10, height * 0.03, width * 0.72, height * 0.32),
            fill=(225, 252, 255, 52),
        )
        sheen = sheen.filter(ImageFilter.GaussianBlur(p(2.2)))
        sheen.putalpha(Image.composite(sheen.getchannel("A"), Image.new("L", mask.size, 0), mask))
        fill.alpha_composite(sheen)

        if rotation:
            fill = fill.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
        self._paste_center(fill, center)

    def brow(self, center: tuple[float, float], tilt: float = 0.0, lift: float = 0.0, alpha: int = 150) -> None:
        draw = ImageDraw.Draw(self.accents)
        half = 19
        y = center[1] - 35 - lift
        delta = math.tan(math.radians(tilt)) * half
        draw.line(
            (p(center[0] - half), p(y - delta), p(center[0] + half), p(y + delta)),
            fill=(98, 213, 255, alpha),
            width=p(2.1),
        )

    def mouth(
        self,
        *,
        width: float = 36,
        curve: float = 4,
        openness: float = 0.0,
        x: float = 120,
        y: float | None = None,
        tilt: float = 0.0,
        warmth: float = 0.0,
    ) -> None:
        y = self.variant.mouth_y if y is None else y
        layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        color = PALETTE["light"]
        if warmth:
            warm = PALETTE["warm"]
            color = tuple(int(color[i] * (1 - warmth * 0.3) + warm[i] * warmth * 0.3) for i in range(4))
        if openness > 0.12:
            w, h = p(width), p(7 + openness * 15)
            box = (p(x) - w // 2, p(y) - h // 2, p(x) + w // 2, p(y) + h // 2)
            draw.rounded_rectangle(box, radius=h // 2, fill=PALETTE["deep"], outline=color, width=p(2.4))
            if openness > 0.55:
                draw.arc((box[0] + p(6), box[1] + p(5), box[2] - p(6), box[3] + p(4)), 185, 355, fill=PALETTE["warm"], width=p(2))
        else:
            points = quadratic_points((x - width / 2, y - tilt), (x, y + curve), (x + width / 2, y + tilt))
            stroke = 2.7 if self.variant.shape == "leaf" else 4.2
            draw.line(points, fill=color, width=p(stroke), joint="curve")
            radius = p(stroke / 2)
            for point in (points[0], points[-1]):
                draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), fill=color)
        self.emissive.alpha_composite(layer)

    def side_waves(self, phase: float) -> None:
        draw = ImageDraw.Draw(self.accents)
        for side in (-1, 1):
            anchor = 48 if side < 0 else 192
            for index in range(2):
                pulse = (phase + index * 0.25) % 1.0
                radius = p(18 + index * 9 + pulse * 4)
                cx, cy = p(anchor), p(111)
                box = (cx - radius, cy - radius, cx + radius, cy + radius)
                alpha = int(145 * (1 - 0.25 * index) * (1 - 0.35 * pulse))
                angles = (112, 248) if side < 0 else (-68, 68)
                draw.arc(box, *angles, fill=(89, 205, 255, alpha), width=p(1.6))

    def dots(self, count: int, phase: float = 0.0) -> None:
        draw = ImageDraw.Draw(self.accents)
        for index in range(count):
            x = 177 + index * 17
            y = 67 - index * 13 + math.sin(phase * math.tau + index) * 2
            radius = 2.5 + index * 0.8
            draw.ellipse((p(x - radius), p(y - radius), p(x + radius), p(y + radius)), fill=PALETTE["detail"])

    def spark(self, center: tuple[float, float], size: float, alpha: int = 210) -> None:
        draw = ImageDraw.Draw(self.accents)
        cx, cy, s = p(center[0]), p(center[1]), p(size)
        color = (183, 241, 255, alpha)
        draw.line((cx - s, cy, cx + s, cy), fill=color, width=p(1.5))
        draw.line((cx, cy - s, cx, cy + s), fill=color, width=p(1.5))

    def ring(self, radius: float, alpha: int = 100) -> None:
        draw = ImageDraw.Draw(self.accents)
        r = p(radius)
        cx, cy = p(120), p(111)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(49, 163, 255, alpha), width=p(1.4))

    def tear(self, center: tuple[float, float], alpha: int = 220) -> None:
        draw = ImageDraw.Draw(self.accents)
        x, y = p(center[0]), p(center[1])
        draw.polygon(((x, y - p(7)), (x - p(5), y + p(4)), (x + p(5), y + p(4))), fill=(99, 211, 255, alpha))
        draw.ellipse((x - p(5), y - p(1), x + p(5), y + p(8)), fill=(99, 211, 255, alpha))

    def heart(self, center: tuple[float, float], size: float, alpha: int = 240) -> None:
        draw = ImageDraw.Draw(self.accents)
        x, y, s = p(center[0]), p(center[1]), p(size)
        color = (255, 115, 128, alpha)
        draw.ellipse((x - s, y - s // 2, x, y + s // 2), fill=color)
        draw.ellipse((x, y - s // 2, x + s, y + s // 2), fill=color)
        draw.polygon(((x - s, y), (x + s, y), (x, y + int(s * 1.35))), fill=color)

    def music_note(self, center: tuple[float, float], size: float, phase: float, mirrored: bool = False) -> None:
        draw = ImageDraw.Draw(self.accents)
        bounce = math.sin(phase * math.tau) * 3
        x, y = center[0], center[1] + bounce
        direction = -1 if mirrored else 1
        color = (122, 224, 255, 220)
        draw.ellipse((p(x - size * 0.42), p(y + size * 0.56), p(x + size * 0.42), p(y + size * 1.18)), fill=color)
        draw.line((p(x + direction * size * 0.32), p(y + size * 0.76), p(x + direction * size * 0.32), p(y - size * 0.72)), fill=color, width=p(2.2))
        draw.line((p(x + direction * size * 0.32), p(y - size * 0.72), p(x + direction * size * 0.98), p(y - size * 0.42)), fill=color, width=p(2.2))

    def guitar(self, phase: float, sway: float) -> None:
        """Compact guitar performance staged below the eyes."""
        draw = ImageDraw.Draw(self.emissive)
        bob = 1.5 * math.sin(phase * math.tau * 2)
        shift = sway * 0.28

        def point(x: float, y: float) -> tuple[int, int]:
            return p(x + shift), p(y + bob)

        body = (255, 151, 61, 248)
        body_light = (255, 216, 122, 255)
        body_dark = (157, 61, 30, 255)
        cyan = (116, 224, 255, 245)
        ink = (5, 20, 48, 255)

        # Neck and headstock sit behind the hands and body.
        draw.line((point(126, 171), point(196, 135)), fill=body_dark, width=p(13))
        draw.line((point(127, 168), point(196, 132)), fill=body_light, width=p(7))
        hx, hy = point(201, 130)
        draw.rounded_rectangle((hx - p(8), hy - p(6), hx + p(9), hy + p(6)), radius=p(4), fill=body)

        # The overlapping circles give the tiny guitar a readable waist.
        ux, uy = point(107, 174)
        lx, ly = point(104, 193)
        draw.ellipse((ux - p(24), uy - p(19), ux + p(24), uy + p(19)), fill=body)
        draw.ellipse((lx - p(31), ly - p(24), lx + p(31), ly + p(24)), fill=body)
        draw.polygon((point(84, 166), point(128, 163), point(133, 198), point(75, 200)), fill=body)
        draw.arc((lx - p(28), ly - p(21), lx + p(28), ly + p(21)), 18, 195, fill=body_light, width=p(3))

        sx, sy = point(108, 181)
        draw.ellipse((sx - p(10), sy - p(10), sx + p(10), sy + p(10)), fill=ink, outline=body_light, width=p(2))
        draw.line((point(83, 198), point(111, 198)), fill=body_dark, width=p(4))
        for offset in (-2, 0, 2):
            draw.line((point(86, 191 + offset), point(204, 128 + offset)), fill=(228, 246, 255, 215), width=max(1, p(0.7)))

        # One hand holds the neck while the other visibly strums four beats.
        draw.line((point(177, 160), point(157, 150)), fill=cyan, width=p(8))
        fx, fy = point(157, 150)
        draw.ellipse((fx - p(6), fy - p(6), fx + p(6), fy + p(6)), fill=cyan)
        strum = 8 * math.sin(phase * math.tau * 4)
        draw.line((point(60, 166), point(106, 181 + strum)), fill=cyan, width=p(8))
        rx, ry = point(106, 181 + strum)
        draw.ellipse((rx - p(6), ry - p(6), rx + p(6), ry + p(6)), fill=cyan)
        alpha = int(90 + 120 * abs(math.sin(phase * math.tau * 4)))
        for offset in (-8, 8):
            draw.line((point(116 + offset, 175 + strum * 0.3), point(122 + offset, 186 + strum * 0.3)), fill=(166, 234, 255, alpha), width=p(1.5))

    def painting(self, phase: float) -> None:
        """Animated easel scene with a brush following a three-stroke loop."""
        draw = ImageDraw.Draw(self.emissive)
        accent = ImageDraw.Draw(self.accents)
        beat = math.sin(phase * math.tau)
        stroke_phase = (phase * 3.0) % 1.0
        wood = (218, 139, 63, 245)
        wood_light = (255, 205, 112, 255)
        cyan = (101, 222, 255, 248)
        canvas = (223, 244, 242, 255)
        canvas_shadow = (39, 87, 119, 255)

        # The easel remains still while the hand and brush move in soft arcs.
        draw.line((p(158), p(190), p(143), p(224)), fill=wood, width=p(6))
        draw.line((p(190), p(190), p(206), p(224)), fill=wood, width=p(6))
        draw.line((p(174), p(103), p(174), p(221)), fill=wood_light, width=p(5))
        draw.rounded_rectangle(
            (p(126), p(111), p(215), p(196)),
            radius=p(5),
            fill=wood,
            outline=wood_light,
            width=p(2),
        )
        draw.rounded_rectangle(
            (p(133), p(118), p(208), p(189)),
            radius=p(3),
            fill=canvas,
        )

        # Finished marks stay on the canvas; the active one grows under the brush.
        strokes = (
            ((145, 143), (194, 136), (34, 154, 250, 255)),
            ((142, 158), (198, 169), (255, 116, 112, 255)),
            ((151, 178), (191, 151), (255, 191, 72, 255)),
        )
        active = int(phase * 3) % len(strokes)
        for index, (start, end, color) in enumerate(strokes):
            amount = 1.0 if index < active else stroke_phase if index == active else 0.0
            if phase >= (index + 1) / 3:
                amount = 1.0
            if amount <= 0:
                continue
            end_x = start[0] + (end[0] - start[0]) * amount
            end_y = start[1] + (end[1] - start[1]) * amount
            draw.line((p(start[0]), p(start[1]), p(end_x), p(end_y)), fill=color, width=p(6))

        start, end, color = strokes[active]
        tip_x = start[0] + (end[0] - start[0]) * stroke_phase
        tip_y = start[1] + (end[1] - start[1]) * stroke_phase + beat * 1.5
        hand_x, hand_y = 109 + beat * 2, 177 - abs(beat) * 2
        draw.line((p(54), p(185), p(hand_x), p(hand_y)), fill=cyan, width=p(9))
        draw.ellipse((p(hand_x - 6), p(hand_y - 6), p(hand_x + 6), p(hand_y + 6)), fill=cyan)
        draw.line((p(hand_x), p(hand_y), p(tip_x), p(tip_y)), fill=wood_light, width=p(4))
        draw.line((p(tip_x - 4), p(tip_y + 3), p(tip_x), p(tip_y)), fill=color, width=p(5))

        # Palette and paint dots make the activity readable on the small screen.
        draw.ellipse((p(45), p(196), p(104), p(225)), fill=wood, outline=wood_light, width=p(2))
        draw.ellipse((p(85), p(201), p(96), p(212)), fill=canvas_shadow)
        for x, dot_color in ((56, PALETTE["mid"]), (68, PALETTE["warm"]), (80, PALETTE["gold"])):
            draw.ellipse((p(x), p(205), p(x + 7), p(212)), fill=dot_color)
        accent.ellipse((p(tip_x - 2), p(tip_y - 2), p(tip_x + 2), p(tip_y + 2)), fill=(225, 252, 255, 180))

    def compose(self) -> Image.Image:
        base = Image.new("RGBA", (CANVAS, CANVAS), PALETTE["ink"])
        alpha = self.emissive.getchannel("A")
        halo_alpha = alpha.filter(ImageFilter.GaussianBlur(p(7))).point(lambda value: int(value * self.variant.glow * 0.28))
        rim_alpha = alpha.filter(ImageFilter.GaussianBlur(p(2.2))).point(lambda value: int(value * 0.55))
        halo = self.emissive.filter(ImageFilter.GaussianBlur(p(7)))
        halo.putalpha(halo_alpha)
        rim = self.emissive.filter(ImageFilter.GaussianBlur(p(2.2)))
        rim.putalpha(rim_alpha)
        accents = self.accents.filter(ImageFilter.GaussianBlur(p(0.25)))
        base.alpha_composite(halo)
        base.alpha_composite(rim)
        base.alpha_composite(self.emissive)
        base.alpha_composite(accents)
        return base


def face(
    variant: Variant,
    *,
    openness: float = 1.0,
    left_open: float | None = None,
    right_open: float | None = None,
    width_scale: float = 1.0,
    height_scale: float = 1.0,
    left_scale: float = 1.0,
    right_scale: float = 1.0,
    gaze_x: float = 0.0,
    gaze_y: float = 0.0,
    eye_y: float = 108.0,
    eye_shift: float = 0.0,
    rotation: float = 0.0,
    left_rotation: float | None = None,
    right_rotation: float | None = None,
    smile_eyes: float = 0.0,
    lid: float = 0.0,
    mouth_width: float = 36,
    mouth_curve: float = 4,
    mouth_open: float = 0.0,
    mouth_x: float = 120,
    mouth_y: float | None = None,
    mouth_tilt: float = 0.0,
    warmth: float = 0.0,
    brows: tuple[float, float] | None = None,
) -> FaceFrame:
    frame = FaceFrame(variant)
    offset = variant.eye_gap / 2 + variant.eye_width / 2
    left_center = (120 - offset + eye_shift, eye_y)
    right_center = (120 + offset + eye_shift, eye_y)
    frame.eye(
        left_center,
        side=-1,
        openness=openness if left_open is None else left_open,
        width_scale=width_scale * left_scale,
        height_scale=height_scale * left_scale,
        rotation=rotation if left_rotation is None else left_rotation,
        gaze_x=gaze_x,
        gaze_y=gaze_y,
        smile=smile_eyes,
        lid=lid,
        warmth=warmth,
    )
    frame.eye(
        right_center,
        side=1,
        openness=openness if right_open is None else right_open,
        width_scale=width_scale * right_scale,
        height_scale=height_scale * right_scale,
        rotation=-rotation if right_rotation is None else right_rotation,
        gaze_x=gaze_x,
        gaze_y=gaze_y,
        smile=smile_eyes,
        lid=lid,
        warmth=warmth,
    )
    if brows and variant.shape != "leaf":
        frame.brow(left_center, brows[0])
        frame.brow(right_center, brows[1])
    frame.mouth(
        width=mouth_width,
        curve=mouth_curve,
        openness=mouth_open,
        x=mouth_x,
        y=mouth_y,
        tilt=mouth_tilt,
        warmth=warmth,
    )
    return frame


def loop_frames(variant: Variant, emotion: str) -> list[tuple[FaceFrame, int]]:
    frames: list[tuple[FaceFrame, int]] = []
    count = 16
    for index in range(count):
        t = index / count
        wave = math.sin(t * math.tau)
        wave2 = math.sin(t * math.tau * 2)
        micro = 0.8 * math.sin(t * math.tau + 0.6)
        kwargs: dict[str, object] = {"eye_y": 108 + micro, "gaze_x": 0.06 * wave}

        if emotion in ("neutral", "robot_2"):
            if variant.shape == "leaf":
                kwargs.update(mouth_width=17, mouth_curve=0, gaze_y=0.15)
            else:
                kwargs.update(mouth_width=34, mouth_curve=3.5)
            if index in (9, 10):
                kwargs.update(openness=0.14 if index == 9 else 0.48)
            if index >= 12:
                kwargs.update(gaze_x=-0.35 + 0.1 * (index - 12), mouth_x=118)
        elif emotion == "happy":
            kwargs.update(smile_eyes=0.82, openness=0.88, eye_y=106 - 1.4 * wave, mouth_width=49, mouth_curve=9, warmth=0.12)
        elif emotion == "laughing":
            kwargs.update(smile_eyes=0.95, openness=0.82, eye_y=108 + 2.2 * wave2, mouth_width=44, mouth_open=0.72 + 0.18 * abs(wave2), warmth=0.18)
        elif emotion == "sad":
            kwargs.update(openness=0.72, lid=0.18, left_rotation=-8, right_rotation=8, eye_y=112 + micro, gaze_y=0.45, mouth_width=38, mouth_curve=-7, brows=(-10, 10))
        elif emotion == "crying":
            kwargs.update(openness=0.64, lid=0.22, left_rotation=-9, right_rotation=9, gaze_y=0.5, mouth_width=34, mouth_curve=-8, brows=(-11, 11))
        elif emotion == "angry":
            kwargs.update(openness=0.58, lid=0.3, left_rotation=10, right_rotation=-10, eye_shift=1.2 * wave2, mouth_width=39, mouth_curve=-4, warmth=0.34, brows=(13, -13))
        elif emotion in ("sleepy", "dozing"):
            opening = 0.32 + 0.10 * wave
            if emotion == "dozing":
                opening = max(0.08, 0.72 - index / count * 0.68)
            kwargs.update(openness=opening, lid=0.38, eye_y=114, gaze_y=0.4, mouth_width=24, mouth_curve=1)
        elif emotion in ("surprised", "shocked"):
            scale = 1.08 + (0.07 if emotion == "shocked" else 0.035) * wave2
            kwargs.update(width_scale=scale, height_scale=1.14, mouth_width=18, mouth_open=0.78, eye_shift=(1.2 * wave2 if emotion == "shocked" else 0))
        elif emotion == "thinking":
            kwargs.update(gaze_x=0.48, gaze_y=-0.55, left_scale=1.03, right_scale=0.9, mouth_width=25, mouth_curve=1, mouth_x=126, mouth_tilt=-2)
        elif emotion == "confused":
            kwargs.update(left_scale=1.07 + 0.03 * wave, right_scale=0.82 - 0.02 * wave, left_rotation=4 * wave, right_rotation=-6 * wave, gaze_x=0.2 * wave, mouth_width=31, mouth_curve=-1, mouth_tilt=3 * wave)
        elif emotion == "winking":
            right = 0.08 if 5 <= index <= 8 else 1.0
            kwargs.update(right_open=right, smile_eyes=0.15 if right < 0.2 else 0, mouth_width=44, mouth_curve=7, mouth_tilt=2)
        elif emotion == "loving":
            kwargs.update(smile_eyes=0.7, openness=0.9, mouth_width=44, mouth_curve=8, warmth=0.35)
        elif emotion == "cool":
            kwargs.update(openness=0.58, lid=0.38, gaze_x=0.28, mouth_width=40, mouth_curve=4, mouth_tilt=2)
        elif emotion == "confident":
            kwargs.update(openness=0.72, lid=0.32, left_rotation=3, right_rotation=-3, gaze_x=0.12, mouth_width=43, mouth_curve=5, mouth_tilt=2)
        elif emotion == "embarrassed":
            kwargs.update(openness=0.68, gaze_x=-0.5 + 0.12 * wave, gaze_y=0.3, mouth_width=27, mouth_curve=0, warmth=0.38)
        elif emotion in ("funny", "silly", "delicious"):
            kwargs.update(left_scale=1.08 + 0.05 * wave, right_scale=0.9 - 0.04 * wave, gaze_x=0.35 * wave2, mouth_width=38, mouth_open=0.62 + 0.12 * wave2, mouth_tilt=3 * wave)
        elif emotion == "kissy":
            kwargs.update(smile_eyes=0.86, openness=0.8, mouth_width=15, mouth_open=0.5, warmth=0.3)
        elif emotion == "relaxed":
            kwargs.update(smile_eyes=0.62, openness=0.7, gaze_y=0.2, mouth_width=42, mouth_curve=7)
        elif emotion == "curious":
            kwargs.update(left_scale=1.09 + 0.03 * wave, right_scale=0.9 - 0.02 * wave, gaze_x=0.45 * wave, gaze_y=-0.1, mouth_width=32, mouth_curve=4, mouth_tilt=2 * wave)
        elif emotion == "listening":
            pulse = 1.0 + 0.035 * wave
            kwargs.update(width_scale=pulse, gaze_x=0, mouth_width=29, mouth_curve=3)
        elif emotion == "speaking":
            energy = 0.48 + 0.42 * abs(wave2)
            kwargs.update(openness=0.93 + 0.05 * wave2, eye_y=108 - 1.2 * wave, mouth_width=31 + 14 * energy, mouth_open=energy)
        elif emotion == "connecting":
            kwargs.update(openness=0.82, gaze_x=0.55 * wave, mouth_width=27, mouth_curve=0)
        elif emotion == "music":
            kwargs.update(smile_eyes=0.7, openness=0.82, eye_shift=2.0 * wave, eye_y=106 - 2 * abs(wave2), mouth_width=36, mouth_curve=7, mouth_tilt=2 * wave)
        elif emotion == "painting":
            kwargs.update(
                openness=0.92,
                eye_y=76 - 1.5 * abs(wave),
                gaze_x=0.48,
                gaze_y=0.58,
                left_scale=0.96,
                right_scale=1.02,
                mouth_width=18,
                mouth_curve=2,
                mouth_x=91,
                mouth_y=118,
            )
        else:
            kwargs.update(mouth_width=34, mouth_curve=4)

        frame = face(variant, **kwargs)
        if emotion == "crying":
            progress = (t * 1.7) % 1.0
            frame.tear((87, 139 + progress * 49), alpha=int(235 * (1 - progress * 0.6)))
        if emotion in ("sleepy", "dozing"):
            frame.dots(2 if index < 8 else 3, t)
        if emotion == "thinking":
            frame.dots(1 + (index // 4) % 3, t)
        if emotion == "loving":
            beat = 6 + 2 * max(0, wave2)
            frame.heart((204, 64 - 5 * t), beat)
        if emotion == "embarrassed":
            frame.heart((203, 70), 4.5, alpha=120)
        if emotion == "kissy":
            progress = t
            frame.heart((120 + 10 * wave, 154 - 42 * progress), 5 + 3 * (1 - progress), alpha=int(240 * (1 - 0.55 * progress)))
        if emotion == "listening":
            frame.side_waves(t)
        if emotion == "connecting":
            frame.ring(82 + 4 * wave, alpha=75 + int(30 * abs(wave)))
            frame.dots(1 + (index // 4) % 3, t)
        if emotion == "curious" and index in (3, 11):
            frame.spark((204 if index == 3 else 37, 55), 7)
        if emotion == "music":
            frame.guitar(t, sway=2.6 * wave)
            frame.music_note((38, 49), 10 + 1.5 * abs(wave2), t)
            frame.music_note((200, 45), 12 + 1.5 * abs(wave), t + 0.4, mirrored=True)
        if emotion == "painting":
            frame.painting(t)
        frames.append((frame, 82 if emotion in ("speaking", "laughing", "music", "painting") else 105))
    return frames


def lifecycle_frames(variant: Variant, emotion: str) -> list[tuple[FaceFrame, int]]:
    frames: list[tuple[FaceFrame, int]] = []
    count = 18
    for index in range(count):
        t = index / (count - 1)
        e = ease(t)
        if emotion == "boot":
            opening = clamp((e - 0.22) / 0.72)
            frame = face(
                variant,
                openness=max(0.055, opening),
                width_scale=0.72 + 0.28 * spring(t),
                eye_shift=0,
                mouth_width=12 + 29 * opening,
                mouth_curve=1 + 5 * opening,
                mouth_y=174 + 5 * (1 - opening),
            )
            frame.ring(10 + 79 * e, alpha=int(190 * (1 - e)))
            if index < 8:
                frame.spark((120, 110), 4 + 13 * e, int(245 * (1 - 0.55 * e)))
        elif emotion == "wake":
            opening = clamp(0.05 + spring(t) * 0.95)
            frame = face(
                variant,
                openness=opening,
                height_scale=1 + 0.08 * math.sin(t * math.pi),
                eye_y=116 - 8 * e,
                mouth_width=18 + 24 * e,
                mouth_curve=1 + 5 * e,
            )
            if index in (11, 14):
                frame.spark((38 if index == 11 else 202, 58), 7, 180)
        elif emotion == "goodnight":
            opening = max(0.04, 1 - e)
            frame = face(
                variant,
                openness=opening,
                lid=0.45 * e,
                eye_y=108 + 8 * e,
                width_scale=1 - 0.12 * e,
                mouth_width=max(8, 42 - 32 * e),
                mouth_curve=5 * (1 - e),
            )
            if 5 <= index <= 13:
                frame.spark((202 - 5 * (index - 5), 52 + 3 * (index - 5)), max(2, 7 - 0.5 * (index - 5)), int(170 * (1 - e)))
        else:
            return loop_frames(variant, emotion)
        frames.append((frame, 78 if emotion != "goodnight" else 92))
    if emotion == "goodnight":
        frames.append((FaceFrame(variant), 800))
    return frames


EMOTIONS = (
    "boot",
    "wake",
    "dozing",
    "goodnight",
    "listening",
    "speaking",
    "music",
    "painting",
    "connecting",
    "curious",
    "neutral",
    "robot_2",
    "happy",
    "laughing",
    "sad",
    "crying",
    "angry",
    "sleepy",
    "surprised",
    "shocked",
    "thinking",
    "confused",
    "winking",
    "loving",
    "cool",
    "confident",
    "embarrassed",
    "funny",
    "silly",
    "kissy",
    "relaxed",
    "delicious",
)


def build_emotion(variant: Variant, emotion: str) -> list[tuple[FaceFrame, int]]:
    if emotion in ("boot", "wake", "goodnight"):
        return lifecycle_frames(variant, emotion)
    return loop_frames(variant, emotion)


def quantize_frames(frames: list[Image.Image], colors: int) -> list[Image.Image]:
    indexes = sorted({int(i * (len(frames) - 1) / 7) for i in range(8)})
    strip = Image.new("RGB", (LOGICAL_SIZE, LOGICAL_SIZE * len(indexes)))
    for row, index in enumerate(indexes):
        strip.paste(frames[index], (0, row * LOGICAL_SIZE))
    reference = strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    reference.putpalette(rgb565_palette(reference.getpalette()))
    return [frame.quantize(palette=reference, dither=Image.Dither.FLOYDSTEINBERG) for frame in frames]


def save_gif(path: Path, sequence: list[tuple[FaceFrame, int]], colors: int) -> None:
    frames = [
        frame.compose().resize((LOGICAL_SIZE, LOGICAL_SIZE), Image.Resampling.LANCZOS).convert("RGB")
        for frame, _ in sequence
    ]
    durations = [duration for _, duration in sequence]
    quantized = quantize_frames(frames, colors)
    quantized[0].save(
        path,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )


def save_review_sheet(path: Path, variant: Variant, sequences: dict[str, list[tuple[FaceFrame, int]]]) -> None:
    keys = [name for name in EMOTIONS if name != "robot_2"]
    columns, tile = 5, 168
    rows = math.ceil(len(keys) / columns)
    sheet = Image.new("RGB", (columns * tile, rows * (tile + 28)), (7, 12, 18))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, name in enumerate(keys):
        sequence = sequences[name]
        frame = sequence[len(sequence) // 2][0].compose().resize((tile, tile), Image.Resampling.LANCZOS).convert("RGB")
        x = (index % columns) * tile
        y = (index // columns) * (tile + 28)
        sheet.paste(frame, (x, y))
        draw.text((x + 8, y + tile + 7), name.upper(), fill=(177, 216, 228), font=font)
    sheet.save(path, quality=95)


def save_motion_reel(path: Path, variant: Variant, sequences: dict[str, list[tuple[FaceFrame, int]]]) -> None:
    reel_names = ("neutral", "listening", "speaking", "music", "painting", "happy", "thinking", "goodnight")
    frames: list[Image.Image] = []
    durations: list[int] = []
    for name in reel_names:
        sequence = sequences[name]
        step = max(1, len(sequence) // 6)
        for frame, duration in sequence[::step][:6]:
            frames.append(frame.compose().resize((LOGICAL_SIZE, LOGICAL_SIZE), Image.Resampling.LANCZOS).convert("RGB"))
            durations.append(max(90, duration))
    quantized = quantize_frames(frames, 255)
    quantized[0].save(path, save_all=True, append_images=quantized[1:], duration=durations, loop=0, optimize=True, disposal=1)


def generate_variant(variant: Variant, root: Path, only: str | None, colors: int) -> None:
    target = root / f"giddy-v2-{variant.name}-240"
    target.mkdir(parents=True, exist_ok=True)
    names = [only] if only else list(EMOTIONS)
    sequences = {name: build_emotion(variant, name) for name in names}
    for name, sequence in sequences.items():
        save_gif(target / f"{name}.gif", sequence, colors)
        print(f"{variant.name:>5}  {name:<12} {len(sequence):>2} frames")
    if not only:
        save_review_sheet(target / "review-sheet.jpg", variant, sequences)
        save_motion_reel(target / "motion-reel.gif", variant, sequences)
        manifest = {
            "schema": 1,
            "avatarVersion": "3.0" if variant.shape == "leaf" else "2.0",
            "variant": variant.name,
            "identity": "soft rounded organic eyes" if variant.shape == "leaf" else "rounded Giddy V2 eyes",
            "display": {"width": 240, "height": 240, "color": "RGB565"},
            "emotionContract": list(EMOTIONS),
            "principles": ["readable", "interruptible", "restrained", "friendly", "extensible"],
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Giddy V2 avatar family")
    parser.add_argument("--variant", choices=(*VARIANTS.keys(), "all"), default="core")
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--only", choices=EMOTIONS, default=None)
    parser.add_argument("--colors", type=int, default=255)
    args = parser.parse_args()

    root = Path(args.out_root) if args.out_root else Path(__file__).resolve().parent / "output"
    root.mkdir(parents=True, exist_ok=True)
    selected = VARIANTS.values() if args.variant == "all" else (VARIANTS[args.variant],)
    for variant in selected:
        generate_variant(variant, root, args.only, args.colors)


if __name__ == "__main__":
    main()

"""Generate the Giddy Signal V3 character for the 240x240 RGB565 display."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


SIZE = 240
K = 4
CANVAS = SIZE * K
CYAN = (35, 235, 255, 255)
BLUE = (20, 119, 255, 255)
DEEP = (8, 44, 128, 255)
WHITE = (224, 255, 255, 255)
CORAL = (255, 126, 116, 255)


EMOTIONS = (
    "boot", "wake", "dozing", "goodnight", "listening", "speaking",
    "music", "connecting", "curious", "neutral", "robot_2", "happy",
    "laughing", "sad", "crying", "angry", "sleepy", "surprised",
    "shocked", "thinking", "confused", "winking", "loving", "cool",
    "confident", "embarrassed", "funny", "silly", "kissy", "relaxed",
    "delicious",
)


def px(value: float) -> int:
    return int(round(value * K))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smooth(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def refined_settle(value: float) -> float:
    """Controlled overshoot under 4 percent, then a long clean settle."""
    value = clamp(value)
    return 1 - math.exp(-6.8 * value) * math.cos(7.4 * value) * 0.96


def quadratic_points(
    start: tuple[float, float], control: tuple[float, float], end: tuple[float, float], steps: int = 40
) -> list[tuple[int, int]]:
    result = []
    for index in range(steps + 1):
        t = index / steps
        inv = 1 - t
        result.append((
            px(inv * inv * start[0] + 2 * inv * t * control[0] + t * t * end[0]),
            px(inv * inv * start[1] + 2 * inv * t * control[1] + t * t * end[1]),
        ))
    return result


def path_length(points: list[tuple[int, int]]) -> float:
    return sum(math.dist(points[index - 1], points[index]) for index in range(1, len(points)))


def partial_path(points: list[tuple[int, int]], progress: float) -> list[tuple[int, int]]:
    progress = clamp(progress)
    if progress >= 1:
        return points
    target = path_length(points) * progress
    result = [points[0]]
    travelled = 0.0
    for index in range(1, len(points)):
        segment = math.dist(points[index - 1], points[index])
        if travelled + segment >= target:
            ratio = 0 if segment == 0 else (target - travelled) / segment
            x = int(points[index - 1][0] + (points[index][0] - points[index - 1][0]) * ratio)
            y = int(points[index - 1][1] + (points[index][1] - points[index - 1][1]) * ratio)
            result.append((x, y))
            break
        result.append(points[index])
        travelled += segment
    return result


def rgb565_palette(palette: list[int]) -> list[int]:
    result = []
    for index in range(0, len(palette), 3):
        red, green, blue = palette[index:index + 3]
        r5, g6, b5 = red >> 3, green >> 2, blue >> 3
        result.extend(((r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)))
    return result


class SignalFrame:
    def __init__(self) -> None:
        self.light = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    def _paste(self, piece: Image.Image, center: tuple[float, float]) -> None:
        self.light.alpha_composite(piece, (px(center[0]) - piece.width // 2, px(center[1]) - piece.height // 2))

    def _gradient_piece(self, mask: Image.Image) -> Image.Image:
        width, height = mask.size
        fill = Image.new("RGBA", mask.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(fill)
        for y in range(height):
            t = y / max(1, height - 1)
            if t < 0.55:
                local = t / 0.55
                top, bottom = CYAN, BLUE
            else:
                local = (t - 0.55) / 0.45
                top, bottom = BLUE, DEEP
            color = tuple(int(top[i] + (bottom[i] - top[i]) * local) for i in range(4))
            draw.line((0, y, width, y), fill=color)
        fill.putalpha(mask)
        return fill

    def module(
        self,
        center: tuple[float, float],
        side: str,
        *,
        width: float = 60,
        height: float = 44,
        stroke: float = 8.5,
        rotation: float = 0,
        shape: str = "module",
        progress: float = 1.0,
        intensity: float = 1.0,
    ) -> None:
        pad = px(stroke * 0.72)
        w, h = px(width), max(px(5), px(height))
        mask = Image.new("L", (w + pad * 2, h + pad * 2), 0)
        draw = ImageDraw.Draw(mask)
        line_width = max(px(2), px(stroke))
        left, top, right, bottom = pad, pad, pad + w, pad + h
        chamfer = min(px(10), h // 3, w // 5)

        if shape == "bar":
            points = [(left + chamfer, (top + bottom) // 2), (right - chamfer, (top + bottom) // 2)]
        elif shape in ("arch", "lower_arc"):
            curve = -height * 0.32 if shape == "arch" else height * 0.32
            points = quadratic_points(
                ((left + chamfer) / K, (top + bottom) / (2 * K)),
                ((left + right) / (2 * K), (top + bottom) / (2 * K) + curve),
                ((right - chamfer) / K, (top + bottom) / (2 * K)),
            )
        else:
            if side == "left":
                points = [
                    (right - chamfer, top), (left + chamfer, top), (left, top + chamfer),
                    (left, bottom - chamfer), (left + chamfer, bottom), (right - chamfer, bottom),
                ]
            else:
                points = [
                    (left + chamfer, top), (right - chamfer, top), (right, top + chamfer),
                    (right, bottom - chamfer), (right - chamfer, bottom), (left + chamfer, bottom),
                ]

        visible = partial_path(points, progress)
        if len(visible) >= 2:
            draw.line(visible, fill=int(255 * clamp(intensity)), width=line_width, joint="curve")
            radius = line_width // 2
            for point in (visible[0], visible[-1]):
                draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), fill=int(255 * clamp(intensity)))

        piece = self._gradient_piece(mask)
        highlight = Image.new("RGBA", piece.size, (0, 0, 0, 0))
        if len(visible) >= 2 and intensity > 0.65:
            ImageDraw.Draw(highlight).line(visible[:max(2, len(visible) // 2)], fill=(228, 255, 255, 54), width=max(1, px(1.1)))
            highlight.putalpha(Image.composite(highlight.getchannel("A"), Image.new("L", mask.size, 0), mask))
            piece.alpha_composite(highlight)
        if rotation:
            piece = piece.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
        self._paste(piece, center)

    def mouth(
        self,
        *,
        shape: str = "line",
        width: float = 26,
        curve: float = 0,
        openness: float = 0,
        center: tuple[float, float] = (120, 168),
        color: tuple[int, int, int, int] = BLUE,
        rotation: float = 0,
    ) -> None:
        layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        cx, cy = center
        if shape == "open" or openness > 0.15:
            w, h = px(width), px(6 + 10 * openness)
            box = (px(cx) - w // 2, px(cy) - h // 2, px(cx) + w // 2, px(cy) + h // 2)
            draw.rounded_rectangle(box, radius=max(px(2), h // 3), outline=color, width=px(3.1))
        else:
            points = quadratic_points((cx - width / 2, cy), (cx, cy + curve), (cx + width / 2, cy))
            draw.line(points, fill=color, width=px(3.5), joint="curve")
            radius = px(1.75)
            for point in (points[0], points[-1]):
                draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), fill=color)
        if rotation:
            layer = layer.rotate(rotation, center=(px(cx), px(cy)), resample=Image.Resampling.BICUBIC)
        self.light.alpha_composite(layer)

    def compose(self) -> Image.Image:
        background = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 255))
        alpha = self.light.getchannel("A")
        near_alpha = alpha.filter(ImageFilter.GaussianBlur(px(2.2))).point(lambda value: int(value * 0.42))
        far_alpha = alpha.filter(ImageFilter.GaussianBlur(px(6))).point(lambda value: int(value * 0.13))
        near = self.light.filter(ImageFilter.GaussianBlur(px(2.2)))
        far = self.light.filter(ImageFilter.GaussianBlur(px(6)))
        near.putalpha(near_alpha)
        far.putalpha(far_alpha)
        background.alpha_composite(far)
        background.alpha_composite(near)
        background.alpha_composite(self.light)
        return background


def face(
    *,
    left_shape: str = "module",
    right_shape: str | None = None,
    eye_y: float = 108,
    left_y: float = 4,
    right_y: float = -7,
    eye_shift: float = 0,
    spacing: float = 42,
    width: float = 58,
    height: float = 42,
    left_scale: float = 1,
    right_scale: float = 1,
    left_rotation: float = 0,
    right_rotation: float = -7,
    left_progress: float = 1,
    right_progress: float = 1,
    left_intensity: float = 1,
    right_intensity: float = 1,
    mouth_shape: str = "line",
    mouth_width: float = 25,
    mouth_curve: float = 0,
    mouth_open: float = 0,
    mouth_y: float = 168,
    mouth_x: float = 120,
    mouth_color: tuple[int, int, int, int] = BLUE,
    mouth_rotation: float = 0,
) -> SignalFrame:
    frame = SignalFrame()
    right_shape = left_shape if right_shape is None else right_shape
    frame.module(
        (120 - spacing + eye_shift, eye_y + left_y), "left",
        width=width * left_scale, height=height * left_scale,
        rotation=left_rotation, shape=left_shape, progress=left_progress,
        intensity=left_intensity,
    )
    frame.module(
        (120 + spacing + eye_shift, eye_y + right_y), "left",
        width=width * right_scale, height=height * right_scale,
        rotation=right_rotation, shape=right_shape, progress=right_progress,
        intensity=right_intensity,
    )
    frame.mouth(
        shape=mouth_shape, width=mouth_width, curve=mouth_curve,
        openness=mouth_open, center=(mouth_x, mouth_y), color=mouth_color,
        rotation=mouth_rotation,
    )
    return frame


def lifecycle(name: str) -> list[tuple[SignalFrame, int]]:
    frames = []
    for index in range(20):
        t = index / 19
        e = smooth(t)
        if name == "boot":
            reveal = clamp((e - 0.08) / 0.82)
            frame = face(
                height=10 + 32 * refined_settle(t),
                left_progress=reveal,
                right_progress=reveal,
                left_intensity=0.45 + 0.55 * reveal,
                right_intensity=0.45 + 0.55 * reveal,
                mouth_width=8 + 18 * reveal,
                mouth_curve=2 * reveal,
                mouth_y=173 - 5 * reveal,
            )
        elif name == "wake":
            height = 5 + 37 * refined_settle(t)
            frame = face(
                height=height,
                eye_y=114 - 6 * e,
                mouth_width=12 + 14 * e,
                mouth_curve=3 * e,
            )
        else:
            closing = 1 - e
            frame = face(
                left_shape="lower_arc" if closing < 0.25 else "module",
                right_shape="lower_arc" if closing < 0.25 else "module",
                height=max(5, 42 * closing),
                eye_y=108 + 7 * e,
                left_intensity=max(0.15, closing),
                right_intensity=max(0.15, closing),
                mouth_width=max(8, 27 * closing),
                mouth_curve=4 * closing,
                mouth_y=168 + 6 * e,
            )
        frames.append((frame, 72 if name != "goodnight" else 88))
    if name == "goodnight":
        frames.append((SignalFrame(), 900))
    return frames


def loop(name: str) -> list[tuple[SignalFrame, int]]:
    frames = []
    for index in range(18):
        t = index / 18
        wave = math.sin(t * math.tau)
        wave2 = math.sin(t * math.tau * 2)
        micro = 0.7 * math.sin(t * math.tau + 0.4)
        options: dict[str, object] = {"eye_y": 108 + micro, "mouth_width": 25, "mouth_curve": 1.5}

        if name in ("neutral", "robot_2"):
            if index in (10, 11):
                options.update(height=7 if index == 10 else 22)
            elif index >= 14:
                options.update(eye_shift=-2 + (index - 14) * 0.6, mouth_x=119)
        elif name == "listening":
            options.update(width=60 + 2.5 * wave, height=44 + 1.5 * wave, spacing=43, mouth_width=22, mouth_curve=2.5)
        elif name == "speaking":
            energy = 0.42 + 0.5 * abs(wave2)
            options.update(height=41 + 2 * wave, mouth_shape="open", mouth_width=20 + 11 * energy, mouth_open=energy)
        elif name == "music":
            options.update(left_shape="arch", right_shape="arch", eye_y=106 - 2 * abs(wave2), eye_shift=2 * wave, left_rotation=-2 * wave, right_rotation=-2 * wave, mouth_width=31, mouth_curve=6)
        elif name == "connecting":
            phase = (t * 2) % 1
            options.update(left_progress=phase, right_progress=clamp(phase - 0.18) / 0.82, mouth_width=18, mouth_curve=0)
        elif name == "curious":
            options.update(left_scale=1.03 + 0.05 * wave, right_scale=0.9 - 0.03 * wave, left_y=-5, right_y=3, left_rotation=-3, right_rotation=2, mouth_width=20, mouth_x=122, mouth_rotation=-3)
        elif name == "happy":
            options.update(left_shape="arch", right_shape="arch", eye_y=111 - 1.5 * wave, mouth_width=39, mouth_curve=8)
        elif name == "laughing":
            options.update(left_shape="arch", right_shape="arch", eye_y=110 + 2.2 * wave2, mouth_shape="open", mouth_width=34, mouth_open=0.65 + 0.18 * abs(wave2))
        elif name == "sad":
            options.update(height=34, left_rotation=-7, right_rotation=7, left_y=4, right_y=4, mouth_width=30, mouth_curve=-6)
        elif name == "crying":
            dim = 0.64 + 0.12 * wave
            options.update(height=30, left_rotation=-8, right_rotation=8, left_y=6, right_y=6, left_intensity=dim, right_intensity=dim, mouth_width=26, mouth_curve=-7)
        elif name == "angry":
            options.update(height=30, left_rotation=9, right_rotation=-9, spacing=40, eye_shift=1.2 * wave2, mouth_width=30, mouth_curve=-3)
        elif name in ("sleepy", "dozing"):
            if name == "dozing":
                shape = "bar" if index > 8 else "module"
                height = max(6, 35 - index * 2.6)
            else:
                shape = "bar" if index % 6 < 4 else "lower_arc"
                height = 8
            options.update(left_shape=shape, right_shape=shape, height=height, eye_y=114, mouth_width=18, mouth_curve=1)
        elif name in ("surprised", "shocked"):
            pulse = 1 + (0.07 if name == "shocked" else 0.035) * wave2
            options.update(width=48 * pulse, height=54 * pulse, spacing=39, mouth_shape="open", mouth_width=14 + (4 if name == "shocked" else 0), mouth_open=0.75)
        elif name == "thinking":
            options.update(left_y=3, right_y=-8, left_scale=0.94, right_scale=1.04, left_rotation=-2, right_rotation=3, mouth_width=17, mouth_x=118, mouth_rotation=2)
        elif name == "confused":
            options.update(left_y=4 * wave, right_y=-4 * wave, left_rotation=5 * wave, right_rotation=-5 * wave, left_scale=1.02, right_scale=0.88, mouth_width=22, mouth_curve=-1, mouth_rotation=3 * wave)
        elif name == "winking":
            right_shape = "bar" if 5 <= index <= 10 else "module"
            options.update(right_shape=right_shape, height=42, mouth_width=33, mouth_curve=6, mouth_rotation=1.5)
        elif name == "loving":
            options.update(
                left_shape="arch", right_shape="arch", eye_y=109 + 0.7 * wave,
                mouth_width=34 + 1.5 * wave, mouth_curve=7, mouth_color=CORAL,
            )
        elif name == "cool":
            options.update(left_shape="bar", right_shape="bar", height=8, left_rotation=2, right_rotation=-2, mouth_width=29, mouth_curve=4)
        elif name == "confident":
            options.update(height=34, left_rotation=4, right_rotation=-4, spacing=41, mouth_width=31, mouth_curve=4)
        elif name == "embarrassed":
            options.update(eye_shift=-3 * wave, left_scale=0.92, right_scale=0.92, left_y=3, right_y=3, mouth_width=15, mouth_x=118, mouth_rotation=-2)
        elif name == "funny":
            options.update(left_scale=1.08 + 0.06 * wave, right_scale=0.82 - 0.05 * wave, left_y=-3, right_y=5, mouth_shape="open", mouth_width=25, mouth_open=0.55)
        elif name == "silly":
            options.update(left_rotation=7 * wave, right_rotation=-7 * wave, left_y=4 * wave2, right_y=-4 * wave2, mouth_shape="open", mouth_width=22, mouth_open=0.48, mouth_rotation=5 * wave)
        elif name == "kissy":
            options.update(left_shape="arch", right_shape="arch", mouth_shape="open", mouth_width=10 + 2 * wave, mouth_open=0.35, mouth_color=CORAL)
        elif name == "relaxed":
            options.update(left_shape="lower_arc", right_shape="lower_arc", height=15, eye_y=109 + micro, mouth_width=34, mouth_curve=6)
        elif name == "delicious":
            options.update(left_shape="arch", right_shape="arch", mouth_shape="open", mouth_width=27 + 3 * wave, mouth_open=0.48 + 0.1 * abs(wave2), mouth_color=CORAL)

        frames.append((face(**options), 80 if name in ("speaking", "music", "laughing") else 105))
    return frames


def build(name: str) -> list[tuple[SignalFrame, int]]:
    if name in ("boot", "wake", "goodnight"):
        return lifecycle(name)
    return loop(name)


def quantize(frames: list[Image.Image], colors: int) -> list[Image.Image]:
    indexes = sorted({int(i * (len(frames) - 1) / 7) for i in range(8)})
    strip = Image.new("RGB", (SIZE, SIZE * len(indexes)))
    for row, index in enumerate(indexes):
        strip.paste(frames[index], (0, row * SIZE))
    palette = strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    palette.putpalette(rgb565_palette(palette.getpalette()))
    return [frame.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG) for frame in frames]


def save_gif(path: Path, sequence: list[tuple[SignalFrame, int]], colors: int) -> None:
    images = [frame.compose().resize((SIZE, SIZE), Image.Resampling.LANCZOS).convert("RGB") for frame, _ in sequence]
    durations = [duration for _, duration in sequence]
    frames = quantize(images, colors)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True, disposal=1)


def review_sheet(path: Path, sequences: dict[str, list[tuple[SignalFrame, int]]]) -> None:
    names = [name for name in EMOTIONS if name != "robot_2"]
    columns, tile, label = 5, 176, 28
    rows = math.ceil(len(names) / columns)
    sheet = Image.new("RGB", (columns * tile, rows * (tile + label)), (5, 10, 15))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, name in enumerate(names):
        sequence = sequences[name]
        image = sequence[len(sequence) // 2][0].compose().resize((tile, tile), Image.Resampling.LANCZOS).convert("RGB")
        x, y = (index % columns) * tile, (index // columns) * (tile + label)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + tile + 7), name.upper(), fill=(151, 199, 216), font=font)
    sheet.save(path, quality=95)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    parser.add_argument("--only", choices=EMOTIONS, default=None)
    parser.add_argument("--colors", type=int, default=255)
    args = parser.parse_args()

    target = Path(args.out) if args.out else Path(__file__).resolve().parent / "output" / "giddy-v3-signal-240"
    target.mkdir(parents=True, exist_ok=True)
    names = (args.only,) if args.only else EMOTIONS
    sequences = {name: build(name) for name in names}
    for name, sequence in sequences.items():
        save_gif(target / f"{name}.gif", sequence, args.colors)
        print(f"{name:<12} {len(sequence):>2} frames")
    if not args.only:
        review_sheet(target / "review-sheet.jpg", sequences)
        manifest = {
            "schema": 1,
            "avatarVersion": "3.0-signal",
            "display": {"width": 240, "height": 240, "color": "RGB565"},
            "identity": "asymmetric same-direction signal modules",
            "emotionContract": list(EMOTIONS),
            "motion": {
                "elasticity": "0-4%",
                "timing": "controlled pose-to-pose",
                "secondaryAction": "minimal and state-derived",
            },
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="ascii")


if __name__ == "__main__":
    main()

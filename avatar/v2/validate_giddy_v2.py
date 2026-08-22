"""Validate a generated Giddy avatar collection before firmware packaging."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from generate_giddy_v2 import EMOTIONS, LOGICAL_SIZE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("collection", type=Path)
    parser.add_argument("--max-kb", type=int, default=240)
    args = parser.parse_args()

    collection = args.collection.resolve()
    expected = {f"{emotion}.gif" for emotion in EMOTIONS}
    actual = {path.name for path in collection.glob("*.gif")}
    deliverables = actual - {"motion-reel.gif"}
    errors: list[str] = []

    missing = sorted(expected - deliverables)
    extra = sorted(deliverables - expected)
    if missing:
        errors.append(f"missing files: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected files: {', '.join(extra)}")

    total_bytes = 0
    frame_total = 0
    for name in sorted(expected & deliverables):
        path = collection / name
        total_bytes += path.stat().st_size
        if path.stat().st_size > args.max_kb * 1024:
            errors.append(f"{path.name}: exceeds {args.max_kb} KB")
        with Image.open(path) as image:
            if image.format != "GIF":
                errors.append(f"{path.name}: format is {image.format}, expected GIF")
            if image.size != (LOGICAL_SIZE, LOGICAL_SIZE):
                errors.append(f"{path.name}: size is {image.size}, expected 240x240")
            frames = getattr(image, "n_frames", 1)
            frame_total += frames
            if frames < 2:
                errors.append(f"{path.name}: is not animated")
            for frame_index in range(frames):
                image.seek(frame_index)
                duration = int(image.info.get("duration", 0))
                if duration < 20:
                    errors.append(f"{path.name}: frame {frame_index} duration is {duration} ms")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(
        f"OK: {len(deliverables)} emotions, {frame_total} frames, "
        f"{total_bytes / 1024:.1f} KB, 240x240 RGB565-ready GIFs"
    )


if __name__ == "__main__":
    main()

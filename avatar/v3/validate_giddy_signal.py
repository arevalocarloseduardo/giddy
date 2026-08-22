"""Validate a Giddy Signal collection before firmware packaging."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from generate_giddy_signal import EMOTIONS, SIZE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("collection", type=Path)
    parser.add_argument("--max-kb", type=int, default=240)
    args = parser.parse_args()
    collection = args.collection.resolve()
    expected = {f"{name}.gif" for name in EMOTIONS}
    actual = {path.name for path in collection.glob("*.gif")}
    errors = []
    if expected - actual:
        errors.append(f"missing: {', '.join(sorted(expected - actual))}")
    if actual - expected:
        errors.append(f"unexpected: {', '.join(sorted(actual - expected))}")

    total, frames_total = 0, 0
    for path in sorted(collection.glob("*.gif")):
        total += path.stat().st_size
        if path.stat().st_size > args.max_kb * 1024:
            errors.append(f"{path.name}: over {args.max_kb} KB")
        with Image.open(path) as image:
            if image.size != (SIZE, SIZE):
                errors.append(f"{path.name}: {image.size}, expected {SIZE}x{SIZE}")
            frame_count = getattr(image, "n_frames", 1)
            frames_total += frame_count
            if frame_count < 2:
                errors.append(f"{path.name}: not animated")
            for index in range(frame_count):
                image.seek(index)
                if int(image.info.get("duration", 0)) < 20:
                    errors.append(f"{path.name}: invalid duration at frame {index}")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        raise SystemExit(1)
    print(f"OK: {len(actual)} emotions, {frames_total} frames, {total / 1024:.1f} KB")


if __name__ == "__main__":
    main()

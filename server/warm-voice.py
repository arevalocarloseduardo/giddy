#!/usr/bin/env python3
import argparse
import asyncio
import json
import time

from core.product_settings import ProductSettings
from core.providers.tts.edge import TTSProvider


async def warm(settings_path):
    settings = ProductSettings(settings_path)
    current = settings.load()
    voice = current["voice"]
    provider = TTSProvider({
        "voice": voice["voice"],
        "rate": voice["rate"],
        "settings_path": str(settings.path),
        "output_dir": "tmp/",
        "record_voice_metrics": False,
    }, delete_audio_file=True)
    phrases = settings.voice_cache_phrases(current)
    semaphore = asyncio.Semaphore(3)
    failures = []

    async def generate(phrase):
        async with semaphore:
            try:
                await provider.text_to_speak(phrase, None)
            except Exception as exc:
                failures.append({"phrase": phrase, "error": str(exc)[:160]})

    started = time.perf_counter()
    await asyncio.gather(*(generate(phrase) for phrase in phrases))
    return {
        "ok": len(failures) == 0,
        "phrases": len(phrases),
        "failures": failures,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", default="data/giddy-product.json")
    args = parser.parse_args()
    result = asyncio.run(warm(args.settings))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

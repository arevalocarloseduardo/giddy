#!/usr/bin/env python3
"""Simulate one Giddy device turn through the real WebSocket and TTS stack."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import websockets


SERVER_DIR = Path(__file__).resolve().parent
METRICS_PATH = SERVER_DIR / "data" / "giddy-routing.jsonl"


def _metric_count() -> int:
    if not METRICS_PATH.exists():
        return 0
    return len(METRICS_PATH.read_text(encoding="utf-8").splitlines())


def _latest_metric(after: int):
    if not METRICS_PATH.exists():
        return None
    lines = METRICS_PATH.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines[after:]):
        try:
            return json.loads(line)
        except (TypeError, ValueError):
            continue
    return None


async def run_turn(args) -> dict:
    marker = _metric_count()
    device_id = args.device_id or f"giddy-smoke-{uuid.uuid4().hex[:10]}"
    headers = {"device-id": device_id, "client-id": device_id}
    connection_started = time.perf_counter()
    assistant_parts = []
    audio_packets = 0
    tts_states = []
    session_id = None
    first_text_ms = None
    first_audio_ms = None

    async with websockets.connect(
        args.url,
        additional_headers=headers,
        open_timeout=5,
        close_timeout=2,
        max_size=4 * 1024 * 1024,
    ) as socket:
        await socket.send(json.dumps({
            "type": "hello",
            "version": 3,
            "features": {"mcp": True},
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60,
            },
        }))

        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            message = await asyncio.wait_for(
                socket.recv(), timeout=max(0.1, deadline - time.monotonic())
            )
            if isinstance(message, bytes):
                continue
            payload = json.loads(message)
            if payload.get("type") == "hello":
                session_id = payload.get("session_id")
                break
        if not session_id:
            raise RuntimeError("El servidor no completo el saludo WebSocket")

        connection_ms = int((time.perf_counter() - connection_started) * 1000)
        turn_started = time.perf_counter()
        await socket.send(json.dumps({
            "session_id": session_id,
            "type": "listen",
            "state": "detect",
            "text": args.prompt,
        }))

        while time.monotonic() < deadline:
            try:
                message = await asyncio.wait_for(
                    socket.recv(), timeout=max(0.1, deadline - time.monotonic())
                )
            except asyncio.TimeoutError:
                break
            if isinstance(message, bytes):
                audio_packets += 1
                if first_audio_ms is None:
                    first_audio_ms = int((time.perf_counter() - turn_started) * 1000)
                continue

            payload = json.loads(message)
            if payload.get("type") != "tts":
                continue
            state = payload.get("state", "unknown")
            tts_states.append(state)
            if payload.get("text"):
                assistant_parts.append(payload["text"])
                if first_text_ms is None:
                    first_text_ms = int((time.perf_counter() - turn_started) * 1000)
            if state == "stop":
                break

    await asyncio.sleep(0.2)
    result = {
        "ok": bool(assistant_parts and audio_packets),
        "route": _latest_metric(marker),
        "connection_ms": connection_ms,
        "latency_ms": int((time.perf_counter() - turn_started) * 1000),
        "first_text_ms": first_text_ms,
        "first_audio_ms": first_audio_ms,
        "assistant_text": "".join(assistant_parts).strip(),
        "audio_packets": audio_packets,
        "tts_states": tts_states,
    }
    if args.expect_route and (result["route"] or {}).get("route") != args.expect_route:
        result["ok"] = False
        result["error"] = f"Se esperaba ruta {args.expect_route}"
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--url", default="ws://127.0.0.1:8010/xiaozhi/v1/")
    parser.add_argument("--device-id")
    parser.add_argument("--expect-route", choices=("instant", "local", "power"))
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()

    result = asyncio.run(run_turn(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

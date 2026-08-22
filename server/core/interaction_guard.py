import time


EXCLUSIVE_TOOLS = frozenset({"generate_image"})
DEFAULT_AUDIO_COOLDOWN_SECONDS = 3.0
BLOCK_LOG_INTERVAL_SECONDS = 2.0


def is_exclusive_tool(tool_name: str) -> bool:
    return str(tool_name or "") in EXCLUSIVE_TOOLS


def begin_exclusive_operation(conn, operation: str) -> bool:
    operation = str(operation or "").strip()
    if not operation:
        return False

    active = getattr(conn, "giddy_exclusive_operation", None)
    if active and active != operation:
        return False

    conn.giddy_exclusive_operation = operation
    return True


def end_exclusive_operation(
    conn,
    operation: str,
    cooldown_seconds: float = DEFAULT_AUDIO_COOLDOWN_SECONDS,
):
    if getattr(conn, "giddy_exclusive_operation", None) == operation:
        conn.giddy_exclusive_operation = None

    cooldown_until = time.monotonic() + max(0.0, float(cooldown_seconds))
    conn.giddy_ignore_audio_until = max(
        float(getattr(conn, "giddy_ignore_audio_until", 0.0) or 0.0),
        cooldown_until,
    )


def audio_block_reason(conn, now: float | None = None) -> str | None:
    active = getattr(conn, "giddy_exclusive_operation", None)
    if active:
        return f"operacion exclusiva: {active}"

    current = time.monotonic() if now is None else now
    if current < float(getattr(conn, "giddy_ignore_audio_until", 0.0) or 0.0):
        return "enfriamiento de audio"

    if getattr(conn, "client_is_speaking", False) and not getattr(
        conn, "client_aec", False
    ):
        return "reproduccion sin cancelacion de eco"

    return None


def discard_blocked_audio(conn, source: str) -> bool:
    now = time.monotonic()
    reason = audio_block_reason(conn, now)
    if reason is None:
        return False

    reset_audio_states = getattr(conn, "reset_audio_states", None)
    if callable(reset_audio_states):
        reset_audio_states()

    last_log_at = float(getattr(conn, "giddy_last_audio_block_log_at", 0.0) or 0.0)
    if now - last_log_at >= BLOCK_LOG_INTERVAL_SECONDS:
        conn.giddy_last_audio_block_log_at = now
        logger = getattr(conn, "logger", None)
        if logger is not None:
            logger.bind(tag=__name__).info(
                f"Audio descartado en {source} ({reason})"
            )
    return True

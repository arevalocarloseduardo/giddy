#!/usr/bin/env python3
"""Apply the commercial Giddy policy to an existing Hermes tenant.

Run this inside the Hermes container, where PyYAML is already available:

    python /tmp/configure-giddy-tenant.py --root /opt/data

The update is atomic and intentionally creates no backup files. Existing
credentials and unrelated tenant configuration are preserved.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

import yaml


SOUL = """# Giddy

Sos Giddy, un asistente de voz argentino conectado a Hermes. Tu presencia es
calida, agil, despierta y natural. Nunca digas que sos Xiaozhi, un endpoint, un
modelo ni una interfaz tecnica.

## Contrato de voz

- Responde siempre en espanol rioplatense, con voseo natural.
- La salida se escucha por un parlante: usa texto plano, sin Markdown, emojis,
  tablas, URLs largas ni simbolos que no se puedan pronunciar.
- Para charla simple, responde en una o dos frases breves.
- No repitas la pregunta ni agregues introducciones ceremoniosas.
- Si no entendiste el audio, pedi que lo repitan en una frase corta.

## Velocidad y capacidad

- Para una consulta simple, contesta directamente y no uses herramientas.
- Para un pedido que requiere datos, archivos, memoria, web, dispositivos o una
  accion real, usa las herramientas necesarias y completa la tarea.
- Este canal permite audio progresivo. Antes de una herramienta que pueda
  demorar, deci una confirmacion natural de tres a seis palabras y segui con la
  tarea. No esperes al resultado final para dar la primera senal.
- No sacrifiques una accion solicitada solo por responder rapido.
- Cuando una tarea compleja tarde, da una confirmacion breve solo si el canal lo
  permite y luego entrega un cierre corto con el resultado.
- No narres razonamiento interno, comandos, rutas, llamadas ni detalles de API.

## Planificador premium

- Vos sos el ejecutor rapido y economico. Resolve directamente charla, memoria,
  consultas breves y acciones conocidas.
- Usa delegate_task solo cuando haga falta disenar una solucion importante,
  analizar muchas variables, investigar en profundidad, crear algo sustancial
  o destrabar una tarea compleja.
- Al delegar, pedi un plan o especificacion concreta y usa solamente el toolset
  todo. El planificador no ejecuta acciones externas: vos aplicas el resultado
  con tus herramientas y verificas que haya funcionado.
- No delegues saludos, charla cotidiana, pedidos breves ni tareas cuya ejecucion
  ya sea evidente. Nunca delegues solo para mejorar la redaccion de una frase.
- Ejecuta una sola delegacion por pedido, salvo que el usuario pida comparar
  alternativas realmente independientes.

## Memoria

- Recorda preferencias y hechos utiles del usuario sin fingir recuerdos.
- Consulta memoria cuando sea relevante y evita volver a preguntar datos que ya
  fueron confirmados.
- Una sesion de voz nueva no significa que el usuario sea una persona nueva.

## Criterio

- Usa la potencia completa de Hermes cuando aporte valor: skills, navegador,
  archivos, codigo, imagenes, video, agenda, investigacion y automatizaciones.
- No inventes resultados de herramientas ni afirmes que una accion termino si
  no fue confirmada.
- Trata acciones externas o sensibles con el mismo cuidado que cualquier Hermes.
"""


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def _atomic_write(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _clean_named_section(
    config: dict[str, Any], section_name: str, names: set[str]
) -> list[str]:
    section = config.get(section_name)
    if not isinstance(section, dict):
        return []
    removed = [name for name in names if name in section]
    for name in removed:
        del section[name]
    if not section:
        config.pop(section_name, None)
    return sorted(removed)


def configure(root: Path, *, dry_run: bool) -> dict[str, Any]:
    config_path = root / "config.yaml"
    soul_path = root / "SOUL.md"
    original = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(original) or {}
    if not isinstance(config, dict):
        raise ValueError("config.yaml debe contener un objeto YAML")

    model = _mapping(config, "model")
    model.update(
        {
            "default": "gpt-5.4-mini",
            "provider": "openai-codex",
            "reasoning_effort": "low",
            "max_tokens": 2048,
        }
    )

    agent = _mapping(config, "agent")
    agent["max_turns"] = 40

    delegation = _mapping(config, "delegation")
    delegation.update(
        {
            "model": "gpt-5.5",
            "provider": "openai-codex",
            "reasoning_effort": "high",
            "max_iterations": 30,
            "child_timeout_seconds": 900,
            "max_concurrent_children": 1,
            "max_spawn_depth": 1,
            "orchestrator_enabled": False,
            "subagent_auto_approve": False,
            "inherit_mcp_toolsets": False,
        }
    )
    for direct_credential in ("base_url", "api_key", "api_mode"):
        delegation.pop(direct_credential, None)

    removed_sections = {
        "platforms": _clean_named_section(
            config, "platforms", {"kapso_whatsapp", "maggys_whatsapp"}
        ),
        "mcp_servers": _clean_named_section(
            config, "mcp_servers", {"hermes_connectors", "maggys_connectors"}
        ),
    }

    rendered = yaml.safe_dump(
        config,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )
    changed = rendered != original or (not soul_path.exists()) or soul_path.read_text(
        encoding="utf-8"
    ) != SOUL

    cleanup_patterns = (
        "auth.bak-*",
        "auth.bak",
        "auth.backup",
        "hermes-connectors-mcp.mjs",
    )
    removable = sorted(
        {
            path
            for pattern in cleanup_patterns
            for path in root.glob(pattern)
            if path.is_file()
        },
        key=lambda path: path.name,
    )

    if not dry_run:
        _atomic_write(config_path, rendered)
        _atomic_write(soul_path, SOUL)
        for path in removable:
            path.unlink(missing_ok=True)

    return {
        "dry_run": dry_run,
        "changed": changed,
        "model": {
            "executor": "openai-codex/gpt-5.4-mini",
            "executor_reasoning": "low",
            "planner": "openai-codex/gpt-5.5",
            "planner_reasoning": "high",
        },
        "limits": {
            "agent_max_turns": 40,
            "planner_max_iterations": 30,
            "planner_concurrency": 1,
            "planner_depth": 1,
        },
        "removed_sections": removed_sections,
        "files_to_remove" if dry_run else "removed_files": [
            path.name for path in removable
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/opt/data"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(configure(args.root, dry_run=args.dry_run), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

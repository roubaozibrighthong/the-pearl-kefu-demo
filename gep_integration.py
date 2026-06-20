import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
BRIDGE_PATH = BASE_DIR / "scripts" / "gep_bridge.mjs"
RUNTIME_DIR = BASE_DIR / "runtime" / "gep"
ASSET_DIR = RUNTIME_DIR / "assets"
EVENT_LOG_PATH = RUNTIME_DIR / "events.jsonl"
EVOLVER_SESSIONS_DIR = BASE_DIR / "runtime" / "evolver" / "sessions"
EVOLVER_BIN = BASE_DIR / "node_modules" / ".bin" / "evolver"
EVOLVER_BRIDGE_PATH = BASE_DIR / "scripts" / "evolver_bridge.cjs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", value)
    value = re.sub(r"(?<!\d)\d{12,}(?!\d)", "[长编号已脱敏]", value)
    return value[:2000]


def _run_bridge(operation: str, payload: dict) -> dict:
    request = {
        "operation": operation,
        "payload": payload,
        "output_dir": str(ASSET_DIR),
    }
    try:
        result = subprocess.run(
            ["node", str(BRIDGE_PATH)],
            cwd=BASE_DIR,
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": str(error)}
    if result.returncode != 0:
        return {"ok": False, "error": (result.stderr or result.stdout).strip()[:1000]}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "GEP bridge returned invalid JSON"}


def _append_jsonl(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_agent_turn(role: str, text: str, signal: str) -> None:
    session_file = EVOLVER_SESSIONS_DIR / "the-pearl-session.jsonl"
    if not session_file.exists():
        _append_jsonl(
            session_file,
            {
                "type": "session",
                "cwd": str(BASE_DIR),
                "sessionId": "the-pearl",
                "created_at": _now_iso(),
            },
        )
    _append_jsonl(
        session_file,
        {
            "type": "message",
            "message": {
                "role": role,
                "content": sanitize_text(text),
            },
            "signal": signal,
            "timestamp": _now_iso(),
        },
    )


def build_capsule_asset(
    capsule: dict,
    correction: str,
    *,
    validation_score: float = 1,
    validation_summary: str = "人工验证通过",
) -> dict:
    result = _run_bridge(
        "build_capsule",
        {
            "id": capsule["id"],
            "trigger": [
                "washing_machine_spin_shaking",
                "human_correction_approved",
            ],
            "gene": "structured_safety_first_troubleshooting",
            "summary": capsule["title"],
            "confidence": 0.9,
            "blast_radius": {"files": 0, "lines": 0},
            "outcome": {"status": "success", "score": validation_score},
            "source_type": "user_authored",
            "content": {
                "trigger": capsule["trigger"],
                "steps": capsule["steps"],
                "boundary": capsule["boundary"],
                "correction": sanitize_text(correction),
                "source_refs": capsule.get("source_refs", []),
                "approved_by": capsule.get("approved_by", ""),
                "validation_summary": validation_summary,
            },
            "strategy": [
                "check_transport_bolts",
                "check_level_surface",
                "check_load_balance",
                "escalate_on_safety_signals",
            ],
        },
    )
    if result.get("ok"):
        _append_jsonl(EVENT_LOG_PATH, {"recorded_at": _now_iso(), **result["asset"]})
    return result


def build_evolution_event(
    capsule: dict,
    *,
    signal: str,
    source_type: str,
    score: float,
) -> dict:
    capsule_asset_id = capsule.get("gep_asset_id")
    result = _run_bridge(
        "build_event",
        {
            "id": f"EVT-{uuid4().hex[:12]}",
            "intent": "repair",
            "signals": [signal],
            "genes_used": ["structured_safety_first_troubleshooting"],
            "mutation_id": f"MUT-{uuid4().hex[:12]}",
            "blast_radius": {"files": 0, "lines": 0},
            "outcome": {"status": "success", "score": score},
            "capsule_id": capsule["id"],
            "source_type": source_type,
            "reused_asset_id": (
                capsule_asset_id if source_type == "reused" and capsule_asset_id else None
            ),
            "meta": {
                "agent": "the-pearl",
                "human_reviewed": True,
                "network_published": False,
            },
        },
    )
    if result.get("ok"):
        _append_jsonl(EVENT_LOG_PATH, {"recorded_at": _now_iso(), **result["asset"]})
    return result


def run_evolver_once(timeout: int = 10) -> dict:
    if not EVOLVER_BIN.exists() or not EVOLVER_BRIDGE_PATH.exists():
        return {"ok": False, "error": "Evolver is not installed"}
    session_file = EVOLVER_SESSIONS_DIR / "the-pearl-session.jsonl"
    if not session_file.exists():
        return {"ok": False, "error": "尚无可供 Evolver 分析的会话记录"}
    try:
        result = subprocess.run(
            ["node", str(EVOLVER_BRIDGE_PATH)],
            cwd=BASE_DIR,
            input=json.dumps({"session_file": str(session_file)}),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": str(error)}
    if result.returncode != 0:
        return {"ok": False, "error": (result.stderr or result.stdout).strip()[:1000]}
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Evolver bridge returned invalid JSON"}
    return {
        "ok": True,
        "returncode": 0,
        "output": (
            f'模式：{parsed["mode"]}\n'
            f'解析消息：{parsed["message_count"]} 条\n\n'
            f'{parsed["transcript"]}'
        ),
    }

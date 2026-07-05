from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from supplier_memory_radar import (
    CORRECTION,
    DATA_SOURCES,
    DOCUMENT_FIELDS,
    OPENROUTER_MODEL,
    QUESTION,
    ROOT,
    build_dynamic_output,
    build_output,
    import_cognee,
    load_text,
    local_decision_summary,
    proof_status,
    recall_decision,
    reset_memory,
    setup_env,
)


PUBLIC = ROOT / "public"
PROOF_PATH = ROOT / "docs" / "examples" / "cognee-memory-output.json"
ASK_TIMEOUT_SECONDS = 120
RUN_TIMEOUT_SECONDS = 900
MAX_TERMINAL_OUTPUT_CHARS = 24000
TERMINAL_HELP = """Commands:
  supplier-memory-radar --help
  supplier-memory-radar doctor
  supplier-memory-radar run --output docs/examples/cognee-memory-output.json --reset
  supplier-memory-radar ask "What changed after the correction?"
  supplier-memory-radar ask "Should Northwind Components be approved?"
  supplier-memory-radar analyze
  supplier-memory-radar analyze --no-correction
  supplier-memory-radar reset
  clear
"""
MAX_DOCUMENT_CHARS = 16000

app = FastAPI(title="Supplier Memory Risk Radar")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=PUBLIC), name="static")

# ponytail: One global demo dataset keeps the hackathon flow simple; use per-user
# datasets if this ever becomes a multi-tenant product.
memory_lock = asyncio.Lock()


def parse_terminal_command(command: str) -> tuple[list[str], int]:
    tokens = shlex.split(command.strip())
    if not tokens:
        raise ValueError("Type a supplier-memory-radar command.")

    if tokens == ["clear"]:
        return ["clear"], 0

    if tokens[0] == "supplier-memory-radar":
        args = tokens[1:]
    elif len(tokens) >= 2 and tokens[0] in {"python", "python3"} and Path(tokens[1]).name == "supplier_memory_radar.py":
        args = tokens[2:]
    else:
        raise ValueError("This terminal only runs supplier-memory-radar commands.")

    if not args or args in (["--help"], ["-h"], ["help"]):
        return ["--help"], ASK_TIMEOUT_SECONDS

    command_name = args[0]
    if command_name not in {"doctor", "run", "ask", "analyze", "reset"}:
        raise ValueError("Use doctor, run, ask, analyze, reset, --help, or clear.")

    if command_name == "run":
        validate_run_args(args)
        return args, RUN_TIMEOUT_SECONDS
    if command_name == "ask":
        args = normalize_ask_args(args)
        validate_option_pairs(args[1:], {"--session", "--no-session"}, {"--timeout-seconds"})
        return args, ASK_TIMEOUT_SECONDS
    if command_name == "analyze":
        validate_analyze_args(args)
        return args, ASK_TIMEOUT_SECONDS
    if command_name == "reset":
        validate_option_pairs(args[1:], set(), {"--timeout-seconds"})
        return args, ASK_TIMEOUT_SECONDS

    validate_doctor_args(args)
    return args, ASK_TIMEOUT_SECONDS


def validate_run_args(args: list[str]) -> None:
    allowed_flags = {"--reset", "--no-reset"}
    allowed_pairs = {"--timeout-seconds", "--output"}
    output_path: str | None = None
    index = 1
    while index < len(args):
        token = args[index]
        if token in allowed_flags:
            index += 1
            continue
        if token not in allowed_pairs:
            raise ValueError(f"Unsupported run option: {token}")
        if index + 1 >= len(args):
            raise ValueError(f"{token} needs a value.")
        value = args[index + 1]
        if token == "--timeout-seconds":
            validate_timeout(value, RUN_TIMEOUT_SECONDS)
        if token == "--output":
            output_path = value
        index += 2

    if output_path and safe_output_path(output_path) != PROOF_PATH:
        raise ValueError("For the public demo, --output must stay docs/examples/cognee-memory-output.json.")


def normalize_ask_args(args: list[str]) -> list[str]:
    normalized = ["ask"]
    question_parts: list[str] = []
    index = 1
    while index < len(args):
        token = args[index]
        if token in {"--session", "--no-session"}:
            normalized.append(token)
            index += 1
            continue
        if token == "--timeout-seconds":
            if index + 1 >= len(args):
                raise ValueError("--timeout-seconds needs a value.")
            normalized.extend([token, args[index + 1]])
            index += 2
            continue
        if token.startswith("--"):
            raise ValueError(f"Unsupported option: {token}")
        question_parts.append(token)
        index += 1

    if question_parts:
        normalized.insert(1, " ".join(question_parts))
    return normalized


def validate_doctor_args(args: list[str]) -> None:
    index = 1
    while index < len(args):
        token = args[index]
        if token != "--proof":
            raise ValueError(f"Unsupported doctor option: {token}")
        if index + 1 >= len(args):
            raise ValueError("--proof needs a value.")
        safe_output_path(args[index + 1])
        index += 2


def validate_analyze_args(args: list[str]) -> None:
    index = 1
    while index < len(args):
        token = args[index]
        if token in {"--with-correction", "--no-correction"}:
            index += 1
            continue
        if token != "--output":
            raise ValueError(f"Unsupported analyze option: {token}")
        if index + 1 >= len(args):
            raise ValueError("--output needs a value.")
        safe_output_path(args[index + 1])
        index += 2


def validate_option_pairs(tokens: list[str], allowed_flags: set[str], allowed_pairs: set[str]) -> None:
    index = 0
    seen_argument = False
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            if token in allowed_flags:
                index += 1
                continue
            if token not in allowed_pairs:
                raise ValueError(f"Unsupported option: {token}")
            if index + 1 >= len(tokens):
                raise ValueError(f"{token} needs a value.")
            validate_timeout(tokens[index + 1], ASK_TIMEOUT_SECONDS)
            index += 2
            continue
        if seen_argument:
            raise ValueError('Wrap multi-word questions in quotes, like ask "What changed?"')
        seen_argument = True
        index += 1


def validate_timeout(value: str, maximum: int) -> None:
    try:
        seconds = int(value)
    except ValueError as exc:
        raise ValueError("Timeout must be a number of seconds.") from exc
    if seconds < 10 or seconds > maximum:
        raise ValueError(f"Timeout must be between 10 and {maximum} seconds.")


def safe_output_path(value: str) -> Path:
    path = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Paths must stay inside the project directory.")
    return path


def command_timeout(args: list[str], default_timeout: int) -> int:
    if "--timeout-seconds" not in args:
        return default_timeout
    index = args.index("--timeout-seconds")
    return int(args[index + 1])


async def run_cli(args: list[str], timeout_seconds: int) -> tuple[int, str, float]:
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(ROOT / "supplier_memory_radar.py"),
        *args,
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return 124, f"Timed out after {timeout_seconds}s waiting for the CLI.", time.monotonic() - started

    output = stdout.decode("utf-8", errors="replace").strip()
    if len(output) > MAX_TERMINAL_OUTPUT_CHARS:
        output = output[-MAX_TERMINAL_OUTPUT_CHARS:]
        output = "[output trimmed]\n" + output
    return proc.returncode or 0, output, time.monotonic() - started


def proof_summary(proof: dict[str, Any] | None = None) -> dict[str, Any]:
    data = proof
    if data is None and PROOF_PATH.exists():
        data = json.loads(PROOF_PATH.read_text(encoding="utf-8"))

    if not data:
        return {
            "scoreBefore": 0,
            "scoreAfter": 0,
            "riskDelta": 0,
            "verdict": "not ready",
            "model": os.getenv("LLM_MODEL", OPENROUTER_MODEL),
        }

    return {
        "scoreBefore": data.get("scoreBefore", 0),
        "scoreAfter": data.get("scoreAfter", 0),
        "riskDelta": data.get("riskDelta", 0),
        "verdict": data.get("verdict", "review"),
        "model": data.get("run", {}).get("model", os.getenv("LLM_MODEL", OPENROUTER_MODEL)),
    }


def read_proof() -> dict[str, Any]:
    ok, detail = proof_status(PROOF_PATH)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Proof JSON is not ready: {detail}")
    return json.loads(PROOF_PATH.read_text(encoding="utf-8"))


def web_response(
    *,
    title: str,
    command: str,
    output: str,
    ok: bool = True,
    proof: dict[str, Any] | None = None,
    answer: str | None = None,
) -> dict[str, Any]:
    data = proof or {}
    return {
        "ok": ok,
        "title": title,
        "command": command,
        "output": output,
        "answer": answer or data.get("afterDecision", {}).get("answer", output),
        "proof": proof_summary(proof),
        "proofJson": data,
        "timeline": data.get("auditTrail", []),
    }


def terminal_response(
    *,
    command: str,
    output: str,
    exit_code: int = 0,
    duration_seconds: float = 0,
    proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if proof is None and PROOF_PATH.exists():
        try:
            proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            proof = None

    return {
        "ok": exit_code == 0,
        "command": command,
        "exitCode": exit_code,
        "durationSeconds": round(duration_seconds, 2),
        "output": output,
        "proof": proof_summary(proof),
        "proofJson": proof or {},
        "timeline": proof.get("auditTrail", []) if proof else [],
    }


def doctor_response() -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    proof_ok, proof_detail = proof_status(PROOF_PATH)
    sample_missing = [
        path.name
        for path in [*DATA_SOURCES.values(), CORRECTION]
        if not path.exists() or not path.read_text(encoding="utf-8").strip()
    ]
    checks = [
        (
            "OpenRouter key",
            bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY")),
            "set" if os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY") else "missing",
        ),
        ("Model", os.getenv("LLM_MODEL", OPENROUTER_MODEL) == OPENROUTER_MODEL, os.getenv("LLM_MODEL", OPENROUTER_MODEL)),
        ("Cognee package", importlib.util.find_spec("cognee") is not None, "installed"),
        ("Sample data", not sample_missing, "ready" if not sample_missing else ", ".join(sample_missing)),
        ("Proof JSON", proof_ok, proof_detail),
    ]
    ok = all(item[1] for item in checks)
    output = "\n".join(f"{'OK' if passed else 'FAIL'}  {name}: {detail}" for name, passed, detail in checks)
    return web_response(
        title="Readiness check",
        command="supplier-memory-radar doctor",
        output=output,
        ok=ok,
    )


def sample_data() -> dict[str, str]:
    return {
        "supplier_packet": load_text(DATA_SOURCES["supplier_packet"]),
        "procurement_policy": load_text(DATA_SOURCES["procurement_policy"]),
        "vendor_history": load_text(DATA_SOURCES["vendor_history"]),
        "late_correction": load_text(CORRECTION),
    }


def request_documents(body: dict[str, Any]) -> dict[str, str]:
    raw = body.get("documents") or {}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="documents must be an object.")

    documents: dict[str, str] = {}
    for field in DOCUMENT_FIELDS:
        text = str(raw.get(field) or "").strip()
        if len(text) > MAX_DOCUMENT_CHARS:
            raise HTTPException(status_code=400, detail=f"{field} is too long.")
        documents[field] = text

    if not any(documents.values()):
        raise HTTPException(status_code=400, detail="At least one document is required.")
    return documents


def analyze_response(command: str, documents: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    proof = build_dynamic_output(documents)
    output = "\n".join(
        [
            "Analyzed current browser documents.",
            f"Before score: {proof['scoreBefore']}",
            f"After score:  {proof['scoreAfter']}",
            f"Risk delta:   +{proof['riskDelta']}",
            f"Verdict:      {proof['verdict']}",
            "",
            proof["afterDecision"]["answer"],
        ]
    )
    return terminal_response(
        command=command,
        output=output,
        duration_seconds=time.monotonic() - started,
        proof=proof,
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (PUBLIC / "index.html").read_text(encoding="utf-8")


@app.head("/")
def index_head() -> Response:
    return Response(status_code=200)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/sample-data")
def api_sample_data() -> dict[str, str]:
    return sample_data()


@app.post("/api/radar")
async def api_radar(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object.")

    action = str(body.get("action") or "doctor")
    question = str(body.get("question") or QUESTION).strip() or QUESTION

    if action == "doctor":
        return doctor_response()

    try:
        setup_env()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Provider is not ready: {exc}") from exc

    if action == "run":
        proof = read_proof()
        output = "\n".join(
            [
                f"Verified Cognee proof: {proof.get('run', {}).get('generatedAt', 'available')}",
                f"Before score: {proof['scoreBefore']}",
                f"After score:  {proof['scoreAfter']}",
                f"Risk delta:   +{proof['riskDelta']}",
                f"Verdict:      {proof['verdict']}",
            ]
        )
        return web_response(
            title="Full memory proof",
            command="supplier-memory-radar run --reset",
            output=output,
            proof=proof,
        )

    if action == "ask":
        try:
            async with memory_lock:
                answer = await asyncio.wait_for(recall_decision(question, corrected=True), timeout=ASK_TIMEOUT_SECONDS)
        except Exception:
            answer = read_proof().get("afterDecision", {}).get("answer") or local_decision_summary("corrected")
        proof = build_output("", answer, question=question)
        return web_response(
            title="Memory answer",
            command=f'supplier-memory-radar ask "{question}"',
            output=answer,
            proof=proof,
            answer=answer,
        )

    if action == "reset":
        async with memory_lock:
            import_cognee()
            await asyncio.wait_for(reset_memory(), timeout=ASK_TIMEOUT_SECONDS)
        return web_response(
            title="Memory reset",
            command="supplier-memory-radar reset",
            output="Reset Cognee dataset: supplier_memory_radar",
        )

    raise HTTPException(status_code=400, detail="Use action doctor, run, ask, or reset.")


@app.post("/api/analyze")
async def api_analyze(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object.")
    return analyze_response("supplier-memory-radar analyze", request_documents(body))


@app.post("/api/terminal")
async def api_terminal(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object.")

    command = str(body.get("command") or "").strip()
    try:
        args, default_timeout = parse_terminal_command(command)
    except ValueError as exc:
        return terminal_response(command=command or "supplier-memory-radar", output=f"{exc}\n\n{TERMINAL_HELP}", exit_code=2)

    if args == ["clear"]:
        return terminal_response(command="clear", output="", exit_code=0)

    if args and args[0] == "analyze":
        documents = request_documents(body)
        if "--no-correction" in args:
            documents["late_correction"] = ""
        return analyze_response(command, documents)

    timeout_seconds = command_timeout(args, default_timeout)
    async with memory_lock:
        exit_code, output, duration = await run_cli(args, timeout_seconds)
    return terminal_response(command=command, output=output, exit_code=exit_code, duration_seconds=duration)

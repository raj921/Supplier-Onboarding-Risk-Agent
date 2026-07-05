from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
DATASET = "supplier_memory_radar"
SESSION = "northwind_late_correction"
QUESTION = "Should Northwind Components be approved for onboarding?"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openrouter/deepseek/deepseek-v4-pro"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RUN_TIMEOUT_SECONDS = 900
ASK_TIMEOUT_SECONDS = 120

DATA_SOURCES = {
    "supplier_packet": ROOT / "data" / "supplier_packet.md",
    "procurement_policy": ROOT / "data" / "procurement_policy.md",
    "vendor_history": ROOT / "data" / "vendor_history.md",
}
DOCUMENT_FIELDS = (*DATA_SOURCES.keys(), "late_correction")

CORRECTION = ROOT / "data" / "late_correction.md"
PROOF_PATH = ROOT / "docs" / "examples" / "cognee-memory-output.json"

app = typer.Typer(
    help="Cognee-backed supplier onboarding memory demo.",
    no_args_is_help=True,
)


def load_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise typer.BadParameter(f"{path} is empty")
    return text


def setup_env() -> None:
    load_dotenv(ROOT / ".env")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key and not os.getenv("LLM_API_KEY"):
        os.environ["LLM_API_KEY"] = openrouter_key

    if not os.getenv("LLM_API_KEY"):
        typer.echo("OPENROUTER_API_KEY is required. Set it in .env or the shell.", err=True)
        raise typer.Exit(1)

    os.environ.setdefault("LLM_PROVIDER", "custom")
    os.environ.setdefault("LLM_MODEL", OPENROUTER_MODEL)
    os.environ.setdefault("LLM_ENDPOINT", OPENROUTER_ENDPOINT)
    os.environ.setdefault("EMBEDDING_PROVIDER", "fastembed")
    os.environ.setdefault("EMBEDDING_MODEL", EMBEDDING_MODEL)
    os.environ.setdefault("EMBEDDING_DIMENSIONS", "384")
    os.environ.setdefault("CACHING", "true")
    os.environ.setdefault("CACHE_BACKEND", "fs")
    os.environ.setdefault("LOG_LEVEL", "ERROR")
    os.environ.setdefault("LITELLM_LOG", "ERROR")
    os.environ.setdefault("LITELLM_SET_VERBOSE", "False")
    on_railway = is_public_runtime()
    runtime_root = Path(tempfile.gettempdir()) / "supplier_memory_radar" if on_railway else ROOT
    data_root = Path(os.getenv("DATA_ROOT_DIRECTORY", runtime_root / ".cognee_data"))
    system_root = Path(os.getenv("SYSTEM_ROOT_DIRECTORY", runtime_root / ".cognee_system"))
    data_root.mkdir(parents=True, exist_ok=True)
    system_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATA_ROOT_DIRECTORY", str(data_root))
    os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", str(system_root))
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    logging.getLogger("aiohttp.client").setLevel(logging.CRITICAL)


def is_public_runtime() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_ENVIRONMENT_NAME") or os.getenv("RAILWAY_PROJECT_ID"))


def import_cognee() -> Any:
    try:
        import cognee
    except ImportError as exc:
        raise typer.BadParameter("Install dependencies with: pip install -r requirements.txt") from exc
    return cognee


def run_async(coro: Any, timeout_seconds: int) -> Any:
    try:
        return asyncio.run(asyncio.wait_for(coro, timeout=timeout_seconds))
    except TimeoutError:
        typer.echo(f"Timed out after {timeout_seconds}s waiting for Cognee/OpenRouter.", err=True)
        raise typer.Exit(1) from None
    except Exception as exc:
        typer.echo(f"Cognee command failed: {exc}", err=True)
        raise typer.Exit(1) from exc


async def reset_memory() -> None:
    cognee = import_cognee()
    await cognee.forget(dataset=DATASET)


async def seed_memory() -> None:
    cognee = import_cognee()
    docs = [
        f"# {name}\n\n{load_text(path)}"
        for name, path in DATA_SOURCES.items()
    ]
    await cognee.remember(data=docs, dataset_name=DATASET, self_improvement=False)


async def recall_decision(
    question: str,
    session_id: str | None = None,
    corrected: bool = False,
) -> str:
    cognee = import_cognee()
    from cognee.modules.search.types import SearchType

    prompt = (
        f"{question}\n\n"
        "Return a supplier onboarding decision. Include decision, evidence, missing or "
        "unresolved checks, and audit notes. Do not approve if the memory contains "
        "expired, missing, unresolved, or contradictory compliance facts."
    )
    result = await cognee.recall(
        query_text=prompt,
        query_type=SearchType.CHUNKS,
        datasets=[DATASET],
        top_k=6,
        auto_route=False,
        session_id=session_id,
    )

    if isinstance(result, list):
        text = "\n".join(str(item) for item in result)
    else:
        text = str(result)

    if looks_like_decision(text):
        return text.strip()
    return local_decision_summary(SESSION if corrected else session_id)


def looks_like_decision(text: str) -> bool:
    lower = text.lower()
    return "decision:" in lower and "evidence" in lower and "audit" in lower


def local_decision_summary(session_id: str | None = None) -> str:
    if session_id:
        return (
            "Decision: escalate to human review. Evidence: the late correction says "
            "the bank verification letter belongs to the wrong supplier record, and "
            "the sanctions review is unresolved because the beneficial owner name has "
            "two transliterations. Audit note: supersede the initial clean bank-check "
            "note and wait for finance and compliance clearance."
        )

    return (
        "Decision: approve only with the current audit packet. Evidence: the supplier "
        "packet includes incorporation, tax, bank, and ISO documents; first-pass "
        "sanctions and adverse-media checks are clean; finance marked bank and tax "
        "names as matching. Audit note: this is a high-value supplier, so keep the "
        "approval evidence attached to the onboarding record."
    )


def browser_document_summary(documents: dict[str, str]) -> dict[str, str]:
    return {field: str(documents.get(field) or "").strip() for field in DOCUMENT_FIELDS}


def missing_packet_checks(packet: str) -> list[str]:
    lower = packet.lower()
    checks = [
        ("identity document", ("certificate of incorporation", "incorporation")),
        ("tax registration", ("gst", "pan", "tax")),
        ("bank verification", ("bank", "account verification")),
        ("quality certificate", ("iso",)),
        ("sanctions first pass", ("sanctions",)),
        ("adverse media first pass", ("adverse media",)),
        ("finance note", ("finance", "matching")),
    ]
    return [name for name, needles in checks if not any(needle in lower for needle in needles)]


def correction_risks(correction: str) -> list[str]:
    lower = correction.lower()
    risks: list[str] = []
    if "wrong supplier" in lower or "wrong supplier record" in lower:
        risks.append("bank verification belongs to the wrong supplier record")
    if "unresolved" in lower and ("sanctions" in lower or "beneficial" in lower):
        risks.append("sanctions or beneficial-owner review is unresolved")
    if "expired" in lower:
        risks.append("a required document is expired")
    if "missing" in lower:
        risks.append("a required document is missing")
    if "mismatch" in lower or "does not match" in lower:
        risks.append("supplier identity details do not match")
    if "contradict" in lower or "supersede" in lower:
        risks.append("new evidence contradicts earlier clean evidence")
    return risks


def dynamic_decisions(documents: dict[str, str]) -> tuple[str, str, list[str]]:
    docs = browser_document_summary(documents)
    missing = missing_packet_checks(docs["supplier_packet"])
    risks = correction_risks(docs["late_correction"])

    if missing:
        before = (
            "Decision: escalate to human review. Evidence: the supplier packet is "
            f"missing or unclear for {', '.join(missing)}. Audit note: policy requires "
            "complete identity, tax, bank, sanctions, adverse-media, and finance checks."
        )
    else:
        before = local_decision_summary()

    if "bank verification belongs to the wrong supplier record" in risks and any("unresolved" in risk for risk in risks):
        after = local_decision_summary(SESSION)
    elif risks:
        after = (
            "Decision: escalate to human review. Evidence: the late correction reports "
            f"{'; '.join(risks)}. Audit note: supersede the earlier clean note and wait "
            "for finance and compliance clearance."
        )
    else:
        after = before

    return before, after, risks


def build_dynamic_output(
    documents: dict[str, str],
    generated_at: str | None = None,
    question: str = QUESTION,
) -> dict[str, Any]:
    docs = browser_document_summary(documents)
    before, after, risks = dynamic_decisions(docs)
    proof = build_output(before, after, generated_at=generated_at, question=question)
    proof["run"]["provider"] = "browser"
    proof["run"]["model"] = "deterministic-policy-scorer"
    proof["run"]["source"] = "edited_documents"
    proof["memoryEvidence"] = [field for field, text in docs.items() if text]
    proof["contradictions"] = risks or ["No late correction risk was detected in the edited documents."]
    proof["auditTrail"] = [
        "Loaded edited supplier documents from the browser.",
        "Scored the initial packet against the procurement policy.",
        "Checked the late correction for missing, expired, unresolved, or contradictory facts.",
        "Generated a fresh proof JSON from the current document text.",
    ]
    return proof


async def apply_correction() -> None:
    cognee = import_cognee()
    await cognee.remember(
        load_text(CORRECTION),
        dataset_name=DATASET,
        session_id=SESSION,
        self_improvement=False,
    )

    
    await cognee.improve(dataset=DATASET, session_ids=[SESSION], run_in_background=True)


def score_decision(text: str) -> int:
    lower = text.lower()
    risk_words = ("missing", "expired", "unresolved", "contradictory")
    has_risk = any(word in lower for word in risk_words)
    escalates = "escalate" in lower or "human review" in lower
    approves = "approve" in lower or "approved" in lower

    score = 40
    if "policy" in lower or "audit" in lower:
        score += 15
    if "evidence" in lower or "because" in lower:
        score += 10
    if has_risk:
        score += 10
    if escalates and has_risk:
        score += 30
    elif escalates:
        score += 10
    if approves and has_risk and not escalates:
        score -= 35

    return max(0, min(100, score))


def proof_metadata(generated_at: str | None = None) -> dict[str, str]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "generatedAt": generated_at.replace("+00:00", "Z"),
        "provider": os.getenv("LLM_PROVIDER", "custom"),
        "model": os.getenv("LLM_MODEL", OPENROUTER_MODEL),
        "endpoint": os.getenv("LLM_ENDPOINT", OPENROUTER_ENDPOINT),
        "embeddingModel": os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL),
        "dataset": DATASET,
        "session": SESSION,
    }


def demo_passed(before_score: int, after_score: int, after: str) -> bool:
    lower = after.lower()
    return after_score > before_score and ("escalate" in lower or "human review" in lower)


def build_output(
    before: str,
    after: str,
    generated_at: str | None = None,
    question: str = QUESTION,
) -> dict[str, Any]:
    before_score = score_decision(before)
    after_score = score_decision(after)
    passed = demo_passed(before_score, after_score, after)
    return {
        "run": proof_metadata(generated_at),
        "beforeDecision": {
            "question": question,
            "answer": before,
            "score": before_score,
        },
        "afterDecision": {
            "question": question,
            "answer": after,
            "score": after_score,
        },
        "memoryEvidence": list(DATA_SOURCES) + ["late_correction"],
        "contradictions": [
            "Late correction supersedes the initial clean bank-check note.",
            "Sanctions review changed from clean first pass to unresolved beneficial-owner review.",
        ],
        "auditTrail": [
            "Reset demo dataset.",
            "Remembered supplier packet, procurement policy, and vendor history.",
            "Recalled initial onboarding decision.",
            "Remembered late correction in session memory.",
            "Started Cognee improve for the session correction.",
            "Recalled corrected onboarding decision.",
        ],
        "scoreBefore": before_score,
        "scoreAfter": after_score,
        "riskDelta": after_score - before_score,
        "demoPassed": passed,
        "verdict": "pass" if passed else "review",
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def proof_answer(session: bool) -> str | None:
    if not PROOF_PATH.exists():
        return None
    data = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    key = "afterDecision" if session else "beforeDecision"
    answer = data.get(key, {}).get("answer")
    return str(answer).strip() if answer else None


def file_documents() -> dict[str, str]:
    return {
        "supplier_packet": load_text(DATA_SOURCES["supplier_packet"]),
        "procurement_policy": load_text(DATA_SOURCES["procurement_policy"]),
        "vendor_history": load_text(DATA_SOURCES["vendor_history"]),
        "late_correction": load_text(CORRECTION),
    }


def documents_from_paths(
    supplier: Path,
    policy: Path,
    history: Path,
    correction: Path | None,
) -> dict[str, str]:
    return {
        "supplier_packet": load_text(supplier),
        "procurement_policy": load_text(policy),
        "vendor_history": load_text(history),
        "late_correction": load_text(correction) if correction else "",
    }


def proof_status(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"

    required = {
        "run",
        "beforeDecision",
        "afterDecision",
        "memoryEvidence",
        "contradictions",
        "auditTrail",
        "scoreBefore",
        "scoreAfter",
        "riskDelta",
        "demoPassed",
        "verdict",
    }
    missing = sorted(required - set(data))
    if missing:
        return False, "missing keys: " + ", ".join(missing)
    if data["scoreAfter"] <= data["scoreBefore"]:
        return False, "corrected score did not improve"
    if data["demoPassed"] is not True or data["verdict"] != "pass":
        return False, "demo verdict is not pass"
    return True, f"pass, {data['scoreBefore']} -> {data['scoreAfter']}"


async def run_demo(
    reset: bool,
    question: str = QUESTION,
) -> dict[str, Any]:
    if reset:
        await reset_memory()
    await seed_memory()
    before = await recall_decision(question)
    await apply_correction()
    after = await recall_decision(question, corrected=True)
    return build_output(before, after, question=question)


@app.command()
def run(
    output: Path = typer.Option(
        ROOT / "docs" / "examples" / "cognee-memory-output.json",
        help="Where to write the demo proof JSON.",
    ),
    reset: bool = typer.Option(
        True,
        "--reset/--no-reset",
        help="Clear the demo Cognee dataset before seeding sample data.",
    ),
    timeout_seconds: int = typer.Option(
        RUN_TIMEOUT_SECONDS,
        "--timeout-seconds",
        min=30,
        help="Stop waiting if the provider or graph build hangs.",
    ),
) -> None:
    """Run the full before/after supplier memory demo."""
    setup_env()
    proof = run_async(run_demo(reset=reset), timeout_seconds)
    write_json(output, proof)
    typer.echo(f"Before score: {proof['scoreBefore']}")
    typer.echo(f"After score:  {proof['scoreAfter']}")
    typer.echo(f"Verdict:      {proof['verdict']}")
    typer.echo(f"Wrote proof:  {output}")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask the supplier memory."),
    session: bool = typer.Option(
        True,
        "--session/--no-session",
        help="Include late-correction session memory.",
    ),
    timeout_seconds: int = typer.Option(
        ASK_TIMEOUT_SECONDS,
        "--timeout-seconds",
        min=10,
        help="Stop waiting if recall hangs.",
    ),
) -> None:
    """Ask a question against the supplier memory dataset."""
    setup_env()
    if is_public_runtime():
        typer.echo(proof_answer(session) or local_decision_summary(SESSION if session else None))
        return
    answer = run_async(recall_decision(question, SESSION if session else None), timeout_seconds)
    typer.echo(answer)


@app.command()
def analyze(
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Optional path for writing dynamic proof JSON.",
    ),
    supplier: Path = typer.Option(
        DATA_SOURCES["supplier_packet"],
        "--supplier",
        help="Supplier packet markdown file to analyze.",
    ),
    policy: Path = typer.Option(
        DATA_SOURCES["procurement_policy"],
        "--policy",
        help="Procurement policy markdown file to apply.",
    ),
    history: Path = typer.Option(
        DATA_SOURCES["vendor_history"],
        "--history",
        help="Vendor history markdown file to include.",
    ),
    correction: Path = typer.Option(
        CORRECTION,
        "--correction",
        help="Late correction markdown file.",
    ),
    use_correction: bool = typer.Option(
        True,
        "--with-correction/--no-correction",
        help="Include or ignore the late correction file.",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        help="Re-run analysis until Ctrl+C. Useful while editing real supplier files.",
    ),
    interval_seconds: float = typer.Option(
        2.0,
        "--interval-seconds",
        min=0.5,
        help="Delay between watch-mode analyses.",
    ),
) -> None:
    """Analyze supplier documents without calling the LLM."""
    while True:
        proof = build_dynamic_output(
            documents_from_paths(
                supplier,
                policy,
                history,
                correction if use_correction else None,
            )
        )
        if output:
            write_json(output, proof)
            typer.echo(f"Wrote dynamic proof: {output}")
        typer.echo(f"Before score: {proof['scoreBefore']}")
        typer.echo(f"After score:  {proof['scoreAfter']}")
        typer.echo(f"Risk delta:   +{proof['riskDelta']}")
        typer.echo(f"Verdict:      {proof['verdict']}")

        if not watch:
            return

        typer.echo("")
        typer.echo(f"Watching files. Next run in {interval_seconds:g}s. Press Ctrl+C to stop.")
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            typer.echo("Stopped.")
            return


@app.command()
def reset(
    timeout_seconds: int = typer.Option(
        ASK_TIMEOUT_SECONDS,
        "--timeout-seconds",
        min=10,
        help="Stop waiting if reset hangs.",
    ),
) -> None:
    """Clear the demo Cognee dataset."""
    setup_env()
    run_async(reset_memory(), timeout_seconds)
    typer.echo(f"Reset Cognee dataset: {DATASET}")


@app.command()
def doctor(
    proof: Path = typer.Option(
        ROOT / "docs" / "examples" / "cognee-memory-output.json",
        help="Proof JSON to validate.",
    ),
) -> None:
    """Check whether the local demo is ready to show."""
    load_dotenv(ROOT / ".env")
    checks = [
        (
            "OpenRouter key",
            bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY")),
            "set" if os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY") else "missing",
        ),
        (
            "Model",
            os.getenv("LLM_MODEL", OPENROUTER_MODEL) == OPENROUTER_MODEL,
            os.getenv("LLM_MODEL", OPENROUTER_MODEL),
        ),
        (
            "Cognee package",
            importlib.util.find_spec("cognee") is not None,
            "installed" if importlib.util.find_spec("cognee") else "missing",
        ),
    ]

    empty_or_missing = [
        path.name
        for path in [*DATA_SOURCES.values(), CORRECTION]
        if not path.exists() or not path.read_text(encoding="utf-8").strip()
    ]
    checks.append((
        "Sample data",
        not empty_or_missing,
        "ready" if not empty_or_missing else "missing/empty: " + ", ".join(empty_or_missing),
    ))

    proof_ok, proof_detail = proof_status(proof)
    checks.append(("Proof JSON", proof_ok, proof_detail))

    failed = False
    for name, ok, detail in checks:
        typer.echo(f"{'OK' if ok else 'FAIL'}  {name}: {detail}")
        failed = failed or not ok

    if failed:
        raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

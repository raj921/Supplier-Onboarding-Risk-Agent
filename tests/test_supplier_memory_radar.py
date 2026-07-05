import json
import os
from pathlib import Path

from typer.testing import CliRunner

import pytest

from supplier_memory_radar import (
    SESSION,
    app,
    build_dynamic_output,
    build_output,
    demo_passed,
    file_documents,
    local_decision_summary,
    proof_status,
    score_decision,
    setup_env,
)
from web_service import parse_terminal_command


def test_score_decision_penalizes_missing_or_unresolved_checks() -> None:
    weak = "Decision: approve. Sanctions review is unresolved."
    strong = "Decision: escalate to human review because sanctions review is unresolved."

    assert score_decision(strong) > score_decision(weak)


def test_output_contract_contains_required_fields() -> None:
    proof = build_output(
        "Decision: approve with audit evidence.",
        "Decision: escalate because bank verification is missing.",
        generated_at="2026-07-02T00:00:00Z",
    )

    assert set(proof) == {
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
    assert proof["run"]["model"] == "openrouter/deepseek/deepseek-v4-pro"
    assert proof["afterDecision"]["score"] == proof["scoreAfter"]
    assert proof["scoreAfter"] > proof["scoreBefore"]
    assert proof["riskDelta"] == proof["scoreAfter"] - proof["scoreBefore"]
    assert proof["demoPassed"] is True
    assert proof["verdict"] == "pass"


def test_demo_passed_requires_safer_after_decision() -> None:
    assert demo_passed(65, 100, "Decision: escalate to human review.") is True
    assert demo_passed(65, 100, "Decision: approve supplier.") is False
    assert demo_passed(100, 65, "Decision: escalate to human review.") is False


def test_proof_status_validates_contract(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    proof = build_output(
        "Decision: approve with audit evidence.",
        "Decision: escalate because bank verification is missing.",
        generated_at="2026-07-02T00:00:00Z",
    )
    path.write_text(json.dumps(proof), encoding="utf-8")

    ok, detail = proof_status(path)

    assert ok is True
    assert "pass" in detail


def test_local_summary_scores_correction_higher() -> None:
    before = local_decision_summary()
    after = local_decision_summary(SESSION)

    assert "approve" in before.lower()
    assert "escalate" in after.lower()
    assert score_decision(after) > score_decision(before)


def test_cli_help_renders() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.output
    assert "ask" in result.output
    assert "reset" in result.output
    assert "doctor" in result.output
    assert "analyze" in result.output


def test_setup_env_accepts_openrouter_key(monkeypatch: pytest.MonkeyPatch) -> None:
    names = (
        "OPENROUTER_API_KEY",
        "LLM_API_KEY",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_ENDPOINT",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIMENSIONS",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    setup_env()

    assert os.environ["LLM_API_KEY"] == "test-openrouter-key"
    assert os.environ["LLM_PROVIDER"] == "custom"
    assert os.environ["LLM_MODEL"] == "openrouter/deepseek/deepseek-v4-pro"
    assert os.environ["LLM_ENDPOINT"] == "https://openrouter.ai/api/v1"
    assert os.environ["EMBEDDING_PROVIDER"] == "fastembed"
    assert os.environ["EMBEDDING_MODEL"] == "BAAI/bge-small-en-v1.5"
    assert os.environ["EMBEDDING_DIMENSIONS"] == "384"


def test_terminal_parser_allows_supplier_cli_commands_only() -> None:
    args, timeout = parse_terminal_command('supplier-memory-radar ask "What changed after the correction?"')

    assert args == ["ask", "What changed after the correction?"]
    assert timeout == 120

    args, _ = parse_terminal_command("supplier-memory-radar analyze --no-correction")
    assert args == ["analyze", "--no-correction"]

    args, _ = parse_terminal_command("supplier-memory-radar ask What changed after the correction?")
    assert args == ["ask", "What changed after the correction?"]

    with pytest.raises(ValueError):
        parse_terminal_command("cat .env")


def test_dynamic_output_uses_current_documents() -> None:
    proof = build_dynamic_output(file_documents(), generated_at="2026-07-02T00:00:00Z")

    assert proof["scoreBefore"] == 65
    assert proof["scoreAfter"] == 100
    assert proof["riskDelta"] == 35
    assert proof["run"]["source"] == "edited_documents"
    assert proof["verdict"] == "pass"


def test_dynamic_output_changes_when_correction_is_removed() -> None:
    documents = file_documents()
    documents["late_correction"] = ""

    proof = build_dynamic_output(documents, generated_at="2026-07-02T00:00:00Z")

    assert proof["scoreBefore"] == 65
    assert proof["scoreAfter"] == 65
    assert proof["riskDelta"] == 0
    assert proof["verdict"] == "review"


def test_analyze_accepts_real_supplier_files(tmp_path: Path) -> None:
    supplier = tmp_path / "supplier.md"
    policy = tmp_path / "policy.md"
    history = tmp_path / "history.md"
    correction = tmp_path / "correction.md"
    proof_path = tmp_path / "proof.json"

    supplier.write_text(
        "Certificate of incorporation\nGST\nPAN\nBank account verification\n"
        "ISO 9001\nNo sanctions match\nNo adverse media\nFinance names matching\n",
        encoding="utf-8",
    )
    policy.write_text("Escalate unresolved sanctions or contradictory bank evidence.", encoding="utf-8")
    history.write_text("No prior incidents.", encoding="utf-8")
    correction.write_text(
        "Bank verification belongs to the wrong supplier record. "
        "Sanctions review is unresolved for the beneficial owner.",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "--supplier",
            str(supplier),
            "--policy",
            str(policy),
            "--history",
            str(history),
            "--correction",
            str(correction),
            "--output",
            str(proof_path),
        ],
    )

    assert result.exit_code == 0
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["scoreBefore"] == 65
    assert proof["scoreAfter"] == 100
    assert proof["verdict"] == "pass"

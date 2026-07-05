# Supplier Onboarding Risk Agent

Auditable supplier onboarding with UiPath Maestro, Agent Builder, Orchestrator, and Cognee memory.

## Project description

Supplier onboarding is slow, manual, and risk-sensitive. Procurement, finance, and compliance teams need to review supplier documents, missing information, finance risk, policy fit, and escalation needs before a supplier can be safely approved.

This project uses UiPath to model that process as an agentic onboarding workflow. A low-code Agent reviews supplier onboarding risk and returns a structured decision with missing documents, risk summary, and audit notes. UiPath Maestro models the end-to-end business process, while Orchestrator provides execution proof through real job runs.

The local Cognee demo adds persistent supplier memory. It remembers the supplier packet, policy, and vendor history, recalls an onboarding decision, then improves the memory after a late correction supersedes the first clean bank-check note.

## What it solves

- Reduces manual supplier intake review.
- Creates an auditable decision trail.
- Escalates incomplete or risky supplier packets instead of silently approving them.
- Gives procurement and compliance teams a repeatable workflow for supplier approval.
- Shows how supplier memory changes when a late correction contradicts earlier clean evidence.

## UiPath components used

- UiPath Studio Web
- UiPath Maestro BPMN
- UiPath Agent Builder
- UiPath Orchestrator
- Low-code Agent
- Structured JSON output
- Human review / escalation path

## Cognee memory demo

The Typer CLI in `supplier_memory_radar.py` demonstrates the Cognee memory lifecycle:

- `forget`: reset the demo dataset for a repeatable run.
- `remember`: ingest supplier packet, procurement policy, and vendor history.
- `recall`: ask whether the supplier should be approved.
- `remember` with `session_id`: store a late correction in session memory.
- `improve`: start bridging the session correction into the permanent graph.
- `recall`: ask the same supplier decision again and compare the safer answer.

### Local setup

Use Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

Set an OpenRouter key:

```bash
export OPENROUTER_API_KEY="your-openrouter-key"
```

Or create a local `.env` file:

```bash
OPENROUTER_API_KEY="your-openrouter-key"
LLM_PROVIDER="custom"
LLM_MODEL="openrouter/deepseek/deepseek-v4-pro"
LLM_ENDPOINT="https://openrouter.ai/api/v1"
EMBEDDING_PROVIDER="fastembed"
EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS="384"
```

The CLI maps `OPENROUTER_API_KEY` into Cognee's `LLM_API_KEY` at runtime. It uses local FastEmbed embeddings, so no OpenAI key is needed. You can swap `LLM_MODEL` for another OpenRouter model if needed.

### Typer commands

```bash
supplier-memory-radar --help
supplier-memory-radar run --output docs/examples/cognee-memory-output.json
supplier-memory-radar analyze --no-correction
supplier-memory-radar analyze
supplier-memory-radar doctor
supplier-memory-radar ask "Should we approve this supplier?"
supplier-memory-radar ask "What changed after the correction?"
supplier-memory-radar reset
```

The `run` command writes a judge-friendly proof file to `docs/examples/cognee-memory-output.json`. The `doctor` command checks the key, model, Cognee install, sample data, and proof verdict without printing secrets.
Use `ask --no-session` when you want to inspect the original packet-only view.
You can still run the script directly with `python supplier_memory_radar.py ...` if you do not install the command.

For a real supplier packet, point `analyze` at markdown files instead of the bundled sample:

```bash
supplier-memory-radar analyze \
  --supplier /path/to/supplier_packet.md \
  --policy /path/to/procurement_policy.md \
  --history /path/to/vendor_history.md \
  --correction /path/to/late_correction.md
```

Use `--watch` while editing those files to rerun the analysis every few seconds.

### Public web console

Live Railway app:

```text
https://supplier-memory-risk-radar-production.up.railway.app
```

The Railway app serves the product console and the Python API from the same FastAPI service:

- `GET /` opens the supplier memory console.
- `GET /healthz` returns service health.
- `POST /api/terminal` runs allowlisted `supplier-memory-radar` commands and returns stdout, exit code, duration, and proof JSON.
- `POST /api/radar` remains as a small compatibility endpoint for older demos.

The public terminal accepts the same Typer commands as local development. It does not expose a general shell.
For the live proof, click `No correction` first, then `Analyze docs`. The score should move from review to the corrected risk result when the late correction is included.

Run it locally:

```bash
uvicorn web_service:app --host 127.0.0.1 --port 8765
```

Deploy it to Railway from the repo root:

```bash
railway up --new --name supplier-memory-risk-radar
railway domain --port 8080
```

Set these Railway variables before showing the live app:

```bash
OPENROUTER_API_KEY=...
LLM_PROVIDER=custom
LLM_MODEL=openrouter/deepseek/deepseek-v4-pro
LLM_ENDPOINT=https://openrouter.ai/api/v1
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
```

## Agent type

This solution uses a Low-code Agent built with UiPath Agent Builder.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full workflow architecture.

High-level flow:

1. Supplier onboarding request starts.
2. UiPath Maestro BPMN coordinates the onboarding lifecycle.
3. The Agent checks supplier packet completeness and risk.
4. The Agent returns a structured decision:
   - `decision`
   - `missingDocs`
   - `riskSummary`
   - `auditNotes`
5. Risky or incomplete cases are escalated for human review.
6. Approved cases continue to contract, ERP creation, activation, and email notification.
7. UiPath Orchestrator records execution history for demo and audit proof.

## Demo proof

The Agent was run as a real UiPath Orchestrator job.

- Status: Successful
- Duration: 18.709s
- Triggered by: Manual
- Type: Agent
- Package: `Supplier.Onboarding.1.1.1.agent.Agent@1.0.0-debug.63918228395`
- Job key: `4db04955-4999-49e6-9829-48c86a1c82c9`

See [docs/demo-proof.md](docs/demo-proof.md) for the demo script and output.

See [docs/cognee-demo.md](docs/cognee-demo.md) for the Cognee memory demo script.

## Screenshots

Screenshots are stored in [docs/screenshots](docs/screenshots).

## Setup instructions for judges

1. Run the local Cognee memory demo:

   ```bash
   pip install -e .
   export OPENROUTER_API_KEY="your-openrouter-key"
   supplier-memory-radar run --output docs/examples/cognee-memory-output.json
   supplier-memory-radar doctor
   ```

2. Open the UiPath Labs / Studio Web project:

   `https://staging.uipath.com/hackathon26_639/studio_/designer/f5421889-7320-40f0-92fc-9d20cc7df2e7?solutionId=a359ffdf-e91a-4299-ec15-08decdd7b62e&fileId=1fd0aba6-476d-4c9e-a396-251b063c87ef`

3. Open the solution named `Supplier Onboarding`.

4. To run the Agent directly:

   - Go to UiPath Orchestrator.
   - Open the `Supplier Onboarding 1 1 1` folder/process.
   - Start the `Agent` process.
   - Input can be `{}` for the safety/escalation demo.
   - The expected result is a successful job with an `escalate` decision because no supplier packet was provided.

5. To run the BPMN flow:

   - Open `Supplier_Onboarding.bpmn` in Studio Web.
   - Use Debug to run the workflow.
   - Publish the solution after validation if a new version is needed.

## Example output

When no supplier packet data is supplied, the Agent correctly escalates:

```json
{
  "meetsBasicCriteria": false,
  "riskLevelAcceptable": false,
  "decision": "escalate",
  "missingDocs": ["Supplier onboarding packet data not provided"],
  "riskSummary": "Unable to evaluate supplier onboarding packet because no packet contents or documents were supplied in the conversation. Per policy, missing information and unavailable checks require human review.",
  "auditNotes": [
    "No onboarding packet details were provided, so completeness, sanctions/adverse media, finance risk, bank/tax consistency, and document sufficiency could not be assessed.",
    "No external or workflow-based verification tools are available in this session; any required checks remain needs review."
  ]
}
```

## Try it out

- UiPath Studio Web project: `https://staging.uipath.com/hackathon26_639/studio_/designer/f5421889-7320-40f0-92fc-9d20cc7df2e7?solutionId=a359ffdf-e91a-4299-ec15-08decdd7b62e&fileId=1fd0aba6-476d-4c9e-a396-251b063c87ef`
- Demo guide: [docs/demo-proof.md](docs/demo-proof.md)
- Cognee demo guide: [docs/cognee-demo.md](docs/cognee-demo.md)
- Cognee proof output: [docs/examples/cognee-memory-output.json](docs/examples/cognee-memory-output.json)
- Public Railway console: `https://supplier-memory-risk-radar-production.up.railway.app`

## AI assistant disclosure

AI assistance was used to plan and prepare this hackathon submission. The project logic, data files, README, and CLI should be reviewed before final submission.

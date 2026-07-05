# Cognee demo

## What to show

0. Open the public console:

   ```text
   https://supplier-memory-risk-radar-production.up.railway.app
   ```

   Click `No correction`, then `Analyze docs`. This proves the result changes when the late correction is included.

1. Run `supplier-memory-radar --help` to show the Typer CLI.
2. Set your OpenRouter key:

   ```bash
   export OPENROUTER_API_KEY="your-openrouter-key"
   ```

   The default model is `openrouter/deepseek/deepseek-v4-pro`.

3. Run the full memory demo:

   ```bash
   supplier-memory-radar run --output docs/examples/cognee-memory-output.json
   ```

4. Run the fast document analysis:

   ```bash
   supplier-memory-radar analyze --no-correction
   supplier-memory-radar analyze
   ```

5. Check the local demo is ready:

   ```bash
   supplier-memory-radar doctor
   ```

6. Open `docs/examples/cognee-memory-output.json`.
7. Show the before decision, after decision, contradictions, audit trail, and `verdict: pass`.
8. Ask a follow-up:

   ```bash
   supplier-memory-radar ask "What changed after the correction?"
   ```

## Demo story

The first memory pass contains a clean supplier packet, positive low-value vendor history, and procurement policy. The late correction then supersedes the clean bank-check note and marks sanctions review unresolved.

The point of the demo is not that the supplier gets approved. The point is that the system remembers the first decision, accepts a correction, improves persistent memory, and recalls a safer answer with an audit trail.

## Cognee lifecycle shown

- `forget`: clear the demo dataset.
- `remember`: store supplier packet, policy, and vendor history.
- `recall`: produce the first onboarding decision.
- `remember(session_id=...)`: store late correction in session memory.
- `improve`: start bridging the correction into the graph.
- `recall`: produce the corrected supplier decision.

## Expected proof

The proof JSON should contain:

- `run`
- `beforeDecision`
- `afterDecision`
- `memoryEvidence`
- `contradictions`
- `auditTrail`
- `scoreBefore`
- `scoreAfter`
- `riskDelta`
- `demoPassed`
- `verdict`

The corrected decision should be more cautious because the bank verification and sanctions review are no longer clean.

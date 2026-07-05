# Architecture

## Overview

Supplier Onboarding Risk Agent is a UiPath-based workflow for reviewing supplier onboarding requests with an auditable agentic decision trail. A local Cognee memory demo adds before/after supplier risk recall so the project can show how stale or contradictory onboarding facts change the decision.

## Components

| Layer | Component | Role |
| --- | --- | --- |
| User / business process | Procurement and compliance users | Submit or review supplier onboarding requests |
| Process orchestration | UiPath Maestro BPMN | Models intake, screening, risk review, approval, and activation |
| Agentic review | UiPath Agent Builder | Evaluates supplier packet completeness and risk |
| Memory | Cognee local graph-vector memory | Remembers supplier packet, policy, history, and late corrections |
| CLI | Typer | Runs the local Cognee demo and writes proof JSON |
| Execution | UiPath Orchestrator | Runs the Agent and records job history |
| Human governance | Escalation path | Handles missing, risky, or unverifiable supplier data |

## Workflow

```mermaid
flowchart TD
    A[Supplier onboarding request] --> B[Maestro BPMN intake]
    B --> C[AI intake screening]
    C --> D[Agent Builder risk review]
    D --> E{Decision}
    E -->|Approve| F[Contract and ERP creation]
    E -->|Escalate| G[Human review]
    E -->|Reject| H[Stop onboarding]
    F --> I[Supplier activation]
    G --> I
    I --> J[Email notification]
    D --> K[Orchestrator job history and audit trail]
    A --> L[Typer CLI demo]
    L --> M[Cognee remember policy packet history]
    M --> N[Cognee recall decision]
    N --> O[Late correction]
    O --> P[Cognee improve memory]
    P --> Q[Corrected recall and proof JSON]
```

## Agent output contract

The Agent returns structured JSON:

- `meetsBasicCriteria`
- `riskLevelAcceptable`
- `decision`
- `missingDocs`
- `riskSummary`
- `auditNotes`

The Cognee demo writes `docs/examples/cognee-memory-output.json`:

- `beforeDecision`
- `afterDecision`
- `memoryEvidence`
- `contradictions`
- `auditTrail`
- `scoreBefore`
- `scoreAfter`

## Safety behavior

If supplier packet data is missing, the Agent does not invent approval evidence. It returns `decision: "escalate"` with audit notes explaining what could not be verified.

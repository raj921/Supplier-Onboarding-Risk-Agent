# Architecture

## Overview

Supplier Onboarding Risk Agent is a UiPath-based workflow for reviewing supplier onboarding requests with an auditable agentic decision trail.

## Components

| Layer | Component | Role |
| --- | --- | --- |
| User / business process | Procurement and compliance users | Submit or review supplier onboarding requests |
| Process orchestration | UiPath Maestro BPMN | Models intake, screening, risk review, approval, and activation |
| Agentic review | UiPath Agent Builder | Evaluates supplier packet completeness and risk |
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
```

## Agent output contract

The Agent returns structured JSON:

- `meetsBasicCriteria`
- `riskLevelAcceptable`
- `decision`
- `missingDocs`
- `riskSummary`
- `auditNotes`

## Safety behavior

If supplier packet data is missing, the Agent does not invent approval evidence. It returns `decision: "escalate"` with audit notes explaining what could not be verified.


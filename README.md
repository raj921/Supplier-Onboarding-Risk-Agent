# Supplier Onboarding Risk Agent

Auditable supplier onboarding with UiPath Maestro, Agent Builder, and Orchestrator.

## Project description

Supplier onboarding is slow, manual, and risk-sensitive. Procurement, finance, and compliance teams need to review supplier documents, missing information, finance risk, policy fit, and escalation needs before a supplier can be safely approved.

This project uses UiPath to model that process as an agentic onboarding workflow. A low-code Agent reviews supplier onboarding risk and returns a structured decision with missing documents, risk summary, and audit notes. UiPath Maestro models the end-to-end business process, while Orchestrator provides execution proof through real job runs.

## What it solves

- Reduces manual supplier intake review.
- Creates an auditable decision trail.
- Escalates incomplete or risky supplier packets instead of silently approving them.
- Gives procurement and compliance teams a repeatable workflow for supplier approval.

## UiPath components used

- UiPath Studio Web
- UiPath Maestro BPMN
- UiPath Agent Builder
- UiPath Orchestrator
- Low-code Agent
- Structured JSON output
- Human review / escalation path

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

## Screenshots

Screenshots are stored in [docs/screenshots](docs/screenshots).

## Setup instructions for judges

1. Open the UiPath Labs / Studio Web project:

   `https://staging.uipath.com/hackathon26_639/studio_/designer/f5421889-7320-40f0-92fc-9d20cc7df2e7?solutionId=a359ffdf-e91a-4299-ec15-08decdd7b62e&fileId=1fd0aba6-476d-4c9e-a396-251b063c87ef`

2. Open the solution named `Supplier Onboarding`.

3. To run the Agent directly:

   - Go to UiPath Orchestrator.
   - Open the `Supplier Onboarding 1 1 1` folder/process.
   - Start the `Agent` process.
   - Input can be `{}` for the safety/escalation demo.
   - The expected result is a successful job with an `escalate` decision because no supplier packet was provided.

4. To run the BPMN flow:

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


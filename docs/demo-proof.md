# Demo proof

## What to show in the hackathon video

1. Open the UiPath Studio Web project.
2. Show the `Supplier_Onboarding.bpmn` workflow.
3. Show the Agent / Orchestrator process named `Agent`.
4. Start the Agent job from Orchestrator.
5. Use `{}` as input for the safety demo.
6. Show the job result:
   - Status: Successful
   - Decision: `escalate`
   - Missing docs: `Supplier onboarding packet data not provided`
   - Audit notes are present

## Verified Orchestrator job

- Workspace: `raj315920@gmail.com's workspace`
- Folder/process area: `Supplier Onboarding 1 1 1`
- Status: Successful
- Duration: 18.709s
- Triggered: Manual
- Type: Agent
- Source: Manual
- Package: `Supplier.Onboarding.1.1.1.agent.Agent@1.0.0-debug.63918228395`
- Job key: `4db04955-4999-49e6-9829-48c86a1c82c9`

## Why no input is acceptable for demo

The empty input demo proves the Agent has safe failure behavior. With no supplier packet, it refuses to approve and escalates for human review. That is the correct behavior for a compliance-sensitive onboarding workflow.

For a fuller demo, provide a supplier packet JSON with company details, tax details, bank details, document list, and risk indicators.


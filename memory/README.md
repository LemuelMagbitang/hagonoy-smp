# HSMP Project Memory Library

Last updated: 2026-11-13 (Asia/Manila)

This folder is the living project notebook for HSMP: current instructions, subsystem procedures, verified history, decisions, test outcomes, and handoffs.

## Authority and reading order

1. The user's latest explicit instructions and corrections are authoritative.
2. `PROJECT_MEMORY.md` is the concise current-state handoff and records the active phase.
3. Subsystem workflow documents define detailed requirements and safe procedures.
4. `PROJECT_JOURNAL.md` preserves chronological evidence and decisions.
5. Repository source code is the implementation, but a stale branch or legacy script must not override user requirements.

Do not confuse a historical journal entry with current live state. Prefer the latest dated verified checkpoint.

## Documents

- `PROJECT_MEMORY.md` — mission, non-negotiable requirements, canonical paths, current project status, active next step.
- `CORE_UPDATER_WORKFLOW.md` — Paper/Geyser/Floodgate update scope, central artifact cache, active-host detection/routing, push/pull semantics, current updater blocker and verification sequence.
- `DATAPACK_WORKFLOW.md` — separate VanillaTweaks datapack registration, planning, deployment, and runtime verification process.
- `PROJECT_JOURNAL.md` — chronological log of substantive project conversations, corrections, applied patches, test outcomes, incidents, and decisions.
- `../docs/RECOVERY-CHECKLIST.md` — recovery reference.

## Maintenance rules

For each substantive HSMP conversation/session:
- Update `PROJECT_MEMORY.md` when active priority, state, instructions, paths, verified results, or next action changes.
- Update the relevant workflow document when a design rule or implementation status changes.
- Append a dated journal entry with the user's direction, exact verified outcome, files touched, test results, live-server impact, and next action.
- Mark old status entries as historical/superseded rather than leaving them appearing current.
- Remove obsolete operational instructions when no longer needed, but preserve useful verified history in the journal.
- Keep proposed, applied, tested, committed, pushed, deployed, and live-verified states distinct.
- Never record secrets.
- Memory/documentation commits do not imply approval to commit or push server-manager source-code changes.

# Framework Knowledge Placement

Shared reference for where durable framework knowledge belongs. This file captures the phase-1 placement contract from spec-116 so later cleanup tasks promote rules into the right governed surface instead of copying them across lessons, contexts, overlays, and generated mirrors.

## 30-Second Decision Flow

Most contributors only need to answer three questions:

1. **Is this a hard rule the framework MUST enforce across IDEs?** → `CONSTITUTION.md`
2. **Is this a design decision for one delivery (with rationale)?** → the approved spec Markdown `## Decisions`; rebuild its query projection with `ai-eng decision backfill`.
3. **Is this an accepted risk with lifecycle metadata?** → `.ai-engineering/state/decision-store.json`.
4. **Anything else heuristic, observed, or tentative?** → `.ai-engineering/LESSONS.md` (auto-funnels into `observations/observations.yml` from observations)

Skill / agent / manifest entries follow the matrix below; those are schema homes, not knowledge homes.

> **`memory.db` is read-side only.** It is a retrieval index over the surfaces above (episodes + knowledge objects ingested from `LESSONS.md`, `decision-store.json`, instincts). It is **never** the canonical home for a new rule. `/ai-dream` proposes promotions in `instincts/memory-proposals.md`; humans curate from there.

## Worked Examples

| Concrete rule | Canonical home |
|---|---|
| "Article V — every concept has one canonical source of truth" | `CONSTITUTION.md` |
| "D-003-05 — use progressive hybrid review" | the `## Decisions` section of the approved/archived spec |
| "Accept a finding until a fixed expiry date" | `decision-store.json` |
| "gitleaks 8.x flag for staged files is `protect --staged`, not `detect --no-git --staged-only`" | `LESSONS.md` |
| "After third user correction, propose a recovery instinct" | `observations/observations.yml` (auto-funnel) |
| "Cross-IDE plan-mode default" | `CONSTITUTION.md` Article XI |
| "Skill X triggers on prompt Y, runs script Z" | the skill's own `SKILL.md` |
| "Skills live under `.claude/skills/ai-<name>/SKILL.md`" | `.ai-engineering/manifest.yml` (`framework_state.skills`) |
| "Python style: prefer guard clauses over nested ifs" | `.ai-engineering/overrides/python/conventions.md` |

## Placement Matrix

| Knowledge class | Canonical home | Use this home when | Retain elsewhere when |
|---|---|---|---|
| Skill contracts | Canonical `SKILL.md` for the relevant skill | The rule changes trigger conditions, procedure, inputs, outputs, or tool expectations for one skill | The rule is cross-skill guidance, temporary discovery, or team-local policy |
| Agent orchestration | The relevant agent definition | The rule changes delegation, boundaries, handoffs, review order, write scope, or execution mode for one agent | The rule is a user-facing workflow contract or reusable framework guidance |
| Machine-readable metadata | `.ai-engineering/manifest.yml` | The content is structured, bounded, and consumed by validators, sync, install, hooks, or runtime logic | The content is explanatory prose, rationale, or operator guidance |
| Cross-IDE governance rules | `AGENTS.md` or the relevant framework-owned root entry-point overlay | The rule governs root startup, host-specific behavior, mirror expectations, or the cross-IDE operating contract | The rule is reusable framework guidance or a mirror-path detail that does not need separate governance |
| Reusable framework guidance | Shared root context under `.ai-engineering/contexts/` | The rule is durable across multiple skills, agents, or IDE surfaces and is best read as guidance rather than schema | The rule is team-specific or belongs in Constitution-level hard rules |
| Learning funnel artifacts | `.ai-engineering/LESSONS.md`, `.ai-engineering/observations/observations.yml`, `.ai-engineering/observations/proposals.md` | The content is newly observed, heuristic, disputed, incomplete, or waiting for a better governed home | The rule has become repeatable and a canonical surface can own it |
| Delivery design decisions | Approved/archived spec Markdown `## Decisions` | The decision defines product or architecture behavior for a spec and needs rationale beside its requirements | `decision-store.json` is a rebuildable query projection populated by `ai-eng decision backfill` |
| Risk records | `.ai-engineering/state/decision-store.json` | An active or accepted risk needs finding identity, expiry, renewal and remediation lifecycle metadata | The content is a design decision already owned by a spec, a solved note or a temporary finding |
| Team-local conventions | `.ai-engineering/contexts/team/**` | The rule is project-specific, organization-specific, or intentionally overrides framework defaults | The rule generalizes across repositories and should move to a framework-owned surface |

## Decision Rules

- Place by enforcement target, not by where the rule was first discovered.
- Use one neutral canonical home. Generated mirrors, copied templates, and IDE-specific projections are distribution surfaces, not separate knowledge classes.
- Do not promote mirror-source drift into this matrix. If root-surface ownership is already governed elsewhere, reference that contract instead of creating a second source-of-truth rule here.
- Apply [the persistence doctrine](../../docs/persistence-doctrine.md) whenever a datum has a derived cache or projection; every derivative needs an explicit rebuild command.

## Promotion Test

Move a finding out of `.ai-engineering/LESSONS.md`, `.ai-engineering/observations/observations.yml`, or `.ai-engineering/observations/proposals.md` only when all of these are true:

1. The pattern repeated across more than one task, review, or framework surface.
2. A governed canonical home can own or validate it today.
3. Leaving it in the funnel would force future work to guess where the rule belongs.

Retain the finding in the funnel when any condition fails. Drop it instead of promoting it when it is obsolete, superseded, or already covered by an existing canonical rule.

## Governance Notes

- Rationale: give spec-116 a single placement contract before cleanup moves content.
- Expected gain: later tasks can classify rules consistently and avoid recreating mirror or ownership drift.
- Potential impact: future promotion, cleanup, and metadata tasks should use this matrix before moving content between governed surfaces.

---
id: archflow
name: archflow
description: |
  Show all available archflow skills and recommended workflows.
  Use "/archflow" to see the full skills list.

  Triggers: archflow, archflow help, archflow skills, 아크플로우
user-invocable: true
version: 2.0.0
triggers:
  - "archflow"
  - "archflow help"
  - "archflow skills"
requires: []
recommended_model: sonnet
allowed-tools: []
---

# Archflow Skills

> **Language**: Detect the user's language from their message or system locale. Translate all labels, descriptions, and section headers below into that language. Keep skill command names (e.g., `/spec`, `/arch`) and file paths as-is.

Display the following help message (translate to user's language):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 archflow - The Design Compiler v2.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 Core Pipeline (Feature Development)
  /spec                    Transform materials into spec.md
  /arch                    Multi-agent debate → arch-be/fe.md
  /ui                      Generate UI spec from API endpoints
  /check                   Verify design completeness
  /pre-build               Verify environment readiness
  /build                   Automated implementation from design
  /test                    Generate and/or run tests

🐛 Bugfix & Maintenance
  /debug                   Systematic bug fixing
  /trace                   Record changes to trace.md
  /sync                    Sync design-impacting changes to arch.md

📚 Document Management
  /reinforce               Add requirements or fill documentation gaps
  /reverse                 Reverse-engineer docs from existing code
  /overview                Generate 1-page project overview

🚢 Deployment
  /runbook                 Generate deployment documentation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Document Structure:
   docs/{serviceName}/
   ├── spec.md              # from /spec
   ├── arch-be.md           # from /arch (Backend)
   ├── ui.md                # from /ui
   ├── arch-fe.md           # from /arch (Frontend)
   ├── trace.md             # from /trace
   ├── overview.md          # from /overview
   └── runbook.md           # from /runbook

💡 Recommended Flow:
   Feature BE:   /spec → /arch → /check → /pre-build → /build → /test
   Feature FE:   /spec → /arch(BE) → /check → /ui → /arch(FE) → /check → /pre-build → /build → /test
   Bugfix:       /debug → /trace → /sync
   Enhancement:  /reinforce → /arch → /check → /pre-build → /build → /test
   Legacy:       /reverse → /reinforce (optional) → /check

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

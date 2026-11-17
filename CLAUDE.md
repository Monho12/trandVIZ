# trandVIZ

## Agent skills

Matt Pocock's skills (github.com/mattpocock/skills) are vendored in `.claude/skills/`.

### Issue tracker

Issues are tracked in GitHub Issues for `Monho12/trandVIZ`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root, created as needed. See `docs/agents/domain.md`.

### UI work

Use only `impeccable`, `emil-design-eng`, `dataviz` and `prototype` for UI/UX. Never use `frontend-design` or `design-taste-frontend`. If one is missing, say so; do not substitute. No design change reaches code until Mike picks a prototype. See `docs/adr/0023`, `docs/adr/0025`.

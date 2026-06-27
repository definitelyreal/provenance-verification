---
# Copy this file to user.local.md (same dir), fill it in, set customized: true.
# user.local.md is gitignored — never committed. It EXTENDS claude/RULES.md, it does
# not replace it, so you keep receiving standard updates while your overrides survive.
customized: false
verifier_name: ""          # used in `verified <name> <date>`
surfaces: []               # mediums you use, e.g. [markdown, google-sheets, google-docs, slack]
enforce_paths: []          # globs where the marker hook nags, e.g. ["~/Code/**/*.md"]. Empty = silent.
enforce_mode: warn         # warn | block
do_not_autoresolve: []     # pairs the gate must never auto-merge, e.g. ["HDL/LDL", "Free/Total T4"]
adapters: []               # pointers to co-located project adapters, e.g. ["~/Code/foo/.provenance/adapter.md"]
auto_update: notify        # notify | off  (never silent-pulls executable code)
backfill_renames: ask      # ask | never | auto-safe  (rename .md -> .ai.md during backfill?)
sheets_provenance: column  # column (:Provenance companion) | other  (asked & recorded on first sheets run)
---

# Personal overrides

Put only your deltas below this line. Anything here extends the standard for your setup.

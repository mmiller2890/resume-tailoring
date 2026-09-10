# resume-tailoring

Evidence-gated resume tailoring for AI agents: DOCX text edits with zero format drift, deterministic PDF rendering, and a hard delivery gate that runs real ATS checks before any file ships.

An [agentskills.io](https://agentskills.io)-format skill. Any harness that reads `SKILL.md` can use it.

## What it guarantees

- The master template is never modified - every tailoring writes a fresh copy
- Only text runs (`w:t`) change; styles, numbering, and headers stay byte-identical (enforced by `verify-format`)
- Non-ASCII is rejected up front - em dashes, smart quotes, and ellipses are what ATS parsers mangle
- Nothing is delivered until `verify_output.py` passes every gate: ATS audit, format preservation, keyword coverage, PDF text layer, page limit
- Every application is recorded in an append-only JSONL ledger

## Install

```bash
git clone https://github.com/mmiller2890/resume-tailoring.git
cd resume-tailoring
bash install.sh
```

`install.sh` symlinks this repo into every harness it finds, idempotently:

| Harness | Skill location |
|---|---|
| pi | `~/.pi/agent/skills` |
| Claude Code | `~/.claude/skills` |
| Codex / Copilot CLI / Gemini CLI | `~/.agents/skills` |
| Hermes | `~/.hermes/plugins` |

Restart each harness afterwards so its skill catalog picks it up.

## Configure

```bash
mkdir -p ~/.config/resume-tailoring
cp config.example.json ~/.config/resume-tailoring/config.json
# edit config.json: corpus, template, memory, ledger, owner_name, max_pages
python3 scripts/docx_toolkit.py config   # must pass before tailoring
```

Paths must be absolute - the toolkit does not expand `~` inside config values. Set `$RESUME_TAILORING_CONFIG` to use an alternate config location.

## Your data stays local

The resume corpus, master template, `RESUME.md` memory, and ledger are **never part of this repo**. They live wherever your config points. Nothing personal is committed.

## Dependencies

- python3 + `lxml`
- LibreOffice headless (primary PDF render; `weasyprint` + `mammoth` fallback)
- Swift toolchain (Vision OCR for JD screenshots, PDFKit page checks)
- macOS (`textutil`, PDFKit, Vision); Microsoft Word optional for gold-standard manual PDF export

## Pipeline

1. `python3 scripts/docx_toolkit.py config` - resolve paths
2. `python3 scripts/docx_toolkit.py extract <template.docx>` - numbered paragraph map
3. Build `edits.json` from the JD (see `SKILL.md` and `references/tailoring-playbook.md`)
4. `python3 scripts/docx_toolkit.py apply <template.docx> edits.json <out.docx> --dry-run`, then without `--dry-run`
5. `bash scripts/render_pdf.sh <out.docx> <out.pdf>`
6. `python3 scripts/verify_output.py <out.docx> <keywords.txt> --pdf <out.pdf> --json` - exit 0 or it does not ship
7. `python3 scripts/ledger.py append ...` - record the application

## Smoke test

```bash
bash scripts/smoke_test.sh   # 13 regression tests; requires a valid config
```

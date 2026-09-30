# resume-tailoring

Evidence-based resume tailoring for **any profession or industry** – accounting,
nursing, marketing, teaching, trades, hospitality, research, IT, and more.
An AI agent maps a job description to the candidate's confirmed experience,
edits their own compatible Word template, and delivers checked DOCX/PDF files.
It does not assume the candidate works in IT or uses AI.

An [agentskills.io](https://agentskills.io)-format skill. Any harness that reads
`SKILL.md` can use the instructions.

## What it does

- Chooses emphasis from the target role, seniority, candidate facts, and application rules
- Preserves actual history; never invents duties, metrics, credentials, or proficiency
- Keeps the master template read-only; edits produce a fresh copy
- Preserves all DOCX archive parts except `word/document.xml` byte-for-byte
- Requires content review and ATS-oriented structural, keyword, PDF-text, and page checks
- Uses a configurable page limit – two pages is a default, not a rule for every role or CV
- Records delivered versions in a local append-only ledger; submission is a separate status

The checks reduce known parsing risks. They do not guarantee every ATS vendor's
behavior, ranking, or the candidate's eligibility.

## Install

```bash
git clone https://github.com/mmiller2890/resume-tailoring.git
cd resume-tailoring
bash install.sh
```

`install.sh` idempotently links this repo into harness locations it finds:

| Harness | Skill location |
| --- | --- |
| pi | `~/.pi/agent/skills` |
| Claude Code | `~/.claude/skills` |
| Codex / Copilot CLI / Gemini CLI | `~/.agents/skills` |
| Hermes | `~/.hermes/plugins` |

Restart each harness to refresh its skill catalog. Installation does not upload
candidate files or configure a resume automatically.

## Configure for any candidate

Supply a compatible master DOCX, a local `RESUME.md` containing confirmed facts,
and an output folder. No bundled real resume or particular career is required.

```bash
mkdir -p ~/.config/resume-tailoring
cp config.example.json ~/.config/resume-tailoring/config.json
# set absolute corpus/template/memory/ledger paths, owner_name, and max_pages
python3 scripts/docx_toolkit.py config
```

Paths must be absolute; `~` is not expanded inside config values. Set
`$RESUME_TAILORING_CONFIG` to use another candidate or alternate location.
Confirm `max_pages` from the application and candidate's needs; the example's
value of 2 can be changed for a one-page resume or a longer CV.

In `RESUME.md`, distinguish confirmed history, achievements, competencies,
credentials and status, prior variants, decisions, and unanswered questions.
Do not infer specific duties from a title or employer. AI/automation is optional
and belongs only where relevant and evidenced.

## Supported templates and runtime

Profession-neutral does **not** mean every DOCX layout is supported:

- Plain, single-column English/ASCII text; no tables, text boxes, or contact details in headers
- Standard Summary, Experience, Skills, and Education headings; extra sections such as Licenses, Publications, Projects, or Awards are allowed
- `set_text` edits one-text-run paragraphs; category/title lines use two text runs
- Bullet cloning requires explicit paragraph numbering and one text run; indices come from extraction, not a fixed template
- Current employment-date checks recognize two-run title/date rows using `Month YYYY - Month YYYY` or `Month YYYY - Present`
- Non-ASCII text is rejected by the existing audit/edit policy; do not silently transliterate names or qualifications

Run `extract` and `audit` on the candidate's actual template first. If layout or
run structure is incompatible, request an approved compatible master; never
silently change the formatting. A portfolio, application form, or mandated CV
format may require a different workflow.

Dependencies:

- Python 3 + `lxml`
- LibreOffice headless for PDF rendering; `weasyprint` + `mammoth` as an approximate fallback
- macOS and Swift with Vision/PDFKit for bundled OCR and PDF delivery checks
- Microsoft Word optional for manual PDF export

The skill format works across harnesses. The bundled full PDF/OCR pipeline is
currently macOS-specific; Linux/Windows support is not claimed.

## Pipeline

1. Resolve config; read candidate facts and application requirements.
2. Extract and audit the actual template; archive the verbatim JD locally.
3. Map requirements to evidence, transferable skills, or acknowledged gaps.
4. Draft edits using `SKILL.md` and `references/tailoring-playbook.md`.
5. Preview with `apply --dry-run`, then apply to a new DOCX.
6. Render the PDF and run `verify_output.py ... --pdf ... --json`.
7. Review factual accuracy; require all five delivery gates; record the delivered version.

Do not add unsupported claims to reach keyword coverage. Explicitly acknowledged
missing terms can be reported using `--allow-missing`; missing licenses or other
mandatory qualifications remain substantive gaps. Without `--pdf`, the gate
only checks the DOCX and is not full delivery verification.

## Tests

```bash
bash scripts/smoke_test.sh          # synthetic mechanics + public-guidance checks
bash scripts/smoke_test.sh --pdf    # also render/gate all five fictional career cases
```

Tests create temporary resumes/configs and never read your personal corpus.
The five sample careers (accounting, nursing, marketing, teaching, and IT) are
**test examples, not an exhaustive list or an occupation whitelist**. Tailoring
works from the supplied JD and candidate evidence for any profession, including
ones not named here. Tests also cover different paragraph positions and numbering;
archive/source preservation; invalid edits; parse-risk checks; reported keyword
gaps; and configured page limits.
`evals/evals.json` adds explicit candidate/JD prompts for agent behavior reviews.

## Privacy

Only reusable skill instructions, tools, and fictional tests belong here. Keep
real resumes, contact details, experience memory, outputs, and ledger entries
outside this public repository. `config.json` is ignored. Bundled scripts store
artifacts locally and do not upload candidate data. An AI harness may send text
it reads to its model provider; that harness/provider's privacy and retention
settings still apply. Local files and repository exclusion do not guarantee
end-to-end local AI processing.

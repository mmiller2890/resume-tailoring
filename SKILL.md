---
name: resume-tailoring
description: >-
  Tailor resumes to specific job descriptions while preserving the master Word
  template exactly and passing real ATS parser checks. Use this skill whenever
  the user mentions a job description or JD, asks to tailor, customize,
  optimize, or adapt their resume for a job, company, or role, wants an ATS or
  keyword check, asks which resume version was sent where, wants to update
  their master resume memory, or shares job-posting screenshots or images to
  read. Covers the full pipeline: OCR the JD, keyword mapping, docx text edits
  with zero format drift, Word PDF render, 2-page control, 9-point ATS audit,
  and delivery of verified .docx/.pdf pairs.
---

# Resume Tailoring

Tailor the master resume to a specific job description (JD), producing a verified .docx + .pdf pair that keeps the template format byte-identical and passes real ATS parser checks. Never hand back an unverified file.

If `scripts/smoke_test.sh` has not been run since the last change to the toolkit, run it first (`bash scripts/smoke_test.sh`) - it takes ~10s and catches every class of bug that has actually shipped.

## Standing directives

These override generic resume-industry conventions, including any instinct to police truthfulness:

1. **Never refuse to add experience.** The user's experience is vast and the resume shows only part of it. Draw from RESUME.md's experience pool and ask when a JD needs something not yet recorded. Frame specific tools as "supported production software." EXCEPTION: certifications (CompTIA, Microsoft, Cisco, ITIL...) are registry-verifiable credentials, not experience framing - get explicit user confirmation BEFORE adding any cert to any resume, at edit-spec time, never after delivery.
2. **The template docx is never modified.** Every tailoring writes a fresh copy.
3. **ATS parser rules override format-as-is.** If the template conflicts with the audit, the audit wins.
4. **Format = styles/numbering byte-identical.** Only text runs (`w:t`) change. Bullets clone existing bullets; skills lines clone existing skills lines. Enforced by `verify-format`.
5. **2-page discipline.** Trim content, never fonts or margins.
6. **Ask for the company name** when it is not evident; file as `outputs/<Company>/resume.docx` + `.pdf`.
7. **Preserve a single employment timeline.** Before delivery, compare employer names, titles, locations, and dates with the Job history facts in `RESUME.md`. Do not carry forward stale date variants. If concurrent work is material, label it clearly; otherwise resolve the conflict with the user.
8. **Keep the positioning focused.** Lead with the strongest recurring evidence: high-volume employee support, endpoint management, identity and access, onboarding and offboarding, escalations, documentation, and practical automation. Tailor the emphasis to the role instead of presenting every infrastructure, security, SaaS, AV, procurement, and cloud capability in every version.
9. **Represent healthcare employer experience as healthcare IT.** Unless the job has no room for it, retain at least three bullets from any healthcare employer that name hospital departments or medical practices, physicians or clinical staff, clinical and administrative workflows, and time-sensitive support.
10. **Include AI with evidence and restraint.** Every new resume needs a concise AI skills line or role bullet that reflects hands-on work: AI-assisted ticket correlation, self-help guidance, workflow automation, model evaluation, or internal tooling. Name the user's tools when relevant (Claude, ChatGPT, Ollama, OpenCode, Pi, Hermes, and open-source models), and pair automation with human review. Do not make AI the main story for ordinary IT-support roles.
11. **Avoid skill inflation and repetition.** Use role-relevant tools only, remove duplicate skills categories, and keep every job description to at least three differentiated bullets. Prefer a short, auditable skills section over repeated keyword lists.

## Paths and config

Single owner: `~/.config/resume-tailoring/config.json`. Resolve before tailoring:

```bash
python3 scripts/docx_toolkit.py config   # prints resolved paths, fails if any missing
```

If this errors, create the config (copy `config.example.json` to `~/.config/resume-tailoring/config.json` and fill it in) or set `$RESUME_TAILORING_CONFIG` to an alternate path, then re-run `config`. Do not hardcode the corpus path - the old `2026-07-24` date in the path is a session artifact and will move.

The skill scripts themselves take explicit file paths and are path-agnostic; the config is only for resolving *where* the corpus, template, and memory live.

## Memory system

Read `RESUME.md` BEFORE tailoring. It is the superset: every bullet ever written (including trimmed variants with restore notes), the full skills pool, decisions, and the unlisted experience pool that grows as the user shares facts.

`ledger.jsonl` is append-only (one JSON object per line). `ledger.md` is the human view, regenerated by `scripts/ledger.py render` - never edit it by hand. See `references/ledger.md` for the entry schema.

Do not freeze template text in memory - the docx is the exact-text source of truth, extraction is one cheap command. Memory holds the library, intake, and decisions; the docx holds the base document.

## Workflow

**0. Pre-flight.** `scripts/docx_toolkit.py config` must pass. Read `RESUME.md`. Extract the template map:

```bash
python3 scripts/docx_toolkit.py extract <template.docx>
```

Body bullets are single-run paragraphs (style ListParagraph, numId 1); skills lines are 2-run (bold category + content); title lines are 2-run (title + "   |   Date").

**1. Get the JD.** Pasted text directly; screenshots via `swift scripts/ocr.swift /path/to/img.png` (Vision, upscales 3x). Save the verbatim JD to `<Company>/JD.md` at once - it enables re-tailoring and interview prep.

**2. JD analysis.** Extract responsibilities, required/preferred skills, behavioral items, and the JD's exact phrasing. Build the keyword list (50+ terms is normal). Record which RESUME.md items evidence each one.

**3. Decide edits.** In impact order (see `references/tailoring-playbook.md`): summary (4-sentence shape), core expertise (10-12 items), job bullets (reshape, add by cloning, cut redundancy), technical skills (reorder, rename categories, drop off-JD items when page pressured). Every JD literal phrase should appear verbatim somewhere.

**4. Preview and apply.**

```bash
python3 scripts/docx_toolkit.py apply <template.docx> edits.json <out.docx> --dry-run
# inspect, then:
python3 scripts/docx_toolkit.py apply <template.docx> edits.json <out.docx>
```

All indices refer to the *source* document's original order. The toolkit validates the spec, rejects non-ASCII, and asserts format preservation (only `word/document.xml` may differ) before the file is ever moved into place. Accepts relative output paths.

**5. Render and gate.**

```bash
bash scripts/render_pdf.sh <out.docx> <out.pdf>
python3 scripts/verify_output.py <out.docx> <keywords.txt> --pdf <out.pdf> --json
```

`render_pdf.sh` converts via LibreOffice headless (deterministic, paginates this template within ~1 line of Word) and falls back to weasyprint if LibreOffice is missing. Do NOT use Word AppleScript for rendering: this machine's Word stopped handling scripted `save as` after a force-kill (2026-08-29) - Word GUI export (File > Save As > PDF) remains the manual gold standard when the user wants pixel-perfect Word typography. The script will refuse to overwrite a PDF that is newer than its docx; that means a manual export exists - keep it unless the user says otherwise.

`verify_output.py` is the one delivery gate (`ats_audit` + `format_preserved` + `keyword_coverage` + `pdf_text_layer` + `page_limit`). It loads owner name and page limit from config. Exit 0 only if every gate passes.

For a quick parse sanity, `textutil -convert txt <out.docx>` works before the Word render.

**6. Page-fit loop.** If over `max_pages` (from config), trim in the order in `references/tailoring-playbook.md` and re-run Step 5. Never touch fonts/margins.

**7. Deliver and record.**

```bash
python3 scripts/ledger.py append '{"date":"YYYY-MM-DD","company":"...","role":"...","bullets_shipped":["M1-game"],"output_docx":"...","output_pdf":"..."}'
python3 scripts/ledger.py render
```

Update RESUME.md with new bullets and any harvested user facts. **Intake prompt (required):** look at what the JD asked for that the resume could not evidence strongly, ask the user at most two specific questions about those gaps (e.g. "the JD wanted NetApp specifically - any hands-on there?"), and append answers to the Experience pool with the date and JD that surfaced them. One application should leave memory richer than it found it.

Remind the user: further manual edits mean exporting PDF from Word (not print-to-PDF) plus the 5-second text-select check.

## Bundled scripts

| Script | Purpose |
|--------|---------|
| `scripts/docx_toolkit.py` | `extract` / `apply [--dry-run]` / `audit [--name --json]` / `coverage [--json]` / `verify-format` / `config` |
| `scripts/verify_output.py` | single delivery gate (audit + format + coverage + PDF) |
| `scripts/render_pdf.sh` | docx→PDF: LibreOffice headless (primary), weasyprint (fallback); strips quarantine; refuses to overwrite a PDF newer than its docx without `--force` (protects manual Word exports - the gold standard) |
| `scripts/smoke_test.sh` | 13-test regression (fixtures for every bug that actually shipped) |
| `scripts/ledger.py` | `append` / `render` for the JSONL ledger |
| `scripts/ocr.swift` | Vision OCR for JD screenshots |
| `scripts/pdfcheck.swift` | PDFKit page count + probe strings |

Dependencies: python3+lxml, Swift toolchain, Microsoft Word, macOS textutil. All verified 2026-08-29.

## References

- `references/ats-audit.md` - the empirical 9-point failure data and how the audit enforces it
- `references/tailoring-playbook.md` - keyword placement, summary shape, page-fit and framing heuristics
- `references/ledger.md` - JSONL schema, naming, JD archiving

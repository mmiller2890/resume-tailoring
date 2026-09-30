---
name: resume-tailoring
description: >-
  Use when tailoring, customizing, or checking a resume or CV for a job in any
  profession or industry, analyzing a job description or posting screenshot,
  checking ATS readability or keyword coverage, updating resume experience
  memory, or tracking which version was delivered. Produces verified DOCX/PDF
  pairs from the candidate's own compatible Word template, with preserved
  formatting, evidence-based content, and a configurable page limit.
---

# Resume Tailoring

Tailor a candidate's resume to a target role in **any profession**. Derive the
positioning from their confirmed experience and the job description (JD), not
from a default occupation. The same workflow applies to accounting, nursing,
marketing, teaching, trades, hospitality, research, IT, and other fields.
There is no occupation whitelist: use the supplied JD and evidence even when
the profession is not named in this skill or its sample tests.

Use the candidate's compatible DOCX template and local configuration. Never
ship an unverified file. Run `bash scripts/smoke_test.sh` after toolkit changes;
tests use fictional resumes and do not need personal configuration.

## Standing directives

1. **Use evidence, not assumptions.** Do not invent experience, duties, tools,
   achievements, metrics, education, certifications, licenses, or clearance.
   The resume may omit real experience: consult `RESUME.md` and ask about gaps.
   An employer, job title, or tool name alone does not confirm specific duties
   or proficiency. Record the user's answer, not inferred subskills.
2. **Keep the template read-only.** Write a fresh output. All DOCX archive parts
   except `word/document.xml` must remain byte-identical. Preserve paragraph
   and run formatting; clone compatible bullets or category lines when needed.
3. **Preserve career facts.** Compare names, employers, actual titles, locations,
   dates, education, and credential status with confirmed history. Do not turn
   clinical care into healthcare IT, creative software use into software support,
   or overlapping employment into invented sequential dates. Resolve conflicts.
4. **Choose role-relevant evidence.** Lead with the target role's responsibilities,
   outcomes, and competencies at the candidate's actual seniority. Respect each
   profession's vocabulary. Mention tools only at the demonstrated level of use.
   Career changers can foreground transferable skills without claiming prior
   employment in the new profession.
5. **Confirm credentials explicitly.** Include certifications, professional
   licenses, registrations, degrees, and clearance only when supported by the
   candidate's records or explicit confirmation. Do not imply a credential is
   active, a jurisdiction applies, or a requirement is met without evidence.
6. **AI is optional.** Include AI or automation only when both relevant to the JD
   and supported by confirmed hands-on experience. Do not add an AI line, product
   list, or automation claim to every resume. Describe oversight where material.
7. **Use the configured length.** `max_pages` is the delivery limit, not a fixed
   two-page rule. Confirm an appropriate limit for the candidate and application;
   an academic CV or application-specific format may need a different length.
   Trim content, never shrink fonts or margins to squeeze it in.
8. **Avoid padding and keyword stuffing.** Summary length, competency count, and
   bullets per role depend on evidence and available space. No mandatory minimum
   of three bullets. Retain licenses, projects, publications, portfolios, or other
   sections when relevant and present in the template. Do not add unsupported JD
   phrases merely to reach full coverage.
9. **Require both readability and preservation.** Audit the source template first.
   If it fails and text-only edits cannot fix it, explain the conflict and request
   an approved compatible template. Do not quietly alter layout or bypass gates.
10. **Keep candidate data local.** No resumes, personal facts, ledger entries, or
    real contact information belong in this public skill repository.

## Paths and config

Resolve local paths before tailoring:

```bash
python3 scripts/docx_toolkit.py config
```

If missing, copy `config.example.json` to
`~/.config/resume-tailoring/config.json` and fill in absolute paths, `owner_name`,
and `max_pages`. Set `$RESUME_TAILORING_CONFIG` for another candidate or location.
The scripts accept explicit paths; no occupation or owner is built into them.

Read `RESUME.md` for confirmed history, the full experience and competency pool,
bullet variants, and tailoring decisions. If it is missing, create it locally
from the candidate's supplied resume and answers; distinguish confirmed facts
from unanswered questions. The DOCX is the exact-text source, not the memory.

`ledger.jsonl` is append-only. Regenerate `ledger.md` with `scripts/ledger.py render`;
never edit the rendered view. See `references/ledger.md`.

## Workflow

**0. Pre-flight.** Resolve config, read candidate memory, and confirm the target
field, seniority, application instructions, and configured page limit. Extract
and audit the actual source template:

```bash
python3 scripts/docx_toolkit.py extract <template.docx>
python3 scripts/docx_toolkit.py audit <template.docx> --name "Full Name" --json
```

Use the extracted indices, styles, numbering, and run counts. Never reuse another
candidate's paragraph positions. `set_text` and cloned bullets require one text
run; category lines require two. Bullet clones require explicit `numPr`; no fixed
style name or numbering ID is assumed. Unsupported run structures need a compatible
template, not forced edits. The current audit expects standard Summary, Experience,
Skills, and Education headings; additional profession-specific sections are allowed.
These English/ASCII and template constraints are detailed in `README.md`.

**1. Get the JD.** Accept text, a provided posting, or screenshots. On macOS,
`swift scripts/ocr.swift <image>` extracts screenshots. Re-check OCR names,
credentials, and unusual tokens. Ask for the company and role if unclear; save
the verbatim JD to `outputs/<Company>/JD.md`. Use separate role folders if needed.

**2. Map requirements to evidence.** Extract responsibilities, required/preferred
qualifications, competencies, credentials, and exact terminology. Map each to a
confirmed fact, transferable evidence, or an unanswered/acknowledged gap. Keep a
focused comma-separated keyword list; there is no required keyword count. A duty
or outcome matters even when it is not a software skill.

**3. Decide edits.** Follow `references/tailoring-playbook.md`: relevant summary,
competencies if present, evidence-rich experience bullets, and relevant skills or
qualifications. Use exact JD wording where it describes confirmed experience.
Do not rewrite actual historical titles to impersonate the target role.

**4. Preview and apply.** All indices refer to the original source order:

```bash
python3 scripts/docx_toolkit.py apply <template.docx> edits.json <out.docx> --dry-run
# inspect the preview, then:
python3 scripts/docx_toolkit.py apply <template.docx> edits.json <out.docx>
```

The toolkit validates run shapes and edit conflicts, rejects non-ASCII supplied
text, and checks archive preservation before publishing the output file.

**5. Render and gate.** Independently compare edited content with candidate facts;
the mechanical checks do not establish truthfulness or qualification for a job.

```bash
bash scripts/render_pdf.sh <out.docx> <out.pdf>
python3 scripts/verify_output.py <out.docx> <keywords.txt> --pdf <out.pdf> --json
```

Always provide `--pdf` for delivery. Confirm **all five gates** are present and
pass: `ats_audit`, `format_preserved`, `keyword_coverage`, `pdf_text_layer`, and
`page_limit`. Config must supply the source `template`, `owner_name`, and
`max_pages`. A DOCX-only check is useful during drafting, not full verification.
These are structural ATS-oriented checks, not a guarantee about every ATS vendor.

If a requested JD term is genuinely unsupported, report the gap. With the user's
acknowledgment, `--allow-missing "term one, term two"` can exempt those terms while
still reporting them. Never fabricate a claim or silently drop a requirement to
make coverage pass. Credential gaps are not fixed by wording or exemptions.

**6. Page-fit.** If over the configured limit, trim using the playbook, then render
and re-gate. LibreOffice is the primary renderer; the weasyprint fallback has
approximate layout. Judge page count from the rendered PDF, not character count.
Never overwrite a newer manual PDF export without permission (`--force`).

**7. Deliver and record.** Deliver `outputs/<Company>/resume.docx` and `.pdf` only
after content review and all gates pass. Explain relevant changes and unmet
requirements without promising eligibility or ATS ranking.

```bash
python3 scripts/ledger.py append '{"date":"YYYY-MM-DD","company":"...","role":"...","bullets_shipped":["role1-bullet2"],"output_docx":"...","output_pdf":"..."}'
python3 scripts/ledger.py render
```

Record new variants and user-confirmed facts in local `RESUME.md`. Ask at most two
specific questions about meaningful evidence gaps, when any exist; do not repeat
answered questions. Keep unanswered items unconfirmed. Include the source JD and
date when recording answers. Distinguish a tailored delivery from an application
actually submitted by the user. Manual edits require a fresh PDF export and gate.

## Bundled tools and references

- `scripts/docx_toolkit.py`: extract, apply, audit, coverage, verify-format, config.
- `scripts/verify_output.py`: delivery checks, configured limits, reported keyword gaps.
- `scripts/render_pdf.sh`: LibreOffice PDF export, approximate fallback, overwrite guard.
- `scripts/smoke_test.sh`: self-contained regression tests; `--pdf` adds full renders.
- `scripts/ledger.py`: append/render the local application history.
- `scripts/ocr.swift`, `scripts/pdfcheck.swift`: macOS OCR and PDF text/page checks.
- `references/tailoring-playbook.md`: field-neutral evidence, phrasing, and page-fit.
- `references/ats-audit.md`: audit rules and current template constraints.
- `references/ledger.md`: ledger schema and JD archiving.

The instructions are harness-independent; bundled PDF/OCR verification currently
requires macOS/Swift. See `README.md` for dependencies and supported template shapes.

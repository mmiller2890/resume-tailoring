# Ledger

`ledger.jsonl` lives in the candidate's configured corpus – never in this public
repository. It is append-only, one JSON object per line. `ledger.md` is the human
view; regenerate with `ledger.py render`, never edit it by hand.

## Entry shape

This is a fictional example; labels and bullet IDs are candidate-defined.

```json
{
  "date": "YYYY-MM-DD",
  "company": "ExampleCo",
  "role": "Staff Accountant",
  "keywords_total": 3,
  "coverage": "3/3",
  "pages": 1,
  "audit_passed": true,
  "bullets_shipped": ["role1-reconciliation", "role1-close"],
  "output_docx": "ExampleCo/resume.docx",
  "output_pdf": "ExampleCo/resume.pdf",
  "jd_path": "ExampleCo/JD.md",
  "notes": "Tailored and delivered; submission not yet confirmed."
}
```

## Append and render

```bash
python3 scripts/ledger.py append entry.json
python3 scripts/ledger.py render
```

A JSON object string also works as the append argument. Record actual coverage
and acknowledged gaps; do not report full coverage if terms are missing. Delivery
of a tailored resume is not proof the candidate applied. Use notes to distinguish
delivery from a confirmed submission; record submission only when confirmed.

## JD archiving

Save the verbatim JD to `outputs/<Company>/JD.md` before tailoring. Use distinct
role folders when applying to more than one role at the same company. Keep the
candidate's output locations and evidence history together for later review.

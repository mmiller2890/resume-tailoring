# ATS Audit - empirical failure data

Real parser operator, ~4,000 files, 82% of resumes had at least one failure. The
audit gates delivery - every check must pass, and the checks themselves are
tested (each has a fixture that reproduces the failure).

| # | Parser failure | Rate | How `docx_toolkit.py audit` enforces it |
|---|---------------|------|------------------------------------------|
| 1 | Skills grid/table flattened into "PythonSQLTableauExcel" | 41% | `<w:tbl>`, `txbxContent`, `<w:pict>` absent in document.xml |
| 2 | Name not detected (name in header/text box/image) | 26% | With `--name "Full Name"`, first body paragraph equals the name exactly; header/footer parts carrying contact-like content are also inspected |
| 3 | Em dashes garbled | 19% | No `\u2014` / `\u2013` in any `w:t` run |
| 4 | Icon bullets become garbage | 18% | `numbering.xml` inspected: `lvlText` glyphs + `rFonts` per level, judged jointly (e.g. Word's Symbol+U+F0B7 native bullet passes; Wingdings arrow fails) |
| 4b | Contact info trapped in header/footer | (extends 2) | Every `word/header*.xml` / `footer*.xml` inspected; any part matching email/phone or with >15 chars fails |
| 5 | Two-column layouts interleave sidebar with history | 11% | One `w:sectPr`, no tables, no `framePr` |
| 6 | Ambiguous dates ("2019-21", "Summer 2022") | 9% | Only job title lines (2-run paragraphs where run 2 carries a year) must match `Month YYYY - Month YYYY` |
| 7 | Smart quotes mangled | 8% | No `\u201c` `\u201d` `\u2018` `\u2019` in `w:t` runs |
| 8 | Name merged with next line (text-box spacing lost) | 8% | First paragraph contains no ` | ` separator and is non-empty |
| 9 | Creative headings unclassifiable | 8% | Headings present as paragraph-level matches: some paragraph ends with SUMMARY, some with EXPERIENCE, some with SKILLS, exactly `EDUCATION` |
| 3b | Any non-ASCII in text | - | No character > 126 in any `w:t` run (em dashes, ellipses, curly quotes, icon glyphs all caught here too) |
| + | Scanned image, no text layer (~1 in 10) | - | PDF must extract via `pdfcheck.swift` - the ATS "selectable text" check; a PDF that fails extraction scores zero |

`audit [--name "Full Name"] [--json]` checks document.xml via zipfile (never via a
temp extraction), so headers, footers, and numbering are never invisible. The `+`
check (text layer) is enforced by `verify_output.py`'s `pdf_text_layer` gate, not
by `audit` itself.

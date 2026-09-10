# STATUS: IMPLEMENTED 2026-08-29

All 13 tasks from this plan were implemented. The four handoff-review corrections
(canonical zip order, run-structure date scoping, joint glyph+font bullet check,
full-HFS-name Word matching) are folded in at the same time as the tasks
themselves, so no second pass was needed. Validated by `scripts/smoke_test.sh`
(13/13) and a byte-identical reproduction of the shipped ExampleCo docx.

---
# resume-tailoring: improvement plan (handoff)

Author's note: I built the `resume-tailoring` skill on 2026-08-29 in a single session,
then audited it by trying to break it. This document is the result. Everything below is
evidence-backed - each finding includes the command that proves it. Work the tasks in
priority order; P0 items are correctness bugs where the skill currently lies to the user.

## 1. What exists today

```
~/.pi/agent/skills/resume-tailoring/
├── SKILL.md                      # workflow, 9-point ATS audit, tailoring heuristics
└── scripts/
    ├── docx_toolkit.py           # extract | apply | audit | coverage
    ├── ocr.swift                 # Vision OCR for screenshot JDs
    └── pdfcheck.swift            # PDFKit page count + probe strings

~/Documents/resume-outputs/
├── RESUME.md                     # master memory: bullet library, skills pool, decisions
├── ledger.md                     # application log
├── ExampleCorp/resume.docx          # master template (never modified)
└── ExampleCo-Role/        # first tailored output (docx + pdf)
```

Design contract: the model makes tailoring judgments (what text), the toolkit performs
mechanics deterministically (how it lands in the file). Keep that separation - it is why
the system is testable at all.

## 2. Findings

Reproduce all of these from `/tmp/skillaudit` (recreate as needed). `T` =
`~/Documents/resume-outputs/ExampleCorp/resume.docx`,
`TK` = `~/.pi/agent/skills/resume-tailoring/scripts/docx_toolkit.py`.

### F1 (P0, data loss) - `apply` silently discards output on relative paths

`cmd_apply` runs `subprocess.run(['zip', ...], cwd=td)` where `td` is a
`TemporaryDirectory`. A relative `out` path is therefore created *inside* the temp dir and
destroyed on context exit. It only appeared to work in testing because I passed absolute
paths every time.

```bash
cd /tmp && echo '{"set_text":{"3":"x"}}' > e.json
python3 $TK apply "$T" e.json out.docx     # FileNotFoundError, no output file
python3 $TK apply "$T" e.json /tmp/out.docx # works
```

A fresh agent working inside a company folder will naturally write `resume.docx`. This
must not depend on the caller remembering to absolutize.

### F2 (P0, false confidence) - the icon-bullet check is a no-op

Failure mode #4 (18% of resumes) is icon/glyph bullets. The check is:

```python
all(n.isdigit() for n in re.findall(r'<w:numId w:val="(\w+)"', xml))
```

`numId` values are always numeric in valid OOXML, so this is always true. It never reads
`word/numbering.xml`, where the glyph actually lives. Proof - inject a Wingdings arrow and
the audit still returns a clean bill of health:

```bash
mkdir -p /tmp/ib && cd /tmp/ib && unzip -q "$T" -d x
python3 - <<'EOF'
p='x/word/numbering.xml'; s=open(p,encoding='utf-8').read()
s=s.replace('<w:lvlText w:val="\u25cf"/>','<w:lvlText w:val="\uf0e0"/>')
s=s.replace('<w:rFonts w:ascii="Symbol"','<w:rFonts w:ascii="Wingdings"')
open(p,'w',encoding='utf-8').write(s)
EOF
cd x && zip -qrX ../icon.docx '[Content_Types].xml' _rels docProps word && cd ..
python3 $TK audit icon.docx    # -> PASS [4] ... 10/10 checks passed   (WRONG)
```

### F3 (P0, blind spot) - headers/footers are invisible to the audit

Failure mode #2 (name not detected, 26% - the most common serious failure) is usually
caused by the name living in a header region. `cmd_audit` reads only `word/document.xml`,
so `word/header*.xml` and `footer*.xml` are structurally invisible.

```bash
mkdir -p /tmp/hd && cd /tmp/hd && unzip -q "$T" -d x
printf '%s' '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Test Owner</w:t></w:r></w:p></w:hdr>' > x/word/header1.xml
cd x && zip -qrX ../hdr.docx '[Content_Types].xml' _rels docProps word && cd ..
python3 $TK audit hdr.docx     # -> 10/10 checks passed, header never inspected
```

The current template has no headers, so this is latent, not active. It becomes real the
moment anyone edits the template in Word and adds one.

### F4 (P1, false positive that blocks delivery) - date check over-scopes

Check 6 flags *any* paragraph containing a year that lacks a full `Month YYYY - Month YYYY`
range. A legitimate education line fails and blocks the delivery gate:

```bash
python3 -c "import json;json.dump({'set_text':{'54':'State University | Cybersecurity Bootcamp, Graduated 20XX'}},open('/tmp/d.json','w'))"
python3 $TK apply "$T" /tmp/d.json /tmp/dated.docx >/dev/null
python3 $TK audit /tmp/dated.docx   # -> FAIL [6], 9/10
```

The rule only applies to job title lines. Education dates, certification years, and "2019
- Present" style single tokens elsewhere are legitimate.

### F5 (P1, unenforced core promise) - format preservation is true but untested

The headline guarantee is "styles/numbering byte-identical". It currently holds:

```bash
python3 - <<'EOF'
import zipfile
a=zipfile.ZipFile("<template>"); b=zipfile.ZipFile("/tmp/out.docx")
print([n for n in a.namelist() if n!="word/document.xml" and a.read(n)!=b.read(n)] or "byte-identical")
print("first entry:", b.namelist()[0])   # [Content_Types].xml -> OPC-correct
EOF
```

Result: no drift, `[Content_Types].xml` first. But nothing in the code asserts it. This is
the one invariant that must never silently regress, and it is one careless refactor of the
repack step away from breaking. Assert it in code, not in a doc.

### F6 (P1) - hardcoded, date-stamped paths in two places

`SKILL.md` and `RESUME.md` both hardcode
`~/Documents/resume-outputs/`. That path contains a session date;
it will move. Two copies of the same truth also drift independently. Path resolution needs
one owner.

### F7 (P1) - no machine-readable output, so gating is stdout-scraping

`audit` and `coverage` print prose. Any automated gate (evals, CI, a wrapper script) has to
parse text. Add `--json`.

### F8 (P1) - `apply` has no dry-run and no spec validation

The model composes an edit spec blind and finds out whether it was right only after Word
renders. Also: an index appearing in both `set_text` and `remove_paragraphs` is silently
wasted work, and there is no confirmation of what changed.

### F9 (P2) - the highest-value part of memory is empty and has no filling mechanism

`RESUME.md`'s "Experience pool (user intake)" is the thing that makes tailoring better than
keyword-stuffing - it is where experience the resume doesn't show accumulates. It is empty,
and nothing in the workflow ever prompts the user to add to it. Every application is an
opportunity to harvest 1-2 facts and it is being wasted.

### F10 (P2) - ledger loses provenance, JD text is discarded

The ledger records a coverage number but not *which bullet variants shipped*, so "what did
Meta actually see?" is unanswerable. The JD itself is analyzed then thrown away, which
blocks re-tailoring, interview prep, and any later audit of why a keyword was chosen.

### F11 (P2) - Word automation is fragile

`osascript` blindly acts on `active document`. With a modal dialog open or another document
frontmost, this can save or close the wrong thing. There is also no fallback when Word is
unavailable, and every page-count check costs ~10s of Word round-trip during the page-fit
loop.

### F12 (P2) - no evals, unoptimized trigger description

skill-creator's methodology (draft -> test prompts -> benchmark -> iterate) was skipped.
This skill is an unusually good candidate for automated evals because its outputs are
objectively verifiable by exit code.

## 3. Tasks

### P0-1: Fix the relative-path bug and make repack pure-Python

Two birds: removing the `zip` subprocess also removes the `cwd` trap, the external binary
dependency, and lets us preserve the source archive's entry order exactly.

In `docx_toolkit.py`, replace the repack block at the end of `cmd_apply`:

```python
def _repack(src_docx, workdir, out_path):
    """Rewrite src_docx into out_path, substituting files changed in workdir.

    Preserves the source archive's entry order and per-entry compression, which keeps
    [Content_Types].xml first (OPC requires it) and avoids any dependence on the `zip`
    binary or the process cwd.
    """
    out_path = os.path.abspath(out_path)          # F1: never relative to the temp cwd
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(src_docx) as zin, \
         zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():               # source order preserved
            disk = os.path.join(workdir, info.filename)
            data = open(disk, 'rb').read() if os.path.isfile(disk) else zin.read(info.filename)
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zout.writestr(zi, data)
    return out_path
```

Call it as `out = _repack(src, td, out)` before the `print`, and delete the
`subprocess.run([...'zip'...])` call plus the now-unused `subprocess` import.

Acceptance:
```bash
cd /tmp && echo '{"set_text":{"3":"relative path test"}}' > e.json
python3 $TK apply "$T" e.json rel_out.docx && test -f /tmp/rel_out.docx && echo PASS
python3 -c "import zipfile;print(zipfile.ZipFile('/tmp/rel_out.docx').namelist()[0])"  # [Content_Types].xml
```

### P0-2: Enforce format preservation in code

Add to `docx_toolkit.py` and call it at the end of `cmd_apply` (and expose as a
`verify-format` subcommand so the gate chain can re-check any delivered file):

```python
def assert_format_preserved(src_docx, out_docx):
    """The core guarantee: only word/document.xml may differ. Everything else - styles,
    numbering, fonts, rels, content types - must be byte-identical, or the output is not
    'the same template with new text' and must not ship."""
    with zipfile.ZipFile(src_docx) as a, zipfile.ZipFile(out_docx) as b:
        na, nb = set(a.namelist()), set(b.namelist())
        if na != nb:
            raise ValueError('archive entries changed: only in source=%s only in output=%s'
                             % (sorted(na - nb), sorted(nb - na)))
        drifted = [n for n in sorted(na) if n != 'word/document.xml' and a.read(n) != b.read(n)]
        if drifted:
            raise ValueError('format drift in: %s' % drifted)
        if b.namelist()[0] != '[Content_Types].xml':
            raise ValueError('[Content_Types].xml must be the first archive entry (OPC)')
    return True
```

Acceptance: `apply` on the template succeeds and prints a preservation-confirmed line;
artificially touching `styles.xml` in the workdir makes it raise.

### P0-3: Make the bullet-glyph check real

Replace check 4 in `cmd_audit`. Read `numbering.xml`, look at the actual `lvlText` glyphs
and their fonts, and also catch glyphs typed literally at the start of text runs:

```python
SAFE_BULLET_GLYPHS = {'\u25cf', '\u25cb', '\u25aa', '\u25a0', '\u2022', '\u25e6', '-', 'o'}
SYMBOL_FONTS = {'wingdings', 'wingdings 2', 'wingdings 3', 'webdings', 'symbol'}

def _bullet_check(zf):
    """Failure mode #4: icon bullets (arrows, checkmarks, custom glyphs) arrive as garbage
    characters. The glyph lives in numbering.xml, not document.xml, so it must be read
    there - and symbol fonts are the tell even when the codepoint looks harmless."""
    try:
        numbering = zf.read('word/numbering.xml').decode('utf-8')
    except KeyError:
        return True, 'no numbering.xml (no lists)'
    glyphs = re.findall(r'<w:lvlText w:val="([^"]*)"/>', numbering)
    fonts = {f.lower() for f in re.findall(r'w:ascii="([^"]+)"', numbering)}
    bad_glyphs = [g for g in glyphs if g and not g.startswith('%') and g not in SAFE_BULLET_GLYPHS]
    bad_fonts = sorted(fonts & SYMBOL_FONTS - {'symbol'})  # Symbol+U+F0B7 is Word's own default
    detail = []
    if bad_glyphs:
        detail.append('non-standard glyphs: %s' % [hex(ord(g[0])) for g in bad_glyphs])
    if bad_fonts:
        detail.append('symbol fonts: %s' % bad_fonts)
    return not detail, '; '.join(detail) or '%d list levels, standard glyphs' % len(glyphs)
```

Acceptance: the Wingdings file from F2 must now FAIL check 4; the real template must PASS.

### P0-4: Inspect headers, footers, and text boxes

Add a check that reads every `word/header*.xml` / `word/footer*.xml` and fails when they
carry contact-like content, since that is exactly how the 26% failure happens:

```python
def _header_check(zf):
    parts = [n for n in zf.namelist() if re.match(r'word/(header|footer)\d*\.xml$', n)]
    offenders = []
    for n in parts:
        text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', zf.read(n).decode('utf-8')))
        if re.search(r'@|\(\d{3}\)|\d{3}-\d{4}', text) or len(text.strip()) > 15:
            offenders.append('%s: %r' % (n, text[:60]))
    return not offenders, '; '.join(offenders) or ('%d header/footer parts, none carrying contact info' % len(parts))
```

Acceptance: the F3 header file must FAIL; the template must PASS.

### P1-5: Scope the date check to job title lines

Only enforce the range format where it belongs. Title lines in this template are the 2-run
paragraphs containing ` | ` next to a date; everything else (education, certifications)
should be exempt, and a bare 4-digit year with no month is the actual thing worth warning
about:

```python
title_like = [t for t in para_texts if ' | ' in t and re.search(r'\b(19|20)\d{2}\b', t)]
bad = [t[:60] for t in title_like if not DATE_RE.search(t)]
check(6, 'job title lines use Month YYYY - Month YYYY (9%)', not bad,
      '; '.join(bad) if bad else '%d title lines verified' % len(title_like))
```

Acceptance: the F4 education file passes; a job line rewritten to `2022-23` fails.

### P1-6: `--json` on audit and coverage, plus one gate script

Give every check a machine-readable form, then write the single gate that both the skill
workflow and any future eval grader call. One definition of "good output", used everywhere:

```python
# in cmd_audit / cmd_coverage: build `results` as dicts, then
if '--json' in sys.argv:
    print(json.dumps({'file': docx, 'passed': not failed,
                      'checks': [{'id': n, 'desc': d, 'passed': ok, 'detail': det}
                                 for n, d, ok, det in results]}, indent=2))
```

```python
#!/usr/bin/env python3
"""verify_output.py - the delivery gate. Exit 0 only if every gate passes.

Usage: verify_output.py <tailored.docx> <template.docx> <keywords.txt> [--pdf out.pdf] [--json]
Gates: ATS audit, format preservation vs template, keyword coverage, and - when a PDF is
given - page count <= 2 plus text-layer extraction of the name.
"""
import json, subprocess, sys, pathlib
SCRIPTS = pathlib.Path(__file__).parent

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

def main():
    docx, template, kwfile = sys.argv[1], sys.argv[2], sys.argv[3]
    keywords = pathlib.Path(kwfile).read_text().strip()
    gates = {}
    rc, out = run(['python3', str(SCRIPTS / 'docx_toolkit.py'), 'audit', docx])
    gates['ats_audit'] = {'passed': rc == 0, 'output': out}
    rc, out = run(['python3', str(SCRIPTS / 'docx_toolkit.py'), 'verify-format', docx, template])
    gates['format_preserved'] = {'passed': rc == 0, 'output': out}
    rc, out = run(['python3', str(SCRIPTS / 'docx_toolkit.py'), 'coverage', docx, keywords])
    gates['keyword_coverage'] = {'passed': rc == 0, 'output': out}
    if '--pdf' in sys.argv:
        pdf = sys.argv[sys.argv.index('--pdf') + 1]
        rc, out = run(['swift', str(SCRIPTS / 'pdfcheck.swift'), pdf, 'Test Owner'])
        pages = next((int(l.split(':')[1]) for l in out.splitlines() if l.startswith('Pages:')), 0)
        gates['pdf_text_layer'] = {'passed': rc == 0, 'output': out}
        gates['two_pages'] = {'passed': pages == 2, 'output': 'pages=%d' % pages}
    ok = all(g['passed'] for g in gates.values())
    print(json.dumps({'passed': ok, 'gates': gates}, indent=2) if '--json' in sys.argv
          else '\n'.join('%s %s' % ('PASS' if g['passed'] else 'FAIL', k) for k, g in gates.items()))
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
```

Then SKILL.md's Step 5 collapses to one command, which is also what makes P2-12 cheap.

### P1-7: Dry-run and spec validation for `apply`

```python
def _validate_spec(spec, paras):
    """Catch contradictions before they cost a Word render."""
    edited = {int(i) for k in ('set_text', 'set_skills_content', 'set_skills_line')
              for i in (spec.get(k) or {})}
    removed = {int(i) for i in (spec.get('remove_paragraphs') or [])}
    if edited & removed:
        raise ValueError('paragraphs both edited and removed (wasted edits): %s' % sorted(edited & removed))
    for i in edited | removed | {int(i) for k in ('clone_bullet_after', 'add_skills_line_after')
                                 for i in (spec.get(k) or {})}:
        if not 0 <= i < len(paras):
            raise ValueError('index %d out of range (0..%d)' % (i, len(paras) - 1))
```

And a `--dry-run` flag that prints `[idx] OLD -> NEW` per change plus the resulting
paragraph count, without writing a file. This turns "compose blind, render, discover" into
"compose, inspect, then render".

### P1-8: Config-owned paths

Create `~/.config/resume-tailoring/config.json`:

```json
{
  "corpus_root": "~/Documents/resume-outputs",
  "template": "~/Documents/resume-outputs/ExampleCorp/resume.docx",
  "memory": "RESUME.md",
  "ledger": "ledger.jsonl",
  "owner_name": "Test Owner",
  "max_pages": 2
}
```

```python
def load_config():
    """Resolution order: $RESUME_TAILORING_CONFIG, then ~/.config/resume-tailoring/config.json.
    Paths live in exactly one place so SKILL.md and RESUME.md can stop repeating them - and
    so a moved corpus is a one-line fix rather than a hunt through prose."""
    p = os.environ.get('RESUME_TAILORING_CONFIG') or os.path.expanduser(
        '~/.config/resume-tailoring/config.json')
    if not os.path.exists(p):
        raise SystemExit('no config at %s - create it (see SKILL.md) or set '
                         'RESUME_TAILORING_CONFIG' % p)
    cfg = json.load(open(p))
    for key in ('corpus_root', 'template'):
        if not os.path.exists(cfg[key]):
            raise SystemExit('config %s points at missing path: %s' % (key, cfg[key]))
    return cfg
```

Then replace the Known-paths table in SKILL.md with "run `docx_toolkit.py config` to
resolve paths; ask the user if it errors", and delete the duplicate table from RESUME.md.

### P1-9: Harden the Word render

Target the document by name instead of trusting `active document`, and degrade gracefully:

```applescript
tell application "Microsoft Word"
    set docFile to POSIX file "ABS_DOCX" as alias
    open docFile
    delay 2
    repeat with d in documents
        if name of d is "BASENAME.docx" then
            save as d file name "ABS_PDF" file format format PDF
            close d saving no
            return "ok"
        end if
    end repeat
    return "error: document not found among open documents"
end tell
```

Wrap it in `scripts/render_pdf.sh` that takes docx + pdf paths, checks Word is installed,
returns nonzero with a clear message when it is not, and never closes a document it did not
open. Add a cheap pre-flight so the page-fit loop stops paying 10s per guess:

```python
def estimate_pages(docx, chars_per_page=7900):
    """Calibrated against this template: the shipped 2-page file extracts ~7,900 chars.
    Use it to skip obviously-over drafts before invoking Word - it is a pre-filter, never
    a substitute for the real render."""
```

### P2-10: Make memory self-feeding

The intake section stays empty unless the workflow fills it. Add to SKILL.md Step 7:

> After delivering, look at what the JD asked for that the resume could not evidence
> strongly. Ask the user at most two specific questions about those gaps (e.g. "the JD
> wanted NetApp/EMC specifically - any hands-on there?"), and append the answers to the
> Experience pool in RESUME.md with the date and the JD that surfaced them. One application
> should leave the memory richer than it found it; that compounding is the entire point of
> keeping memory at all.

Also record shipped bullet IDs per application so provenance is answerable.

### P2-11: Ledger as JSONL + JD archive

```python
# scripts/ledger.py  - append + render
def append(entry: dict, path):   # one JSON object per line, never rewrite history
    with open(path, 'a') as f: f.write(json.dumps(entry) + '\n')

def render_md(jsonl_path, md_path):  # regenerate the human view from the machine record
    ...
```

Entry shape: `{date, company, role, jd_path, keywords_total, coverage, pages, audit_passed,
bullets_shipped: ["M1","M3-game","N1-tier"], output_docx, output_pdf, notes}`.
Archive the JD verbatim at `<Company>/JD.md` at Step 2 - it costs nothing and unlocks
re-tailoring, interview prep, and later "why this keyword" audits.

### P2-12: Evals

Now cheap, because `verify_output.py` is the grader. Create `evals/evals.json`:

```json
{
  "skill_name": "resume-tailoring",
  "evals": [
    {"id": 1, "prompt": "here's a JD for a desktop support role at a hospital system [paste]. tailor my resume", "assertions": ["verify_output.py exits 0", "pages == 2", "coverage == 100%", "styles.xml byte-identical to template", "template file mtime unchanged"]},
    {"id": 2, "prompt": "tailor for this SOC analyst posting [paste] - heavy on SIEM and incident response", "assertions": ["security bullets promoted", "gaming/production skills line absent", "verify_output.py exits 0"]},
    {"id": 3, "prompt": "[3 screenshot paths] tailor to this", "assertions": ["OCR ran", "no non-ASCII in output", "verify_output.py exits 0"]}
  ]
}
```

Eval 2 matters most: it tests that tailoring *removes* irrelevant material rather than only
adding. Run with skill vs. without per skill-creator's procedure, then optimize the
description with `scripts/run_loop.py` - the current description is long, untested, and
plausibly over-triggers on "shares screenshots or images to read".

### P2-13: Split SKILL.md

Move the 9-point audit table to `references/ats-audit.md` and the heuristics to
`references/tailoring-playbook.md`, leaving the workflow spine plus pointers in SKILL.md.
Body stays lean for the always-loaded case; detail loads when actually consulted.

## 4. Suggested order

1. P0-1, P0-2 together (both touch the repack path)
2. P0-3, P0-4, P1-5 together (all in `cmd_audit`), then re-run the F2/F3/F4 repros
3. P1-6 (`--json` + `verify_output.py`), then update SKILL.md Step 5 to call it
4. P1-7, P1-8, P1-9
5. P2 items as appetite allows; P2-10 has the best value-per-line of anything here

## 5. Notes for whoever picks this up

- Regression-test against the real artifacts, not synthetic ones: the template and the
  shipped `ExampleCo-Role/resume.docx` are the fixtures. Every change must keep the
  template at a clean audit and keep the shipped file at 2 pages, 54/54 coverage.
- Never modify the template. If you need a mutated docx, build it in `/tmp`.
- Keep the model/mechanics split. If you find yourself encoding *what to write* into
  Python, stop - that judgment belongs to the model reading SKILL.md. The toolkit's job is
  to make the model's decisions land losslessly and to refuse bad output.
- The ASCII guard in `apply` is load-bearing (JD copy-paste is full of em dashes and curly
  quotes). Do not relax it into a warning.
- When you touch `cmd_audit`, remember the checks encode measured parser failure rates from
  a real ATS operator's data. Do not add "checks" that cannot fail - F2 is exactly that
  mistake, and it shipped while reporting 10/10.

#!/usr/bin/env python3
"""docx_toolkit.py - mechanical core for resume tailoring.

Edits docx text runs (w:t) with zero format drift: every archive entry except
word/document.xml is copied byte-for-byte from the source, and that guarantee
is enforced in code after every apply (assert_format_preserved). The template
docx is read-only for this tool - `apply` always writes to a new file.

Commands:
  extract       <docx>                                   numbered paragraph map
  apply         <src.docx> <edits.json> <out.docx> [--dry-run]
  audit         <docx> [--name "Full Name"] [--json]
  coverage      <docx> "kw1, kw2, ..." [--json]
  verify-format <out.docx> <src.docx>
  config                                                 print resolved paths

Edit spec (edits.json) - indices refer to the SOURCE document's original
paragraph order (as shown by `extract`):

{
  "set_text":              {"3": "new text"},
  "set_skills_content":    {"47": "content run text"},
  "set_skills_line":       {"51": ["Category: ", "content"]},
  "clone_bullet_after":    {"13": "new bullet text"},
  "add_skills_line_after": {"50": ["Category: ", "content"]},
  "remove_paragraphs":     [10, 19]
}

Execution order: set_text, set_skills_content, set_skills_line,
clone_bullet_after, add_skills_line_after, remove_paragraphs. All indices
resolve against the ORIGINAL paragraph list, so they stay stable regardless
of insertions or removals in the same spec.

Non-ASCII in supplied text is rejected (em dashes, smart quotes and ellipses
are what ATS parsers mangle - see `audit`). This guard is load-bearing: job
description copy-paste is full of them.
"""
import copy
import json
import os
import re
import sys
import zipfile

from lxml import etree

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(tag): return '{%s}%s' % (W_NS, tag)

DATE_RE = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4} '
    r'- ((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}|Present)')

# Bullets that survive real ATS parsers. Word's own default bullet (Symbol
# font + U+F0B7 private-use char) is exempted jointly in _bullet_check, not
# here, because a private-use codepoint alone is not a reliable signal.
SAFE_BULLET_GLYPHS = {'\u25cf', '\u25cb', '\u25aa', '\u25a0', '\u2022', '\u25e6',
                      '\u00b7', '-', 'o'}
ICON_FONTS = {'wingdings', 'wingdings 2', 'wingdings 3', 'webdings'}
WORD_DEFAULT_BULLET = '\uF0B7'   # Symbol font + F0B7 is Word's native bullet

CONFIG_PATH = os.environ.get('RESUME_TAILORING_CONFIG') or os.path.expanduser(
    '~/.config/resume-tailoring/config.json')


# ---------------------------------------------------------------- config

def load_config(strict=True):
    """Single owner of all paths. Resolution order: $RESUME_TAILORING_CONFIG,
    then ~/.config/resume-tailoring/config.json. Keeping paths out of SKILL.md
    and RESUME.md means a moved corpus is a one-line fix instead of a hunt."""
    if not os.path.exists(CONFIG_PATH):
        if strict:
            raise SystemExit('no config at %s - create it (see SKILL.md) or set '
                             'RESUME_TAILORING_CONFIG' % CONFIG_PATH)
        return {'owner_name': 'Test Owner', 'max_pages': 2}
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    for key in ('corpus_root', 'template'):
        if key in cfg and cfg[key] and not os.path.exists(cfg[key]):
            raise SystemExit('config %s points at missing path: %s' % (key, cfg[key]))
    return cfg


def cmd_config():
    cfg = load_config()
    for key in ('corpus_root', 'template', 'memory', 'ledger', 'owner_name', 'max_pages'):
        val = cfg.get(key, '(not set)')
        if isinstance(val, str) and key in ('corpus_root', 'template', 'memory', 'ledger') and val != '(not set)':
            val = '%s %s' % (val, '(exists)' if os.path.exists(val) else '(MISSING)')
        print('%-12s %s' % (key + ':', val))
    return 0


# ---------------------------------------------------------------- helpers

def _open_tree(docx):
    """Parse word/document.xml from the zip, return (root_element, zip_handle)."""
    zf = zipfile.ZipFile(docx)
    root = etree.fromstring(zf.read('word/document.xml'))
    return root, zf


def _paras(root):
    return root.find(w('body')).findall(w('p'))


def _runs_text(p):
    """[(run_element, text_element, text)] for direct w:r children of paragraph."""
    out = []
    for r in p.findall(w('r')):
        for t in r.findall(w('t')):
            out.append((r, t, t.text or ''))
    return out


def _para_text(p):
    return ''.join(t for _, _, t in _runs_text(p))


def _ascii_check(text, where):
    bad = sorted({c for c in text if ord(c) > 126})
    if bad:
        raise ValueError('%s contains non-ASCII %r - replace before applying '
                         '(these are the characters ATS parsers mangle)' % (where, bad))


# ---------------------------------------------------------------- extract

def cmd_extract(docx):
    root, zf = _open_tree(docx)
    zf.close()
    for i, p in enumerate(_paras(root)):
        runs = _runs_text(p)
        pPr = p.find(w('pPr'))
        style, is_list = None, False
        if pPr is not None:
            ps = pPr.find(w('pStyle'))
            if ps is not None:
                style = ps.get(w('val'))
            is_list = pPr.find(w('numPr')) is not None
        marks = ','.join(m for m in (('BULLET' if is_list else ''),
                                     ('style=' + style if style else '')) if m)
        print('[%03d] runs=%d %-28s | %s' % (i, len(runs), marks or '-', _para_text(p)))
    return 0


# ---------------------------------------------------------------- apply

def _validate_spec(spec, paras):
    """Catch contradictions BEFORE applying anything, so a bad spec never
    produces a half-edited document. All failures name the exact index."""
    edited = {int(i) for k in ('set_text', 'set_skills_content', 'set_skills_line')
              for i in (spec.get(k) or {})}
    removed = {int(i) for i in (spec.get('remove_paragraphs') or [])}
    cloned = {int(i) for i in (spec.get('clone_bullet_after') or {})}
    added = {int(i) for i in (spec.get('add_skills_line_after') or {})}

    for idx in sorted(edited | removed | cloned | added):
        if not 0 <= idx < len(paras):
            raise ValueError('paragraph index %d out of range (document has %d paragraphs)'
                             % (idx, len(paras)))
    if edited & removed:
        raise ValueError('paragraphs both edited and removed (wasted edits): %s'
                         % sorted(edited & removed))

    for idx in sorted(edited):
        n_runs = len(_runs_text(paras[idx]))
        kind = 'set_text' if idx in {int(i) for i in (spec.get('set_text') or {})} else 'skills'
        expected = 1 if kind == 'set_text' else 2
        if n_runs != expected:
            raise ValueError('paragraph %d has %d text runs; %s expects %d - inspect with extract'
                             % (idx, n_runs, kind, expected))
    for idx in sorted(cloned):
        p = paras[idx]
        if p.find(w('pPr')) is None or p.find(w('pPr')).find(w('numPr')) is None:
            raise ValueError('clone_bullet_after[%d]: source paragraph is not a list bullet '
                             '(no numPr) - clone_bullet_after must clone a bullet' % idx)
        if len(_runs_text(p)) != 1:
            raise ValueError('clone_bullet_after[%d]: source paragraph has %d runs, expected 1'
                             % (idx, len(_runs_text(p))))
    for idx in sorted(added):
        if len(_runs_text(paras[idx])) != 2:
            raise ValueError('add_skills_line_after[%d]: source paragraph must have 2 text runs '
                             '(bold category + content)' % idx)


def _set_single_run_text(p, text, where):
    runs = _runs_text(p)
    if len(runs) != 1:
        raise ValueError('%s: expected 1 text run, found %d - for 2-run lines use '
                         'set_skills_content/set_skills_line' % (where, len(runs)))
    _ascii_check(text, where)
    runs[0][1].text = text


def _set_skills_runs(p, cat, content, where):
    runs = _runs_text(p)
    if len(runs) != 2:
        raise ValueError('%s: expected 2 text runs (bold category + content), found %d'
                         % (where, len(runs)))
    _ascii_check(cat + content, where)
    runs[0][1].text = cat
    runs[1][1].text = content


def _repack(src_docx, out_path, replacements):
    """Rewrite src_docx into out_path, substituting whole-file contents from
    `replacements` ({archive_name: bytes}).

    Canonical entry order: [Content_Types].xml hoisted to first (OPC-friendly,
    matches the previously Word-verified output), remaining entries in source
    order. Pure zipfile - no `zip` binary, no temp directory, no cwd
    dependence; the output path is absolutized so relative paths land where
    the caller actually is."""
    out_path = os.path.abspath(out_path)
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with zipfile.ZipFile(src_docx) as zin, \
         zipfile.ZipFile(out_path, 'w') as zout:
        names = [i.filename for i in zin.infolist()]
        ordered = (['[Content_Types].xml'] if '[Content_Types].xml' in names else []) + \
                  [n for n in names if n != '[Content_Types].xml']
        infos = {i.filename: i for i in zin.infolist()}
        zout.comment = zin.comment
        for name in ordered:
            info = infos[name]
            if name in replacements:
                data = replacements[name]
            else:
                data = zin.read(name)
            zi = zipfile.ZipInfo(name, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.create_system = info.create_system
            zi.internal_attr = info.internal_attr
            zi.comment = info.comment
            zout.writestr(zi, data)
    return out_path


def assert_format_preserved(src_docx, out_docx):
    """The core guarantee, enforced: only word/document.xml may differ between
    source and output. Everything else - styles, numbering, fonts, rels,
    content types - must be byte-identical, or the output is NOT 'the same
    template with new text' and must not ship. Also enforces the canonical
    entry order ([Content_Types].xml first)."""
    with zipfile.ZipFile(src_docx) as a, zipfile.ZipFile(out_docx) as b:
        na, nb = set(a.namelist()), set(b.namelist())
        if na != nb:
            raise ValueError('archive entries changed - only in source: %s, only in output: %s'
                             % (sorted(na - nb), sorted(nb - na)))
        drifted = [n for n in sorted(na) if n != 'word/document.xml' and a.read(n) != b.read(n)]
        if drifted:
            raise ValueError('format drift detected in: %s - output rejected' % drifted)
        if b.namelist()[0] != '[Content_Types].xml':
            raise ValueError('[Content_Types].xml must be the first archive entry (OPC)')
    return True


def cmd_apply(src, edits_path, out, dry_run=False):
    with open(edits_path) as f:
        spec = json.load(f)

    if os.path.abspath(out) == os.path.abspath(src) and not dry_run:
        raise ValueError('apply must write to a NEW file; the template is never modified')

    root, zf = _open_tree(src)
    zf.close()
    paras = _paras(root)
    _validate_spec(spec, paras)

    def P(idx):
        return paras[int(idx)]

    # capture old text for the dry-run report
    touched = set()
    for k in ('set_text', 'set_skills_content', 'set_skills_line'):
        touched.update(int(i) for i in (spec.get(k) or {}))
    touched.update(int(i) for i in (spec.get('remove_paragraphs') or []))
    old_text = {i: _para_text(paras[i]) for i in sorted(touched)}

    # 1) text edits
    for idx, text in (spec.get('set_text') or {}).items():
        _set_single_run_text(P(idx), text, 'set_text[%s]' % idx)
    for idx, text in (spec.get('set_skills_content') or {}).items():
        p = P(idx)
        runs = _runs_text(p)
        _ascii_check(text, 'set_skills_content[%s]' % idx)
        runs[1][1].text = text
    for idx, pair in (spec.get('set_skills_line') or {}).items():
        _set_skills_runs(P(idx), pair[0], pair[1], 'set_skills_line[%s]' % idx)

    # 2) clones
    for idx, text in (spec.get('clone_bullet_after') or {}).items():
        src_p = P(idx)
        new_p = copy.deepcopy(src_p)
        _set_single_run_text(new_p, text, 'clone_bullet_after[%s]' % idx)
        src_p.addnext(new_p)
    for idx, pair in (spec.get('add_skills_line_after') or {}).items():
        src_p = P(idx)
        new_p = copy.deepcopy(src_p)
        _set_skills_runs(new_p, pair[0], pair[1], 'add_skills_line_after[%s]' % idx)
        src_p.addnext(new_p)

    # 3) removals
    for idx in (spec.get('remove_paragraphs') or []):
        p = P(idx)
        p.getparent().remove(p)

    new_doc = etree.tostring(root, xml_declaration=True, encoding='UTF-8',
                             standalone=True)

    if dry_run:
        print('--- DRY RUN (nothing written) ---')
        for idx in sorted(touched):
            if idx in (spec.get('remove_paragraphs') or []):
                print('[%03d] REMOVE      %s' % (idx, (old_text[idx] or '')[:70]))
            else:
                new = _para_text(paras[idx]) if idx < len(paras) else ''
                print('[%03d] EDIT        %s' % (idx, (old_text[idx] or '')[:34]))
                print('      ->          %s' % new[:34])
        for idx in (spec.get('clone_bullet_after') or {}):
            print('[%s] CLONE AFTER  %s' % (idx, (spec['clone_bullet_after'][idx])[:60]))
        for idx in (spec.get('add_skills_line_after') or {}):
            print('[%s] ADD LINE     %s%s' % (idx, spec['add_skills_line_after'][idx][0],
                                              spec['add_skills_line_after'][idx][1][:50]))
        print('paragraphs: %d -> %d' % (len(paras), len(_paras(root))))
        return 0

    out = os.path.abspath(out)
    tmp = out + '.tmp'
    try:
        _repack(src, tmp, {'word/document.xml': new_doc})
        assert_format_preserved(src, tmp)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    print('wrote %s (%d bytes); format preservation verified (only word/document.xml changed)'
          % (out, os.path.getsize(out)))
    return 0


def cmd_verify_format(out, src):
    try:
        assert_format_preserved(src, out)
    except ValueError as e:
        print('FAIL: %s' % e)
        return 1
    print('PASS: %s preserves the format of %s (only word/document.xml may differ)' % (out, src))
    return 0


# ---------------------------------------------------------------- audit

def _bullet_check(zf):
    """Failure mode #4 (18%): icon bullets. The glyph lives in numbering.xml,
    not document.xml, so it must be read there - and glyph and font must be
    judged JOINTLY: Word's own default bullet is the Symbol font with the
    U+F0B7 private-use char, which must pass, while Wingdings/Webdings and
    unknown glyphs must fail."""
    try:
        numbering = zf.read('word/numbering.xml').decode('utf-8')
    except KeyError:
        return True, 'no numbering.xml (no lists in document)'
    levels = re.findall(r'<w:lvl\b.*?</w:lvl>', numbering, re.DOTALL)
    offenders = []
    for i, lvl in enumerate(levels):
        m = re.search(r'<w:lvlText w:val="([^"]*)"', lvl)
        glyph = m.group(1) if m else ''
        if not glyph or glyph.startswith('%'):
            continue   # no marker, or auto-numbered marker (%1. etc.)
        if glyph in SAFE_BULLET_GLYPHS:
            continue
        fonts = {f.lower() for f in re.findall(r'w:(?:ascii|hAnsi)="([^"]+)"', lvl)}
        if 'symbol' in fonts and glyph == WORD_DEFAULT_BULLET:
            continue   # Word's native default bullet
        offenders.append('lvl %d: glyph U+%04X fonts=%s'
                         % (i, ord(glyph[0]), sorted(fonts) or ['-']))
    icon_fonts = sorted({f.lower() for f in
                          re.findall(r'w:(?:ascii|hAnsi)="([^"]+)"', numbering)} & ICON_FONTS)
    detail = []
    if offenders:
        detail.append('non-standard bullet glyphs: ' + '; '.join(offenders))
    if icon_fonts:
        detail.append('icon fonts in use: %s' % icon_fonts)
    return (not detail), ('; '.join(detail) if detail
                          else '%d list levels, standard bullets' % len(levels))


def _header_check(zf):
    """Failure mode #2 (26%, the most common serious failure): the name or
    contact info living in a header region that parsers skip or mangle. Any
    header/footer part carrying contact-like content fails the audit."""
    parts = sorted(n for n in zf.namelist()
                   if re.match(r'word/(header|footer)\d*\.xml$', n))
    offenders = []
    for n in parts:
        try:
            xml = zf.read(n).decode('utf-8', errors='replace')
        except Exception as e:
            offenders.append('%s: unreadable (%s)' % (n, e))
            continue
        text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml))
        if re.search(r'@|\(\d{3}\)\s|\d{3}-\d{4}|\b\d{10}\b', text) or len(text.strip()) > 15:
            offenders.append('%s: %r' % (n, text.strip()[:60]))
    return (not offenders), ('; '.join(offenders) if offenders
                             else '%d header/footer part(s), none carrying contact info'
                             % len(parts))


def cmd_audit(docx, name=None, as_json=False):
    """9-point ATS audit from real parser failure data (~4,000 files, 82% of
    resumes had at least one failure). Exit nonzero on any FAIL."""
    with zipfile.ZipFile(docx) as zf:
        doc_xml = zf.read('word/document.xml').decode('utf-8')
        bullet_ok, bullet_detail = _bullet_check(zf)
        header_ok, header_detail = _header_check(zf)

    root = etree.fromstring(doc_xml.encode('utf-8'))
    paras = _paras(root)
    joined = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', doc_xml))
    first_para = _para_text(paras[0]) if paras else ''
    para_texts = [_para_text(p) for p in paras]

    results = []

    def check(n, desc, ok, detail=''):
        results.append((str(n), desc, bool(ok), detail))

    check(1, 'no tables/textboxes (skills grids parse as blobs, 41%)',
          '<w:tbl>' not in doc_xml and 'txbxContent' not in doc_xml
          and '<w:pict' not in doc_xml)
    if name:
        check(2, 'first body line is the name',
              first_para.strip() == name.strip(),
              'first paragraph: %r, expected %r' % (first_para.strip()[:40], name))
    else:
        check(2, 'name is plain text on first body line',
              first_para.strip() != '' and not first_para.startswith(' '),
              'first paragraph: %r' % first_para[:50])
    check(3, 'no em/en dashes (19%)', '\u2014' not in joined and '\u2013' not in joined)
    check(4, 'standard bullets only, no icon glyphs (18%)', bullet_ok, bullet_detail)
    check('4b', 'no contact info trapped in headers/footers (26%)', header_ok, header_detail)
    check(5, 'single column, no frames (11%)',
          doc_xml.count('<w:sectPr') <= 1 and '<w:tbl>' not in doc_xml
          and 'framePr' not in doc_xml)
    # Failure mode #6 (9%): ambiguous dates. Scoped to job TITLE lines, which
    # in this template family are 2-run paragraphs (title + "   |   dates").
    # Education/certification lines legitimately carry single dates.
    n_title, bad_dates = 0, []
    for p in paras:
        runs = _runs_text(p)
        if len(runs) == 2 and re.search(r'\b(19|20)\d{2}\b', runs[1][2]):
            n_title += 1
            if not DATE_RE.search(runs[1][2]):
                bad_dates.append(runs[1][2].strip()[:60])
    check(6, 'job title lines use Month YYYY - Month YYYY (9%)', not bad_dates,
          '; '.join(bad_dates) if bad_dates else '%d title lines verified' % n_title)
    check(7, 'no smart quotes (8%)',
          not any(q in joined for q in '\u201c\u201d\u2018\u2019'))
    check(8, 'name on its own paragraph, not merged (8%)',
          ' | ' not in first_para and first_para.strip() != '')
    upper_paras = [t.strip().upper() for t in para_texts]
    headings_ok = (any(p.endswith('SUMMARY') for p in upper_paras)
                   and any(p.endswith('EXPERIENCE') for p in upper_paras)
                   and any(p.endswith('SKILLS') for p in upper_paras)
                   and any(p == 'EDUCATION' for p in upper_paras))
    check(9, 'standard section headings present (8%)', headings_ok)
    bad_ascii = sorted({c for c in joined if ord(c) > 126})
    check('3b', 'no non-ASCII in text runs', not bad_ascii, repr(bad_ascii) if bad_ascii else '')

    failed = [r for r in results if not r[2]]
    if as_json:
        print(json.dumps({'file': docx, 'passed': not failed,
                          'checks': [{'id': n, 'desc': d, 'passed': ok, 'detail': det}
                                     for n, d, ok, det in results]}, indent=2))
    else:
        for n, desc, ok, detail in results:
            print('%s [%s] %s%s' % ('PASS' if ok else 'FAIL', n, desc,
                                    (' | ' + detail) if detail else ''))
        print('\n%d/%d checks passed' % (len(results) - len(failed), len(results)))
    return 1 if failed else 0


# ---------------------------------------------------------------- coverage

def cmd_coverage(docx, keywords_csv, as_json=False):
    keywords = [k.strip() for k in keywords_csv.split(',') if k.strip()]
    root, zf = _open_tree(docx)
    zf.close()
    joined = ''.join(_para_text(p) for p in _paras(root))
    low = joined.lower()
    missing = [k for k in keywords if k.lower() not in low]
    if as_json:
        print(json.dumps({'file': docx, 'total': len(keywords),
                          'present': len(keywords) - len(missing), 'missing': missing},
                         indent=2))
    else:
        print('coverage: %d/%d keywords present' % (len(keywords) - len(missing), len(keywords)))
        if missing:
            print('missing: %s' % ', '.join(missing))
    return 1 if missing else 0


# ---------------------------------------------------------------- main

def main():
    argv = [a for a in sys.argv[1:] if a not in ('--json',)]
    as_json = '--json' in sys.argv
    dry_run = '--dry-run' in sys.argv
    argv = [a for a in argv if a != '--dry-run']
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    try:
        if cmd == 'config':
            return cmd_config()
        if cmd == 'extract' and len(argv) == 2:
            return cmd_extract(argv[1])
        if cmd == 'apply' and len(argv) == 4:
            return cmd_apply(argv[1], argv[2], argv[3], dry_run=dry_run)
        if cmd == 'audit' and len(argv) >= 2:
            name = None
            rest = argv[2:]
            if '--name' in rest:
                name = rest[rest.index('--name') + 1]
            return cmd_audit(argv[1], name=name, as_json=as_json)
        if cmd == 'coverage' and len(argv) == 3:
            return cmd_coverage(argv[1], argv[2], as_json=as_json)
        if cmd == 'verify-format' and len(argv) == 3:
            return cmd_verify_format(argv[1], argv[2])
    except ValueError as e:
        print('ERROR: %s' % e)
        return 2
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
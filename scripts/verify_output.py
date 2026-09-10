#!/usr/bin/env python3
"""verify_output.py - the delivery gate. Exit 0 only if EVERY gate passes.

Usage:
  verify_output.py <tailored.docx> <keywords.txt> [--template <path>]
                   [--pdf <path>] [--json]

Gates:
  ats_audit         9-point ATS audit (with owner name from config)
  format_preserved  output preserves the template byte-for-byte except document.xml
  keyword_coverage  every JD keyword present
  pdf_text_layer    (with --pdf) name extracts from the PDF text layer
  page_limit        (with --pdf) page count within config max_pages

keywords.txt: comma-separated keywords (or a file containing them).
--template defaults to the config template; the config file is the single
owner of paths and limits (~/.config/resume-tailoring/config.json).

This script is deliberately the ONE definition of "output is good" - the skill
workflow calls it before delivery, and the eval harness uses it as the grader.
"""
import json
import os
import subprocess
import sys
import pathlib

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from docx_toolkit import load_config  # noqa: E402


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    docx, kw_arg = args[0], args[1]

    cfg = load_config()
    name = cfg.get('owner_name', 'Test Owner')
    max_pages = int(cfg.get('max_pages', 2))
    template = cfg.get('template')
    if '--template' in args:
        template = args[args.index('--template') + 1]
    pdf = args[args.index('--pdf') + 1] if '--pdf' in args else None
    as_json = '--json' in args

    if os.path.isfile(kw_arg):
        keywords = open(kw_arg).read().strip()
    else:
        keywords = kw_arg

    gates = {}

    rc, out = run(['python3', str(SCRIPTS / 'docx_toolkit.py'), 'audit', docx,
                   '--name', name, '--json'])
    if rc == 0 and out:
        try:
            gates['ats_audit'] = {'passed': json.loads(out)['passed'],
                                  'output': '%d checks' % len(json.loads(out)['checks'])}
        except json.JSONDecodeError:
            gates['ats_audit'] = {'passed': False, 'output': 'unparseable audit output'}
    else:
        gates['ats_audit'] = {'passed': False, 'output': out[-300:]}

    if template:
        rc, out = run(['python3', str(SCRIPTS / 'docx_toolkit.py'),
                       'verify-format', docx, template])
        gates['format_preserved'] = {'passed': rc == 0, 'output': out.splitlines()[0] if out else ''}

    rc, out = run(['python3', str(SCRIPTS / 'docx_toolkit.py'), 'coverage', docx,
                   keywords, '--json'])
    try:
        cov = json.loads(out)
        # --allow-missing "kw1, kw2": user-confirmed honest gaps (experience the
        # user does not have) do not block delivery - but they are always
        # reported, so a "pass" never silently hides an unmet JD term.
        allowed = {k.strip() for k in args[args.index('--allow-missing') + 1].split(',')} \
            if '--allow-missing' in args else set()
        missing = [k for k in cov['missing'] if k not in allowed]
        justified = [k for k in cov['missing'] if k in allowed]
        gates['keyword_coverage'] = {'passed': not missing,
                                     'output': '%d/%d present%s%s' % (
                                         cov['present'], cov['total'],
                                         (' | missing: ' + ', '.join(missing)) if missing else '',
                                         (' | justified gaps (user-confirmed): ' + ', '.join(justified))
                                         if justified else '')}
    except (json.JSONDecodeError, KeyError):
        gates['keyword_coverage'] = {'passed': rc == 0, 'output': out[-200:]}

    if pdf:
        rc, out = run(['swift', str(SCRIPTS / 'pdfcheck.swift'), pdf, name])
        gates['pdf_text_layer'] = {'passed': rc == 0,
                                   'output': 'probes found' if rc == 0 else out[-200:]}
        pages = 0
        for line in out.splitlines():
            if line.startswith('Pages:'):
                pages = int(line.split(':')[1].strip())
                break
        gates['page_limit'] = {'passed': 1 <= pages <= max_pages,
                               'output': 'pages=%d (max %d)' % (pages, max_pages)}

    ok = all(g['passed'] for g in gates.values())
    if as_json:
        print(json.dumps({'file': docx, 'passed': ok, 'gates': gates}, indent=2))
    else:
        for k, g in gates.items():
            print('%s  %-18s %s' % ('PASS' if g['passed'] else 'FAIL', k, g['output']))
        print('\n%s' % ('ALL GATES PASSED' if ok else 'DELIVERY BLOCKED - fix failures above'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
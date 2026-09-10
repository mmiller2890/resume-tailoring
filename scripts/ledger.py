#!/usr/bin/env python3
"""ledger.py - append to and render the JSONL ledger.

Ledger is append-only JSONL (one JSON object per line). The human-readable
ledger.md is generated from it - never edit ledger.md by hand; edit jsonl
and render.

Usage:
  ledger.py append <entry.json>         # entry is a JSON object (file or inline)
  ledger.py render                      # regenerate ledger.md from ledger.jsonl
"""
import json, os, sys, pathlib
sys.path.insert(0, os.path.dirname(__file__))
from docx_toolkit import load_config

def ledger_paths():
    cfg = load_config()
    root = cfg['corpus_root']
    return os.path.join(root, 'ledger.jsonl'), os.path.join(root, 'ledger.md')

def cmd_append(entry_arg):
    jpath, _ = ledger_paths()
    if os.path.isfile(entry_arg):
        entry = json.loads(open(entry_arg).read())
    else:
        entry = json.loads(entry_arg)
    os.makedirs(os.path.dirname(jpath), exist_ok=True)
    with open(jpath, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print('appended to %s' % jpath)
    return 0

def cmd_render():
    jpath, mpath = ledger_paths()
    if not os.path.exists(jpath):
        print('no ledger at %s - nothing to render' % jpath)
        return 0
    entries = [json.loads(l) for l in open(jpath) if l.strip()]
    lines = ['# Application Ledger\n',
             'Generated from `ledger.jsonl` - do not edit by hand; edit the JSONL and run `ledger.py render`.\n',
             '| Date | Company | Role | Coverage | Pages | Audit | Output | Notes |\n',
             '|------|---------|------|----------|-------|-------|--------|-------|\n']
    for e in entries:
        cov = e.get('coverage', '-') 
        if isinstance(cov, dict): cov = '%d/%d' % (cov.get('present','-'), cov.get('total','-'))
        lines.append('| %s | %s | %s | %s | %s | %s | `%s` | %s |\n' % (
            e.get('date',''), e.get('company',''), e.get('role',''), cov,
            e.get('pages',''), 'PASS' if e.get('audit_passed') else 'FAIL',
            e.get('output_docx',''), e.get('notes','')))
        if e.get('bullets_shipped'):
            lines.append('  *bullets shipped: %s*\n' % ', '.join(e['bullets_shipped']))
    open(mpath, 'w').write(''.join(lines))
    print('rendered %s (%d entries)' % (mpath, len(entries)))
    return 0

def main():
    if len(sys.argv) < 2: print(__doc__); return 2
    if sys.argv[1] == 'append': return cmd_append(sys.argv[2])
    if sys.argv[1] == 'render': return cmd_render()
    print(__doc__); return 2
if __name__ == '__main__': sys.exit(main())
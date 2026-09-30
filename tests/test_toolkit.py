#!/usr/bin/env python3
"""PII-free regression tests. No personal config, template, or corpus is read.

python3 tests/test_toolkit.py
RESUME_TAILORING_TEST_PDF=1 python3 tests/test_toolkit.py  # macOS + renderer
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT = ROOT / 'scripts/docx_toolkit.py'
VERIFY = ROOT / 'scripts/verify_output.py'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ET.register_namespace('w', W)

# Fictional candidates and confirmed facts, never derived from a real resume.
CASES = {
    'accounting': ('Staff Accountant', 'month-end close, reconciliations, Excel',
                   'Completed month-end close and account reconciliations.', ''),
    'nursing': ('Registered Nurse', 'patient care, medication administration, care plans',
                'Provided patient care and medication administration using care plans.',
                'Registered Nurse license (fictional, candidate-confirmed)'),
    'marketing': ('Marketing Specialist', 'campaign copywriting, analytics, engagement',
                  'Used campaign copywriting and analytics to improve engagement by 15%.', ''),
    'teaching': ('Elementary Teacher', 'lesson planning, assessment, differentiated instruction',
                 'Used lesson planning, assessment, and differentiated instruction.',
                 'Teaching license (fictional, candidate-confirmed)'),
    'it': ('IT Support Specialist', 'endpoint management, identity and access, troubleshooting',
           'Handled endpoint management, identity and access, and troubleshooting.', ''),
}


def fixture(path, domain='accounting', padding=0, two_pages=False):
    """Minimal real DOCX; return semantic paragraph indices, not owner offsets."""
    role, skills, bullet, credential = CASES[domain]
    document = ET.Element(f'{{{W}}}document')
    body = ET.SubElement(document, f'{{{W}}}body')
    indices = {}

    def paragraph(key, texts, is_bullet=False):
        indices[key] = len(body)
        p = ET.SubElement(body, f'{{{W}}}p')
        if is_bullet:
            props = ET.SubElement(p, f'{{{W}}}pPr')
            ET.SubElement(props, f'{{{W}}}pStyle', {f'{{{W}}}val': 'ListBullet'})
            num = ET.SubElement(props, f'{{{W}}}numPr')
            ET.SubElement(num, f'{{{W}}}ilvl', {f'{{{W}}}val': '0'})
            ET.SubElement(num, f'{{{W}}}numId', {f'{{{W}}}val': '7'})
        for i, text in enumerate(texts):
            run = ET.SubElement(p, f'{{{W}}}r')
            if len(texts) == 2 and i == 0:
                ET.SubElement(ET.SubElement(run, f'{{{W}}}rPr'), f'{{{W}}}b')
            ET.SubElement(run, f'{{{W}}}t', {'{http://www.w3.org/XML/1998/namespace}space': 'preserve'}).text = text

    paragraph('name', ['Test Candidate'])
    paragraph('contact', ['candidate@example.invalid'])
    for i in range(padding):
        paragraph(f'padding{i}', [''])
    paragraph('summary_heading', ['PROFESSIONAL SUMMARY'])
    paragraph('summary', [f'{role} with documented professional experience.'])
    paragraph('experience_heading', ['PROFESSIONAL EXPERIENCE'])
    paragraph('employer', ['Fictional Employer'])
    paragraph('title', [role, '   |   Jan 2020 - Present'])
    paragraph('bullet', [bullet], is_bullet=True)
    paragraph('skills_heading', ['SKILLS'])
    paragraph('skills', ['Professional Practice: ', skills])
    if credential:
        paragraph('credential', [credential])
    paragraph('education_heading', ['EDUCATION'])
    paragraph('education', ['Fictional Institution | Relevant qualification, Graduated 2019'])
    if two_pages:
        page_break = ET.SubElement(ET.SubElement(body, f'{{{W}}}p'), f'{{{W}}}r')
        ET.SubElement(page_break, f'{{{W}}}br', {f'{{{W}}}type': 'page'})
        paragraph('second_page', ['Additional fictional professional evidence.'])
    section = ET.SubElement(body, f'{{{W}}}sectPr')
    ET.SubElement(section, f'{{{W}}}pgSz', {f'{{{W}}}w': '12240', f'{{{W}}}h': '15840'})
    ET.SubElement(section, f'{{{W}}}pgMar', {f'{{{W}}}top': '720', f'{{{W}}}bottom': '720',
                                         f'{{{W}}}left': '720', f'{{{W}}}right': '720'})
    entries = {
        '[Content_Types].xml': '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>''',
        '_rels/.rels': '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>''',
        'word/_rels/document.xml.rels': '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>''',
        'word/styles.xml': f'''<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/></w:style></w:styles>''',
        'word/numbering.xml': f'''<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="4"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="\u25cf"/></w:lvl></w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="4"/></w:num></w:numbering>''',
        'word/document.xml': ET.tostring(document, encoding='utf-8', xml_declaration=True),
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return indices


def rewrite(source, destination, replacements):
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(destination, 'w') as dst:
        for entry in src.infolist():
            dst.writestr(entry, replacements.get(entry.filename, src.read(entry.filename)))
        for name, data in replacements.items():
            if name not in src.namelist():
                dst.writestr(name, data)


class PublicGuidanceTests(unittest.TestCase):
    def test_no_owner_or_it_only_mandates(self):
        skill = (ROOT / 'SKILL.md').read_text()
        for mandate in ('high-volume employee support, endpoint management',
                        'Represent healthcare employer experience as healthcare IT',
                        'Every new resume needs a concise AI', '2-page discipline',
                        'including any instinct to police truthfulness'):
            with self.subTest(mandate=mandate):
                self.assertNotIn(mandate, skill)

    def test_profile_driven_scope_and_evidence(self):
        skill = (ROOT / 'SKILL.md').read_text().lower()
        for phrase in ('any profession', 'target role', 'do not invent', 'licenses', 'max_pages'):
            self.assertIn(phrase, skill)

    def test_ai_is_optional(self):
        self.assertIn('AI is optional', (ROOT / 'SKILL.md').read_text())

    def test_evals_cover_non_it_and_it_without_placeholder_jds(self):
        evals = json.loads((ROOT / 'evals/evals.json').read_text())['evals']
        for field in ('accountant', 'nurse', 'marketing', 'teacher', 'IT support'):
            self.assertTrue(any(field.lower() in case['prompt'].lower() for case in evals), field)
        self.assertFalse(any('[paste]' in case['prompt'] for case in evals))

    def test_smoke_tests_do_not_read_personal_config_or_fixed_indices(self):
        smoke = (ROOT / 'scripts/smoke_test.sh').read_text()
        self.assertNotIn('TEMPLATE=', smoke)
        self.assertNotIn('"54":', smoke)
        self.assertIn('test_toolkit.py', smoke)


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='resume toolkit test ')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / 'master.docx'
        self.indices = fixture(self.source)
        self.config = self.work / 'config.json'
        self.config.write_text(json.dumps({'corpus_root': str(self.work), 'template': str(self.source),
                                          'owner_name': 'Test Candidate', 'max_pages': 1}))
        self.env = dict(os.environ, RESUME_TAILORING_CONFIG=str(self.config))
        self.output = self.work / 'resume.docx'

    def run_script(self, script, *args, expected=0):
        proc = subprocess.run([sys.executable, str(script), *map(str, args)],
                              cwd=self.work, env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, expected, (proc.stdout + proc.stderr)[-2500:])
        return proc.stdout

    def apply(self, spec, output=None, expected=0, dry_run=False):
        edits = self.work / 'edits.json'
        edits.write_text(json.dumps(spec))
        args = ['apply', self.source, edits, output or self.output]
        if dry_run:
            args.append('--dry-run')
        return self.run_script(TOOLKIT, *args, expected=expected)

    def audit(self, path, expected=0):
        return json.loads(self.run_script(TOOLKIT, 'audit', path, '--name', 'Test Candidate',
                                          '--json', expected=expected))

    def test_fixture_audits_clean(self):
        self.assertTrue(self.audit(self.source)['passed'])

    def test_relative_output_and_source_unchanged(self):
        before = (hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source.stat().st_mtime_ns)
        self.apply({'set_text': {str(self.indices['summary']): 'Accounting professional.'}}, 'relative.docx')
        self.assertTrue((self.work / 'relative.docx').exists())
        self.assertEqual(before, (hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source.stat().st_mtime_ns))

    def test_dry_run_succeeds_without_writing(self):
        out = self.apply({'set_text': {str(self.indices['summary']): 'Accounting professional.'}}, dry_run=True)
        self.assertIn('DRY RUN', out)
        self.assertFalse(self.output.exists())

    def test_contradictory_spec_rejected(self):
        i = self.indices['bullet']
        self.apply({'set_text': {str(i): 'Changed'}, 'remove_paragraphs': [i]}, expected=2)
        self.assertFalse(self.output.exists())

    def test_non_ascii_rejected(self):
        self.apply({'set_text': {str(self.indices['summary']): 'Smart dash \u2014'}}, expected=2)
        self.assertFalse(self.output.exists())

    def test_non_bullet_clone_rejected(self):
        self.apply({'clone_bullet_after': {str(self.indices['summary']): 'Changed'}}, expected=2)
        self.assertFalse(self.output.exists())

    def test_bullet_clone_with_nondefault_numbering(self):
        self.apply({'clone_bullet_after': {str(self.indices['bullet']): 'Prepared financial reports.'}})
        self.run_script(TOOLKIT, 'verify-format', self.output, self.source)
        self.assertTrue(self.audit(self.output)['passed'])
        with zipfile.ZipFile(self.output) as zf:
            self.assertEqual(zf.read('word/document.xml').count(b'<w:numId w:val="7"'), 2)

    def test_two_run_nontechnical_category_operations(self):
        i = str(self.indices['skills'])
        self.apply({'set_skills_line': {i: ['Financial Practice: ', 'reconciliations, Excel']},
                    'add_skills_line_after': {i: ['Communication: ', 'financial reporting']}})
        self.run_script(TOOLKIT, 'verify-format', self.output, self.source)
        self.assertTrue(self.audit(self.output)['passed'])
        with zipfile.ZipFile(self.output) as zf:
            document = ET.fromstring(zf.read('word/document.xml'))
        paragraphs = [''.join(p.itertext()) for p in document.find(f'{{{W}}}body').findall(f'{{{W}}}p')]
        self.assertEqual(paragraphs[int(i)], 'Financial Practice: reconciliations, Excel')
        self.assertEqual(paragraphs.count('Communication: financial reporting'), 1)
        self.assertEqual(len(paragraphs), len(self.indices) + 1)

    def test_icon_bullet_rejected(self):
        with zipfile.ZipFile(self.source) as zf:
            numbering = zf.read('word/numbering.xml').decode().replace('\u25cf', '\uf0e0')
        rewrite(self.source, self.output, {'word/numbering.xml': numbering.encode()})
        check = next(c for c in self.audit(self.output, expected=1)['checks'] if c['id'] == '4')
        self.assertFalse(check['passed'])

    def test_word_native_bullet_accepted(self):
        with zipfile.ZipFile(self.source) as zf:
            numbering = zf.read('word/numbering.xml').decode().replace('<w:lvlText w:val="\u25cf"/>',
                '<w:lvlText w:val="\uf0b7"/><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr>')
        self.assertIn('Symbol', numbering)
        rewrite(self.source, self.output, {'word/numbering.xml': numbering.encode()})
        self.assertTrue(self.audit(self.output)['passed'])

    def test_header_contact_rejected(self):
        rewrite(self.source, self.output, {'word/header1.xml':
            f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>candidate@example.invalid</w:t></w:r></w:p></w:hdr>'.encode()})
        check = next(c for c in self.audit(self.output, expected=1)['checks'] if c['id'] == '4b')
        self.assertFalse(check['passed'])

    def test_education_single_date_accepted(self):
        self.apply({'set_text': {str(self.indices['education']): 'Fictional Institution | Graduated 2019'}})
        self.assertTrue(self.audit(self.output)['passed'])

    def test_ambiguous_employment_date_rejected(self):
        self.apply({'set_skills_line': {str(self.indices['title']): ['Staff Accountant', ' | 2020-21']}})
        check = next(c for c in self.audit(self.output, expected=1)['checks'] if c['id'] == '6')
        self.assertFalse(check['passed'])

    def test_format_drift_rejected(self):
        with zipfile.ZipFile(self.source) as zf:
            styles = zf.read('word/styles.xml') + b'\n<!-- drift -->'
        rewrite(self.source, self.output, {'word/styles.xml': styles})
        self.run_script(TOOLKIT, 'verify-format', self.output, self.source, expected=1)

    def test_missing_keyword_reported(self):
        coverage = json.loads(self.run_script(TOOLKIT, 'coverage', self.source,
                                             'reconciliations, absent keyword', '--json', expected=1))
        self.assertEqual(coverage['missing'], ['absent keyword'])

    def test_overwrite_template_rejected(self):
        before = self.source.read_bytes()
        self.apply({'set_text': {str(self.indices['summary']): 'Changed'}}, self.source, expected=2)
        self.assertEqual(self.source.read_bytes(), before)

    def test_unsupported_run_shape_rejected_without_output(self):
        self.apply({'set_text': {str(self.indices['title']): 'Changed'}}, expected=2)
        self.assertFalse(self.output.exists())

    def test_docx_gates_for_five_professions(self):
        for padding, (domain, (role, skills, bullet, credential)) in enumerate(CASES.items()):
            with self.subTest(domain=domain):
                self.indices = fixture(self.source, domain, padding)
                before = self.source.read_bytes()
                mapping = self.run_script(TOOLKIT, 'extract', self.source)
                self.assertIn(role, mapping)
                summary = f'{role} focused on {skills}.'
                contribution = f'Key contribution: {bullet}'
                self.apply({'set_text': {str(self.indices['summary']): summary,
                                         str(self.indices['bullet']): contribution}})
                with zipfile.ZipFile(self.output) as zf:
                    document = ET.fromstring(zf.read('word/document.xml'))
                paragraphs = [''.join(p.itertext()) for p in document.find(f'{{{W}}}body').findall(f'{{{W}}}p')]
                self.assertEqual(paragraphs[self.indices['summary']], summary)
                self.assertEqual(paragraphs[self.indices['bullet']], contribution)
                gates = json.loads(self.run_script(VERIFY, self.output, skills, '--json'))
                self.assertTrue(gates['passed'])
                self.assertEqual(set(gates['gates']), {'ats_audit', 'format_preserved', 'keyword_coverage'})
                self.assertEqual(before, self.source.read_bytes())
                if credential:
                    self.assertIn(credential, self.run_script(TOOLKIT, 'extract', self.output))
                if domain != 'it':
                    with zipfile.ZipFile(self.output) as zf:
                        text = zf.read('word/document.xml').decode()
                    for unsupported in ('Okta', 'helpdesk', 'AI-assisted'):
                        self.assertNotIn(unsupported, text)

    def test_explicit_gap_reporting_does_not_insert_claim(self):
        self.apply({'set_text': {str(self.indices['summary']): 'Accounting professional.'}})
        blocked = json.loads(self.run_script(VERIFY, self.output, 'reconciliations, QuickBooks', '--json', expected=1))
        self.assertFalse(blocked['passed'])
        allowed = json.loads(self.run_script(VERIFY, self.output, 'reconciliations, QuickBooks', '--allow-missing',
                                             'QuickBooks', '--json'))
        self.assertTrue(allowed['passed'])
        self.assertIn('justified gaps', allowed['gates']['keyword_coverage']['output'])
        self.assertNotIn('QuickBooks', self.run_script(TOOLKIT, 'extract', self.output))

    @unittest.skipUnless(os.environ.get('RESUME_TAILORING_TEST_PDF') == '1', 'enable --pdf for renderer/PDFKit tests')
    def test_full_pdf_delivery_for_five_professions(self):
        for padding, (domain, (role, skills, bullet, _)) in enumerate(CASES.items()):
            with self.subTest(domain=domain):
                self.indices = fixture(self.source, domain, padding)
                self.apply({'set_text': {str(self.indices['summary']): f'{role} focused on {skills}.',
                                         str(self.indices['bullet']): bullet}})
                pdf = self.work / f'{domain}.pdf'
                proc = subprocess.run(['bash', str(ROOT / 'scripts/render_pdf.sh'), str(self.output), str(pdf)],
                                      env=self.env, capture_output=True, text=True, timeout=120)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                report = json.loads(self.run_script(VERIFY, self.output, skills, '--pdf', pdf, '--json'))
                self.assertTrue(report['passed'])
                self.assertEqual(len(report['gates']), 5)
                self.assertIn('max 1', report['gates']['page_limit']['output'])
                # The same two-page resume is rejected at 1 and accepted at 2.
                if domain == 'accounting':
                    self.indices = fixture(self.source, domain, padding, two_pages=True)
                    self.apply({'set_text': {str(self.indices['summary']): f'{role} focused on {skills}.'}})
                    two_page_pdf = self.work / 'two-page.pdf'
                    proc = subprocess.run(['bash', str(ROOT / 'scripts/render_pdf.sh'), str(self.output), str(two_page_pdf)],
                                          env=self.env, capture_output=True, text=True, timeout=120)
                    self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                    blocked = json.loads(self.run_script(VERIFY, self.output, skills, '--pdf', two_page_pdf, '--json', expected=1))
                    self.assertFalse(blocked['gates']['page_limit']['passed'])
                    self.assertIn('pages=2 (max 1)', blocked['gates']['page_limit']['output'])
                    cfg = json.loads(self.config.read_text())
                    cfg['max_pages'] = 2
                    self.config.write_text(json.dumps(cfg))
                    allowed = json.loads(self.run_script(VERIFY, self.output, skills, '--pdf', two_page_pdf, '--json'))
                    self.assertTrue(allowed['passed'])
                    self.assertIn('pages=2 (max 2)', allowed['gates']['page_limit']['output'])
                    cfg['max_pages'] = 1
                    self.config.write_text(json.dumps(cfg))


if __name__ == '__main__':
    unittest.main(verbosity=2)

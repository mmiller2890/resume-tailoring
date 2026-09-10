#!/bin/bash
# smoke_test.sh - full regression for the resume-tailoring toolkit.
#
# Run this before trusting the skill after ANY change to docx_toolkit.py,
# and whenever a fresh session wants to validate the toolchain. Everything
# here was learned the hard way: each fixture reproduces a real bug that
# once shipped (a check that could not fail, a header-blind audit, a
# false-positive date check). If any step fails, do not tailor resumes.
#
# Never modifies the template or any delivered file - all outputs go to a
# temp directory that is removed on exit.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TK="$HERE/docx_toolkit.py"
FAILURES=0
TESTS=0

pass() { TESTS=$((TESTS+1)); echo "PASS  $1"; }
fail() { TESTS=$((TESTS+1)); FAILURES=$((FAILURES+1)); echo "FAIL  $1"; }

# resolve template from config
TEMPLATE="$(python3 "$TK" config 2>/dev/null | awk '/^template:/ {print $2}')"
if [ -z "$TEMPLATE" ] || [ ! -f "$TEMPLATE" ]; then
  echo "FAIL  cannot resolve template from config - run docx_toolkit.py config"
  exit 1
fi
NAME="$(python3 "$TK" config 2>/dev/null | awk '/^owner_name:/ {$1=""; sub(/^ /,""); print}')"
NAME="${NAME:-Test Owner}"

WORK="$(mktemp -d /tmp/resume-smoke.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

echo "== template: $TEMPLATE =="
echo "== workdir: $WORK =="
echo

# 1. template audits clean (with name)
python3 "$TK" audit "$TEMPLATE" --name "$NAME" > "$WORK/audit_t.txt" 2>&1
grep -q "checks passed" "$WORK/audit_t.txt" && \
  [ "$(tail -1 "$WORK/audit_t.txt" | cut -d/ -f1)" -ge 10 ] && \
  pass "template audit clean" || fail "template audit clean"

# 2. relative output path lands where the caller is (the F1 data-loss bug)
mkdir -p "$WORK/rel" && cd "$WORK/rel"
echo '{"set_text":{"3":"smoke test"}}' > e.json
python3 "$TK" apply "$TEMPLATE" e.json out.docx > /dev/null 2>&1
[ -f "$WORK/rel/out.docx" ] && pass "relative-path apply writes to caller dir" \
  || fail "relative-path apply writes to caller dir"
cd "$HERE"

# 3. dry-run writes nothing
python3 "$TK" apply "$TEMPLATE" "$WORK/rel/e.json" "$WORK/dr.docx" --dry-run > /dev/null 2>&1
[ ! -f "$WORK/dr.docx" ] && pass "dry-run writes no file" || fail "dry-run writes no file"

# 4. bad spec: edit AND remove same index -> error, no output
echo '{"set_text":{"9":"x"},"remove_paragraphs":[9]}' > "$WORK/bad1.json"
python3 "$TK" apply "$TEMPLATE" "$WORK/bad1.json" "$WORK/bad1.docx" > /dev/null 2>&1
[ ! -f "$WORK/bad1.docx" ] && pass "contradictory spec rejected" || fail "contradictory spec rejected"

# 5. non-ASCII spec -> error, no output
python3 -c "import json;json.dump({'set_text':{'3':'dash \u2014'}},open('$WORK/bad2.json','w'))"
python3 "$TK" apply "$TEMPLATE" "$WORK/bad2.json" "$WORK/bad2.docx" > /dev/null 2>&1
[ ! -f "$WORK/bad2.docx" ] && pass "non-ASCII text rejected" || fail "non-ASCII text rejected"

# 6. clone_bullet_after on non-bullet -> error, no output
echo '{"clone_bullet_after":{"2":"x"}}' > "$WORK/bad3.json"
python3 "$TK" apply "$TEMPLATE" "$WORK/bad3.json" "$WORK/bad3.docx" > /dev/null 2>&1
[ ! -f "$WORK/bad3.docx" ] && pass "non-bullet clone rejected" || fail "non-bullet clone rejected"

# 7. clean apply passes verify-format
python3 "$TK" apply "$TEMPLATE" "$WORK/rel/e.json" "$WORK/good.docx" > /dev/null 2>&1
python3 "$TK" verify-format "$WORK/good.docx" "$TEMPLATE" > /dev/null 2>&1
[ $? -eq 0 ] && pass "clean apply preserves format" || fail "clean apply preserves format"

# 8. F2 fixture: Wingdings arrow glyph in numbering.xml MUST fail audit check 4
mkdir -p "$WORK/f2" && unzip -q "$TEMPLATE" -d "$WORK/f2/x"
python3 -c "
p='$WORK/f2/x/word/numbering.xml'; s=open(p,encoding='utf-8').read()
s=s.replace('<w:lvlText w:val=\"\u25cf\"/>','<w:lvlText w:val=\"\uf0e0\"/>')
open(p,'w',encoding='utf-8').write(s)"
(cd "$WORK/f2/x" && zip -qrX ../icon.docx '[Content_Types].xml' _rels docProps word) > /dev/null 2>&1
python3 "$TK" audit "$WORK/f2/icon.docx" 2>/dev/null | grep -q "FAIL \[4\]" && \
  pass "icon bullets detected (F2 regression)" || fail "icon bullets detected (F2 regression)"

# 9. Word-native bullet (Symbol font + U+F0B7) MUST pass check 4 (false-positive fix)
mkdir -p "$WORK/native" && unzip -q "$TEMPLATE" -d "$WORK/native/x"
python3 -c "
p='$WORK/native/x/word/numbering.xml'; s=open(p,encoding='utf-8').read()
s=s.replace('<w:lvlText w:val=\"\u25cf\"/>','<w:lvlText w:val=\"\uf0b7\"/><w:rPr><w:rFonts w:ascii=\"Symbol\" w:hAnsi=\"Symbol\"/></w:rPr>')
open(p,'w',encoding='utf-8').write(s)"
(cd "$WORK/native/x" && zip -qrX ../native.docx '[Content_Types].xml' _rels docProps word) > /dev/null 2>&1
python3 "$TK" audit "$WORK/native/native.docx" 2>/dev/null | grep -q "PASS \[4\]" && \
  pass "Word-native Symbol bullets pass (no false positive)" || \
  fail "Word-native Symbol bullets pass (no false positive)"

# 10. F3 fixture: contact info in header MUST fail audit check 4b
mkdir -p "$WORK/f3" && unzip -q "$TEMPLATE" -d "$WORK/f3/x"
printf '%s' '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Test Owner - Senior Support Engineer</w:t></w:r></w:p></w:hdr>' > "$WORK/f3/x/word/header1.xml"
(cd "$WORK/f3/x" && zip -qrX ../hdr.docx '[Content_Types].xml' _rels docProps word) > /dev/null 2>&1
python3 "$TK" audit "$WORK/f3/hdr.docx" 2>/dev/null | grep -q "FAIL \[4b\]" && \
  pass "header contact info detected (F3 regression)" || fail "header contact info detected (F3 regression)"

# 11. F4 fixture: single date in education line MUST NOT fail the date check
echo '{"set_text":{"54":"State University | Cybersecurity Bootcamp, Graduated 20XX"}}' > "$WORK/f4.json"
python3 "$TK" apply "$TEMPLATE" "$WORK/f4.json" "$WORK/f4.docx" > /dev/null 2>&1
python3 "$TK" audit "$WORK/f4.docx" 2>/dev/null | grep -q "PASS \[6\]" && \
  pass "education single date not flagged (F4 false-positive fix)" || \
  fail "education single date not flagged (F4 false-positive fix)"

# 12. format drift MUST be rejected by verify-format
mkdir -p "$WORK/drift" && unzip -q "$TEMPLATE" -d "$WORK/drift/x"
printf '\n<!-- drift -->' >> "$WORK/drift/x/word/styles.xml"
(cd "$WORK/drift/x" && zip -qrX ../drifted.docx '[Content_Types].xml' _rels docProps word) > /dev/null 2>&1
python3 "$TK" verify-format "$WORK/drift/drifted.docx" "$TEMPLATE" > /dev/null 2>&1
[ $? -ne 0 ] && pass "format drift rejected" || fail "format drift rejected"

# 13. coverage detects a missing keyword
python3 "$TK" coverage "$WORK/good.docx" "helpdesk, DEFINITELY_NOT_PRESENT_KW" > /dev/null 2>&1
[ $? -ne 0 ] && pass "coverage flags missing keyword" || fail "coverage flags missing keyword"

echo
if [ $FAILURES -eq 0 ]; then
  echo "SMOKE TEST: $TESTS/$TESTS passed"
  exit 0
else
  echo "SMOKE TEST: $((TESTS-FAILURES))/$TESTS passed - FIX BEFORE TAILORING"
  exit 1
fi
#!/bin/bash
# render_pdf.sh - convert a docx to PDF. Engine order:
#   1. LibreOffice headless (primary - deterministic, no GUI app needed)
#   2. mammoth + weasyprint (fallback - approximate pagination, verify page count!)
# Word GUI export remains the manual gold standard: open in Word, File > Save As > PDF.
#
# History (2026-08-29): the previous primary engine was Word via AppleScript. It
# worked for a full tailoring session, then a render attempt hung, a force-kill
# followed, and this machine's Word install never handled scripted `save as`
# again (basic queries kept working; every save form returned -1708 or hung;
# clearing caches/saved-state and stripping quarantine did not heal it). Do not
# re-add the Word AppleScript path without reinstalling Word first.
#
# Hard-won lesson kept from that failure: quarantined docx files open in Word's
# Protected View and block scripting even when Word is healthy - always strip
# com.apple.quarantine before handing any docx to a converter or to the user.

set -euo pipefail

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "Usage: render_pdf.sh <input.docx> <output.pdf> [--force]" >&2
  exit 2
fi

DOCX="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$1")"
PDF="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$2")"

if [ ! -f "$DOCX" ]; then
  echo "ERROR: input not found: $DOCX" >&2
  exit 1
fi

# GUARD: never silently overwrite a PDF that is newer than its docx - that means
# the user probably re-exported it manually (e.g. from Word, the gold standard).
# Use --force to overwrite anyway.
if [ "${3:-}" != "--force" ] && [ -f "$PDF" ] && [ "$PDF" -nt "$DOCX" ]; then
  echo "ERROR: $PDF is newer than $DOCX - it looks like a manual export. Not overwriting."
  echo "       Re-run with --force to overwrite, or delete the PDF first." >&2
  exit 1
fi

mkdir -p "$(dirname "$PDF")"

# quarantine strip: never let a docx open in Protected View (breaks scripting,
# annoys the user in the GUI)
xattr -d com.apple.quarantine "$DOCX" 2>/dev/null || true

# ---- primary: LibreOffice headless ----
# Paginates this template within ~1 line of Word (Calibri -> Carlito metric
# clone). If fonts change or the template does, re-verify pages with pdfcheck.
if command -v soffice >/dev/null 2>&1; then
  OUTDIR="$(mktemp -d)"
  if soffice --headless --convert-to pdf --outdir "$OUTDIR" "$DOCX" >/dev/null 2>&1; then
    PRODUCED="$OUTDIR/$(basename "${DOCX%.docx}").pdf"
    if [ -s "$PRODUCED" ]; then
      mv "$PRODUCED" "$PDF"
      rm -rf "$OUTDIR"
      echo "rendered (LibreOffice): $PDF ($(stat -f%z "$PDF") bytes)"
      exit 0
    fi
  fi
  rm -rf "$OUTDIR"
  echo "WARN: LibreOffice conversion failed - falling back to weasyprint" >&2
fi

# ---- fallback: mammoth + weasyprint ----
# Approximate layout (flat HTML, no Word layout engine). Always verify the page
# count with pdfcheck/verify_output.py when this engine produces the file.
python3 - "$DOCX" "$PDF" << 'PYEOF'
import sys, pathlib
import mammoth
from weasyprint import HTML
docx, pdf = sys.argv[1], sys.argv[2]
with open(docx, "rb") as f:
    body = mammoth.convert_to_html(f).value
html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: letter; margin: 0.55in 0.7in; }}
body {{ font-family: Calibri, Helvetica, Arial, sans-serif; font-size: 9.6pt; line-height: 1.22; color: #222; }}
p {{ margin: 1.5pt 0; }}
ul {{ margin: 1.5pt 0 1.5pt 15pt; padding: 0; }}
li {{ margin-bottom: 0.5pt; }}
</style></head><body>{body}</body></html>"""
HTML(string=html).write_pdf(pdf)
print(f"rendered (weasyprint fallback): {pdf}")
PYEOF

# never trust a claimed success: verify the artifact exists and is substantial
if [ ! -s "$PDF" ]; then
  echo "ERROR: PDF not created or empty: $PDF" >&2
  exit 1
fi
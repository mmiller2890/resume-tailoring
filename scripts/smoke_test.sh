#!/bin/bash
# Self-contained, PII-free regressions. Does not use candidate config or files.
# --pdf also exercises rendering/PDFKit and configured page limits on macOS.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ $# -gt 1 ]; then
  echo "Usage: smoke_test.sh [--pdf]" >&2
  exit 2
fi
case "${1:-}" in
  "") unset RESUME_TAILORING_TEST_PDF ;;
  --pdf) export RESUME_TAILORING_TEST_PDF=1 ;;
  *) echo "Usage: smoke_test.sh [--pdf]" >&2; exit 2 ;;
esac
exec python3 "$HERE/../tests/test_toolkit.py"

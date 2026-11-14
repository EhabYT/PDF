#!/usr/bin/env bash
# Verify the system-level dependencies that cannot be installed by pip/npm.
# OCR (Smart Document Naming) needs tesseract plus the language packs; upload
# sniffing needs libmagic. Missing tools used to fail silently at job time, so
# fail loudly here instead.
set -uo pipefail

missing=()

need() { command -v "$1" >/dev/null 2>&1 || missing+=("$1"); }
need tesseract
need python3

if command -v tesseract >/dev/null 2>&1; then
  langs=$(tesseract --list-langs 2>/dev/null | tail -n +2 | tr '\n' ' ')
  for lang in ${OCR_LANGUAGES_CHECK:-deu eng ara}; do
    case " $langs " in *" $lang "*) ;; *) missing+=("tesseract-lang:$lang") ;; esac
  done
fi

case "$(uname -s)" in
  Linux)
    if command -v python3 >/dev/null 2>&1; then
      python3 -c "import magic" 2>/dev/null || python3 -c "import ctypes; ctypes.CDLL('libmagic.so.1')" 2>/dev/null || missing+=("libmagic1")
    fi
    ;;
esac

if [ ${#missing[@]} -eq 0 ]; then
  echo "preflight: OK (tesseract + deu/eng/ara, libmagic present)"
  exit 0
fi

echo "preflight: MISSING system dependencies: ${missing[*]}" >&2
echo "" >&2
echo "Install them first (these are OS packages, not pip/npm):" >&2
case "$(uname -s)" in
  Darwin) echo "  brew install tesseract tesseract-lang libmagic" >&2 ;;
  *)      echo "  Debian/Ubuntu: sudo apt-get install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-ara libmagic1" >&2
          echo "  Fedora/RHEL:   sudo dnf install -y tesseract tesseract-langpack-deu tesseract-langpack-ara file-libs" >&2
          echo "  Alpine:        sudo apk add tesseract-ocr tesseract-ocr-data-deu tesseract-ocr-data-ara file" >&2 ;;
esac
echo "" >&2
echo "Without tesseract the app still scans and enhances, but Smart Document" >&2
echo "Naming/OCR will fail for each document. Set ALLOW_MISSING_OCR=1 to continue." >&2
[ "${ALLOW_MISSING_OCR:-0}" = "1" ] && exit 0
exit 1

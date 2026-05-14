#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

.venv/bin/pip install -q pyinstaller

rm -rf build dist

.venv/bin/pyinstaller SPVT-Admin.spec --noconfirm

echo ""
echo "Готово: dist/SPVT Admin.app"
open "dist/SPVT Admin.app" 2>/dev/null || true

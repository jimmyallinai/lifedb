#!/usr/bin/env bash
# Pre-publish personal-data scan (A1 feasibility report, section 4).
# Fails (exit 1) if any named personal identifier, private path, private
# infrastructure endpoint, or credential-shaped value appears anywhere in
# the repo (excluding this script itself and .git). Run before every push:
#   ./prepublish_scan.sh
set -u
cd "$(dirname "$0")"

PATTERNS=(
  '221209612'          # personal platform UID (douban)
  '2327384139'         # personal QQ number
  '525773142'          # family member QQ number
  'xhp861553'          # personal platform slug
  'jimmy\.session'     # private telegram session file name
  'moi_it_zametki'     # private channel name from personal notes
  '/home/hatch'        # private absolute home path
  '127\.0\.0\.1:19999' # private home-IP forward endpoint
  '127\.0\.0\.1:8792'  # private local retrieval service endpoint
  '(SESSDATA|dbcl2|uamtk|pt_key|bili_jct)=[A-Za-z0-9%_-]{16,}'  # credential values
)

fail=0
for pattern in "${PATTERNS[@]}"; do
  if command -v rg >/dev/null 2>&1; then
    hits=$(rg -n --hidden -g '!.git' -g '!prepublish_scan.sh' -e "$pattern" . 2>/dev/null)
  else
    hits=$(grep -rInE --exclude-dir=.git --exclude=prepublish_scan.sh -e "$pattern" . 2>/dev/null)
  fi
  if [ -n "$hits" ]; then
    echo "HIT [$pattern]"
    echo "$hits"
    fail=1
  fi
done

# No credential/session artifacts as files (names listed in .gitignore are
# ignore-rules, not files; this checks actual files on disk).
stray=$(find . -path ./.git -prune -o -type f \( -name '*_cookies.json' -o -name '*.session' -o -name 'token.txt' \) -print)
if [ -n "$stray" ]; then
  echo "STRAY credential-like files:"
  echo "$stray"
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "prepublish scan: clean (0 hits)"
else
  echo "prepublish scan: FAILED - do not publish"
fi
exit "$fail"

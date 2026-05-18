#!/bin/bash
set -euo pipefail

KEY="${POWERBI_EXPORT_KEY:?POWERBI_EXPORT_KEY не задан}"
BASE="http://127.0.0.1:8000"

echo "=== Users in DB ==="
sudo -u postgres psql -d spvt -c "SELECT id, username, full_name FROM users WHERE role='worker' ORDER BY id"

echo "=== Login worker3 ==="
TOKEN=$(curl -sS -X POST "$BASE/api/auth/login" -d "username=worker3&password=worker123" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "=== Submit test ==="
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/test/questions" > /tmp/q.json
python3 - <<'PY'
import json
data = json.load(open("/tmp/q.json"))
qs = data["questions"] if isinstance(data, dict) else data
answers = []
for q in qs:
    ans = q["options"][0]
    if q["text"].startswith("Имеете"):
        ans = "Нет"
    elif "высоте" in q["text"]:
        ans = q["options"][1]
    elif "несчастном" in q["text"]:
        ans = q["options"][1]
    elif q["text"].startswith("Допускается"):
        ans = "Нет"
    elif q["text"].startswith("Обязан"):
        ans = "Да"
    answers.append({"question_id": q["id"], "answer": ans})
json.dump({"answers": answers}, open("/tmp/submit.json", "w"), ensure_ascii=False)
print("answers:", len(answers))
PY
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @/tmp/submit.json "$BASE/api/test/submit"
echo

echo "=== CSV svodka (local) ==="
curl -sS "$BASE/api/export/public/k/$KEY/powerbi-svodka.csv"

echo
echo "=== CSV svodka (HTTPS) ==="
curl -sS "https://45-144-220-51.nip.io/api/export/public/k/$KEY/powerbi-svodka.csv"

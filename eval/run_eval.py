"""Usage: python eval/run_eval.py https://YOUR-APP.onrender.com
Runs eval/questions.json against /ask, checks answer_source, writes eval/results.md"""
import json
import sys
import time

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
questions = json.load(open("eval/questions.json"))
rows, passed, total = [], 0, 0

for q in questions:
    if q["question"].startswith("FILL"):
        print(f"#{q['id']} skipped (fill in the question first)")
        continue
    total += 1
    try:
        r = requests.post(f"{BASE}/ask", json={"question": q["question"], "session_id": q["session_id"]}, timeout=180)
        r.raise_for_status()
        d = r.json()
        ok = d["answer_source"] in q["expected_source"]
        trace = " > ".join(t.split(":")[0] for t in d["reasoning_trace"])
        srcs = ", ".join(sorted({c["doc"] for c in d["citations"]})) or ", ".join(w["url"][:40] for w in d["web_sources"]) or "-"
        rows.append((q["id"], q["category"], q["question"], "/".join(q["expected_source"]), d["answer_source"], "PASS" if ok else "FAIL", srcs, trace))
    except Exception as e:
        ok = False
        rows.append((q["id"], q["category"], q["question"], "/".join(q["expected_source"]), "ERROR", "FAIL", str(e)[:60], ""))
    passed += ok
    print(f"#{q['id']} [{q['category']}] -> {rows[-1][4]} {rows[-1][5]}")
    time.sleep(10)  # stay under free-tier rate limits

md = ["| # | Category | Question | Expected | Got | Result | Sources | Graph path |", "|---|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(str(x).replace("|", "/") for x in row) + " |" for row in rows]
md.append(f"\n**{passed}/{total} passed**")
open("eval/results.md", "w", encoding="utf-8").write("\n".join(md))
print(f"\n{passed}/{total} passed -> eval/results.md")

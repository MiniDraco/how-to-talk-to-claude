#!/usr/bin/env python3
"""
Rules extractor: paper abstracts -> actionable rules, in OUR words, with citations.

  python extract_rules.py --target 3000
  python extract_rules.py --report

Free:  runs entirely on the local Ollama (no key, no quota, no cloud).
Legal: copyright protects EXPRESSION, not ideas. We extract the idea and phrase it
       ourselves; a mechanical n-gram guard rejects any candidate that reuses the
       source's wording. Every rule keeps its DOI/arXiv id so claims stay checkable.

GPU note: this machine has a 1660 SUPER at index 0 and a 3060 at index 1. Ollama
must be pinned to index 1 or it silently falls back to CPU and runs ~10x slower.
"""
import argparse, hashlib, json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
_h = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").replace("http://", "").strip("/")
# OLLAMA_HOST is often set to a BIND address (0.0.0.0); that is not connectable.
_h = _h.replace("0.0.0.0", "127.0.0.1")
BASE = "http://" + (_h if ":" in _h else _h + ":11434")
# 8B fits the 3060 comfortably and runs ~3x faster than a 14B for this task.
PREFERRED = ["hermes3:8b", "dolphin-llama3", "aya-expanse", "qwen3", "qwen2.5:3b"]

# The seven control surfaces from MAP.md, so the DB indexes back onto the doc.
SURFACES = ["intent", "context", "persistence", "comprehension",
            "process", "verification", "termination"]

SYS = """You extract ACTIONABLE RULES for working with large language models from research abstracts.

Return STRICT JSON: {"rules":[{"rule":..., "mechanism":..., "surface":..., "confidence":0.0-1.0}]}

Hard requirements:
- "rule" is an imperative a practitioner can follow. Not a finding, not a summary.
  GOOD: "Sample several reasoning paths and take the majority answer."
  BAD:  "This paper studies self-consistency in chain-of-thought."
- "mechanism" states WHY it works in one clause. If you cannot state a mechanism, omit the rule.
- "surface" is exactly one of: intent, context, persistence, comprehension, process, verification, termination.
- WRITE IN YOUR OWN WORDS. Never copy a phrase of 6+ consecutive words from the abstract.
- If the abstract contains no transferable practitioner rule, return {"rules":[]}. That is a valid, common answer.
- At most 3 rules. Prefer 0 good rules over 3 padded ones.

The rule MUST be something a practitioner can DO when building with or prompting an LLM:
phrase a prompt, structure a workflow, choose a decoding strategy, set up an evaluation.
REJECT and return {"rules":[]} if the abstract only offers:
- policy, regulation, law, ethics or governance recommendations
- research methodology ("evaluate the effectiveness of X", "conduct empirical studies")
- results reporting with no transferable action ("X outperforms Y on benchmark Z")
- domain-specific science that merely uses a model (protein folding, clinical diagnosis,
  materials discovery). A protein language model is not a chatbot; its training tricks
  do not transfer to prompting."""

# Rules that slipped through the model's own filter. Mechanical backstop.
OFF_DOMAIN = re.compile(
    r"(protein|molecul|genom|proteom|clinical|patient|radiolog|tumou?r|drug discovery"
    r"|chemistr|materials science|crystall|astronom|seismic|weather forecast"
    r"|regulat|legislat|policymaker|policy maker|court|lawmaker|governance framework)", re.I)
# Non-anchored: advice aimed at RESEARCHERS, not at people building with an LLM.
META_ANY = re.compile(
    r"(research gap|further research|future (studies|research|work)|research communit"
    r"|advance the field|releas\w+ (your|the) (trained )?(model|dataset|code|weights)"
    r"|open[- ]sourc\w+ (your|the) (model|dataset)|we recommend that researchers"
    r"|call for more (research|study)|encourage researchers)", re.I)
META_RESEARCH = re.compile(
    r"^(evaluate the effectiveness|conduct(ing)? (an )?empirical|perform (an )?empirical"
    r"|investigate whether|study the impact|assess the performance|benchmark \w+ to"
    r"|further research|future work|this paper|the (present )?study)", re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS rules (
  id INTEGER PRIMARY KEY, rule TEXT, mechanism TEXT, category TEXT,
  source_kind TEXT, source_ref TEXT, source_title TEXT, confidence REAL,
  norm_hash TEXT UNIQUE, extracted_at TEXT);
CREATE TABLE IF NOT EXISTS done (ext_id TEXT PRIMARY KEY, n INTEGER, at TEXT);
CREATE INDEX IF NOT EXISTS ix_r_cat ON rules(category);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())


def words(s):
    return re.sub(r"\s+", " ", norm(s)).strip().split(" ")


def verbatim_overlap(rule, abstract, n=6):
    """True if the rule reuses n+ consecutive words from the source. Legal guard."""
    rw, aw = words(rule), words(abstract)
    if len(rw) < n:
        return False
    hay = " " + " ".join(aw) + " "
    return any(f" {' '.join(rw[i:i+n])} " in hay for i in range(len(rw) - n + 1))


def api(path, payload=None, timeout=180):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def pick_model():
    try:
        tags = api("/api/tags")
    except Exception as e:
        sys.exit(f"Ollama unreachable at {BASE}: {e}\n"
                 f"Start it pinned to the 3060:  CUDA_VISIBLE_DEVICES=1 ollama serve")
    names = [m["name"] for m in tags.get("models", [])]
    if not names:
        sys.exit("Ollama is up but has no models pulled.")
    for p in PREFERRED:
        for n in names:
            if n.startswith(p):
                return n
    return names[0]


def extract(model, title, abstract):
    r = api("/api/chat", {
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0.2, "num_gpu": 99, "num_ctx": 8192, "num_predict": 700},
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": f"TITLE: {title}\n\nABSTRACT: {abstract[:5000]}"}],
    })
    try:
        return json.loads(r["message"]["content"]).get("rules", []) or []
    except Exception:
        return []


def run(target, limit_papers):
    papers = sqlite3.connect(os.path.join(HERE, "papers.db"))
    rules = sqlite3.connect(os.path.join(HERE, "rules.db"))
    rules.executescript(SCHEMA)
    model = pick_model()
    have = rules.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    print(f"model={model}  rules={have:,}  target={target:,}", flush=True)

    done = {r[0] for r in rules.execute("SELECT ext_id FROM done")}
    rows = papers.execute("""
        SELECT ext_id, title, abstract, doi, arxiv_id, cited_by, src FROM papers
        WHERE abstract IS NOT NULL AND LENGTH(abstract) > 260
          AND (COALESCE(year,0) >= 2019 OR src='arxiv')
          AND (title LIKE '%language model%' OR title LIKE '%LLM%' OR title LIKE '%prompt%'
               OR title LIKE '%GPT%' OR title LIKE '%agent%' OR title LIKE '%in-context%'
               OR title LIKE '%chain-of-thought%' OR title LIKE '%code generation%'
               OR abstract LIKE '%large language model%' OR abstract LIKE '%prompting%')
        ORDER BY COALESCE(cited_by,0) DESC, year DESC LIMIT ?""", (limit_papers,)).fetchall()
    print(f"{len(rows):,} candidate abstracts, {len(done):,} already processed", flush=True)

    kept = rejected = 0
    t0 = time.time()
    for i, (ext_id, title, abstract, doi, arxiv_id, cited, src) in enumerate(rows):
        if ext_id in done:
            continue
        if rules.execute("SELECT COUNT(*) FROM rules").fetchone()[0] >= target:
            break
        try:
            out = extract(model, title, abstract)
        except Exception as e:
            print(f"  ! {type(e).__name__} {e}", flush=True)
            time.sleep(3)
            continue
        n = 0
        for r in out[:3]:
            rule = (r.get("rule") or "").strip()
            mech = (r.get("mechanism") or "").strip()
            surf = (r.get("surface") or "").strip().lower()
            if len(rule) < 25 or not mech or surf not in SURFACES:
                rejected += 1
                continue
            if verbatim_overlap(rule, abstract) or verbatim_overlap(mech, abstract):
                rejected += 1          # legal guard: too close to the source wording
                continue
            if OFF_DOMAIN.search(rule) or META_RESEARCH.search(rule) or META_ANY.search(rule):
                rejected += 1          # quality guard: not a practitioner rule
                continue
            h = hashlib.sha256(norm(rule).encode()).hexdigest()[:32]
            try:
                rules.execute(
                    """INSERT OR IGNORE INTO rules(rule,mechanism,category,source_kind,
                       source_ref,source_title,confidence,norm_hash,extracted_at)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (rule, mech, surf, src, doi or arxiv_id or ext_id, title,
                     float(r.get("confidence") or 0.5), h, now()))
                n += 1
            except Exception:
                rejected += 1
        rules.execute("INSERT OR REPLACE INTO done VALUES(?,?,?)", (ext_id, n, now()))
        rules.commit()
        kept += n
        if i % 20 == 0:
            tot = rules.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
            rate = (i + 1) / max(1e-9, time.time() - t0)
            print(f"  [{i:5,}/{len(rows):,}] rules={tot:,} kept={kept:,} "
                  f"rejected={rejected:,} {rate:.2f} papers/s", flush=True)
    tot = rules.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    print(f"DONE  rules={tot:,}  kept={kept:,}  rejected={rejected:,}", flush=True)


def report():
    p = os.path.join(HERE, "rules.db")
    if not os.path.exists(p):
        sys.exit("rules.db not built yet")
    con = sqlite3.connect(p)
    con.executescript(SCHEMA)
    tot = con.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    print(f"{tot:,} rules\n")
    print("by control surface:")
    for cat, n in con.execute("SELECT category,COUNT(*) FROM rules GROUP BY category ORDER BY 2 DESC"):
        print(f"  {cat:16} {n:6,}")
    print("\nhighest-confidence samples:")
    for rule, mech, cat, ref in con.execute(
            "SELECT rule,mechanism,category,source_ref FROM rules ORDER BY confidence DESC LIMIT 12"):
        print(f"  [{cat}] {rule}")
        print(f"      why: {mech}")
        print(f"      src: {ref}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=3000)
    ap.add_argument("--papers", type=int, default=40000)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    report() if a.report else run(a.target, a.papers)

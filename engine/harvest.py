#!/usr/bin/env python3
"""
claude-rules-db harvester.

An engine, not a script: sources are adapters, topics are inputs.
Zero dependencies (stdlib only), KEYLESS, resumable, polite, LICENCE-GATED.

  python harvest.py papers  --target 40000
  python harvest.py prompts --target 40000
  python harvest.py status
  python harvest.py licences          # what we would and would not ingest

FREE:  every source below is keyless and free. No API key exists in this repo.
LEGAL: every row carries the licence it arrived under. Prompt datasets are
       gated on a licence fetched at runtime -- unknown fails CLOSED, and
       anything non-commercial (-nc) is refused unless you pass --any-licence.
       See LICENSING.md for what is redistributable and what is not.
"""
import argparse, hashlib, json, os, random, re, sqlite3, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
MAILTO = os.environ.get("CONTACT_EMAIL", "you@example.com")  # polite-pool contact for OpenAlex/Crossref
UA = f"claude-rules-db/0.1 (research; {MAILTO})"

# ---------------------------------------------------------------- licences
# Permissive enough to redistribute AND use commercially.
LICENCE_ALLOW = {
    "cc0-1.0", "cc-by-4.0", "cc-by-3.0", "cc-by-sa-4.0", "cc-by-sa-3.0",
    "mit", "apache-2.0", "bsd", "bsd-3-clause", "bsd-2-clause", "odc-by",
    "odbl", "unlicense", "pddl", "gpl-3.0", "lgpl-3.0", "artistic-2.0",
    # Community Data License Agreement - Permissive: commercial use allowed.
    "cdla-permissive-1.0", "cdla-permissive-2.0",
}
# Explicitly refused: non-commercial, no-derivatives, research-only, unknown.
LICENCE_DENY_PAT = re.compile(r"(-nc|noncommercial|non-commercial|-nd\b|research|academic|openrail|llama|gemma|proprietary|other|unknown)", re.I)

SOURCE_TERMS = {
    # what the SOURCE grants us, independent of the row's own licence
    "openalex":  ("CC0-1.0", 1, "OpenAlex metadata is CC0 public domain."),
    "arxiv":     ("arXiv-metadata-CC0/abstract-author-(c)", 0,
                  "arXiv metadata is CC0; ABSTRACT text remains author copyright - index, do not republish."),
    "crossref":  ("Crossref-metadata-open/abstract-varies", 0,
                  "Crossref metadata is openly reusable; publisher abstracts vary - do not republish."),
}

# ---------------------------------------------------------------- topics
# Targets are inputs. Add a line here and the whole engine widens.
TOPICS = [
    "prompt engineering", "chain of thought prompting", "in-context learning",
    "large language model agents", "LLM tool use", "retrieval augmented generation",
    "self-consistency decoding", "ReAct reasoning acting", "reflexion self-reflection",
    "LLM as a judge", "multi-agent LLM systems", "LLM code generation",
    "program synthesis language model", "instruction tuning", "few-shot prompting",
    "zero-shot reasoning", "prompt injection", "hallucination mitigation LLM",
    "sycophancy language model", "long context language model",
    "context compression LLM", "LLM planning", "self-refine iterative refinement",
    "constitutional AI", "RLHF alignment", "tree of thoughts",
    "least-to-most prompting", "automatic prompt optimization",
    "LLM evaluation benchmark", "agentic workflow", "LLM memory architecture",
    "software engineering large language model", "test generation LLM",
    "code review automation LLM", "repository level code completion",
    "LLM reasoning verification", "process supervision reward model",
    "structured output constrained decoding", "function calling LLM",
    "prompt compression", "role prompting persona", "system prompt design",
    "LLM safety guardrails", "human AI collaboration programming",
    "developer productivity AI assistant", "specification driven development LLM",
]
ARXIV_CATS = ["cs.CL", "cs.AI", "cs.SE", "cs.LG", "cs.MA", "cs.IR", "cs.HC"]

# Candidate prompt corpora. The runtime licence gate decides which survive --
# this list is deliberately broad because the GATE is the authority, not my memory.
HF_PROMPT_DATASETS = [
    "fka/awesome-chatgpt-prompts", "teilomillet/system_prompts",
    "yizhongw/self_instruct", "databricks/databricks-dolly-15k",
    "OpenAssistant/oasst1", "Open-Orca/OpenOrca", "theblackcat102/evol-codealpaca-v1",
    "sahil2801/CodeAlpaca-20k", "b-mc2/sql-create-context", "garage-bAInd/Open-Platypus",
    "iamtarun/python_code_instructions_18k_alpaca", "vicgalle/alpaca-gpt4",
    "TokenBender/code_instructions_122k_alpaca_style", "nomic-ai/gpt4all-j-prompt-generations",
    "WizardLMTeam/WizardLM_evol_instruct_V2_196k", "teknium/OpenHermes-2.5",
    "HuggingFaceH4/ultrachat_200k", "allenai/tulu-v2-sft-mixture",
    "m-a-p/CodeFeedback-Filtered-Instruction", "ise-uiuc/Magicoder-OSS-Instruct-75K",
    "glaiveai/glaive-function-calling-v2", "Salesforce/xlam-function-calling-60k",
    "THUDM/AgentInstruct", "gaia-benchmark/GAIA", "princeton-nlp/SWE-bench",
    "bigcode/self-oss-instruct-sc2-exec-filter-50k", "cognitivecomputations/dolphin",
    "LDJnr/Capybara", "arcee-ai/agent-data", "microsoft/orca-agentinstruct-1M-v1",
]

# ---------------------------------------------------------------- polite http
class Gate:
    """Per-host serialisation + minimum gap + jitter. One lock per host."""
    def __init__(self):
        self._locks, self._last, self._meta = {}, {}, threading.Lock()

    def wait(self, host, gap):
        with self._meta:
            lock = self._locks.setdefault(host, threading.Lock())
        with lock:
            delay = gap + random.uniform(0, 0.5) - (time.time() - self._last.get(host, 0.0))
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.time()

GATE = Gate()
HOST_GAP = {"export.arxiv.org": 3.2, "api.openalex.org": 0.15, "api.crossref.org": 0.6,
            "datasets-server.huggingface.co": 0.35, "huggingface.co": 0.5}


def fetch(url, tries=4, cache=True):
    host = urllib.parse.urlparse(url).netloc
    key = hashlib.sha256(url.encode()).hexdigest()[:40]
    path = os.path.join(CACHE, key)
    if cache and os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    for attempt in range(tries):
        GATE.wait(host, HOST_GAP.get(host, 1.1))
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "application/json, application/atom+xml, */*"})
            body = urllib.request.urlopen(req, timeout=60).read()
            if cache:
                os.makedirs(CACHE, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(body)
            return body
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep((2 ** attempt) * 2 + random.uniform(0, 2)); continue
            return None
        except Exception:
            time.sleep((2 ** attempt) + random.uniform(0, 1))
    return None


# ---------------------------------------------------------------- storage
SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
  id INTEGER PRIMARY KEY, src TEXT, ext_id TEXT UNIQUE, doi TEXT, arxiv_id TEXT,
  title TEXT, abstract TEXT, authors TEXT, year INTEGER, venue TEXT, url TEXT,
  cats TEXT, cited_by INTEGER, norm_title TEXT, topic TEXT,
  licence TEXT, redistribute INTEGER, fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_p_norm ON papers(norm_title);
CREATE INDEX IF NOT EXISTS ix_p_year ON papers(year);

CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER PRIMARY KEY, src TEXT, ext_id TEXT UNIQUE, title TEXT, prompt TEXT,
  role TEXT, category TEXT, tags TEXT, source_url TEXT, tokens_est INTEGER,
  norm_hash TEXT, licence TEXT, redistribute INTEGER, commercial_ok INTEGER,
  fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_q_hash ON prompts(norm_hash);
CREATE INDEX IF NOT EXISTS ix_q_lic ON prompts(commercial_ok);

CREATE TABLE IF NOT EXISTS rules (
  id INTEGER PRIMARY KEY, rule TEXT, mechanism TEXT, category TEXT,
  source_kind TEXT, source_ref TEXT, source_title TEXT, confidence REAL,
  norm_hash TEXT UNIQUE, extracted_at TEXT);

CREATE TABLE IF NOT EXISTS licences (
  dataset TEXT PRIMARY KEY, licence TEXT, verdict TEXT, checked_at TEXT);

CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT);
"""


def db(name):
    con = sqlite3.connect(os.path.join(HERE, name), timeout=60)
    con.executescript(SCHEMA)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def getstate(con, k, d=None):
    r = con.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
    return r[0] if r else d


def setstate(con, k, v):
    con.execute("INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
    con.commit()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def count(con, t):
    return con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# Fuzzy search on OpenAlex/Crossref happily returns the most-cited deep-learning
# papers that merely brush the query -- DeepLab, AlphaFold, Grad-CAM. Volume is
# worthless if the corpus is wrong, so every row must name an actual LLM anchor.
RELEVANT = re.compile(
    r"(large language model|language model|\bLLM\b|\bLLMs\b|\bGPT\b|GPT-[0-9]|ChatGPT"
    r"|Claude|LLaMA|Mistral|Gemini|PaLM|BERT|\bprompt|prompting|in-context learning"
    r"|chain[- ]of[- ]thought|instruction[- ]tun|foundation model|generative AI"
    r"|\bAI agent|agentic|autonomous agent|retrieval[- ]augmented|text[- ]to[- ]text"
    r"|natural language processing|\bNLP\b|code generation|program synthesis)", re.I)


def relevant(title, abstract):
    return bool(RELEVANT.search(f"{title or ''} {abstract or ''}"))


PAPER_COLS = """INSERT OR IGNORE INTO papers(src,ext_id,doi,arxiv_id,title,abstract,authors,
  year,venue,url,cats,cited_by,norm_title,topic,licence,redistribute,fetched_at)
  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


# ---------------------------------------------------------------- licence gate
def hf_licence(con, dataset):
    """Fetch the licence from HF at runtime. Fail CLOSED on unknown."""
    row = con.execute("SELECT licence, verdict FROM licences WHERE dataset=?", (dataset,)).fetchone()
    if row:
        return row[0], row[1]
    body = fetch("https://huggingface.co/api/datasets/" + urllib.parse.quote(dataset))
    lic = None
    if body:
        try:
            meta = json.loads(body)
            card = meta.get("cardData") or {}
            lic = card.get("license")
            if isinstance(lic, list):
                lic = lic[0] if lic else None
            if not lic:
                for t in meta.get("tags", []):
                    if isinstance(t, str) and t.startswith("license:"):
                        lic = t.split(":", 1)[1]
                        break
        except Exception:
            pass
    lic = (lic or "unknown").strip().lower()
    if LICENCE_DENY_PAT.search(lic):
        verdict = "DENY"
    elif lic in LICENCE_ALLOW:
        verdict = "ALLOW"
    else:
        verdict = "DENY"          # fail closed
    con.execute("INSERT OR REPLACE INTO licences VALUES(?,?,?,?)", (dataset, lic, verdict, now()))
    con.commit()
    return lic, verdict


# ---------------------------------------------------------------- paper adapters
def adapter_arxiv(con, topic, budget):
    lic, redis, _ = SOURCE_TERMS["arxiv"]
    added = 0
    for cat in ARXIV_CATS:
        if added >= budget:
            break
        skey = f"arxiv:{topic}:{cat}"
        start = int(getstate(con, skey, 0))
        for _ in range(10):
            if added >= budget:
                break
            q = f'cat:{cat} AND all:"{topic}"'
            url = ("http://export.arxiv.org/api/query?search_query=" + urllib.parse.quote(q)
                   + f"&start={start}&max_results=100&sortBy=relevance")
            body = fetch(url)
            if not body:
                break
            text = body.decode("utf-8", "replace")
            entries = re.findall(r"<entry>(.*?)</entry>", text, re.S)
            if not entries:
                break
            rows = []
            for e in entries:
                def g(tag):
                    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", e, re.S)
                    return strip_tags(m.group(1)) if m else ""
                aid, title, pub = g("id").rsplit("/", 1)[-1], g("title"), g("published")
                if not aid or not title or not relevant(title, g("summary")):
                    continue
                rows.append(("arxiv", f"arxiv:{aid}", None, aid, title, g("summary"),
                             ", ".join(re.findall(r"<name>(.*?)</name>", e)),
                             int(pub[:4]) if pub[:4].isdigit() else None, "arXiv",
                             f"https://arxiv.org/abs/{aid}",
                             ",".join(re.findall(r'category term="([^"]+)"', e)), None,
                             norm(title), topic, lic, redis, now()))
            cur = con.executemany(PAPER_COLS, rows)
            con.commit()
            added += cur.rowcount
            start += 100
            setstate(con, skey, start)
            if len(entries) < 100:
                break
    return added


def adapter_openalex(con, topic, budget):
    lic, redis, _ = SOURCE_TERMS["openalex"]
    added, skey = 0, f"openalex:{topic}"
    cursor = getstate(con, skey, "*")
    if cursor == "DONE":
        return 0
    while added < budget:
        url = ("https://api.openalex.org/works?search=" + urllib.parse.quote(topic)
               + f"&per-page=200&cursor={urllib.parse.quote(cursor)}"
               + "&filter=from_publication_date:2017-01-01"
               + "&select=id,doi,title,publication_year,cited_by_count,abstract_inverted_index,authorships,primary_location"
               + f"&mailto={MAILTO}")
        body = fetch(url, cache=False)
        if not body:
            break
        try:
            data = json.loads(body)
        except Exception:
            break
        results = data.get("results", [])
        if not results:
            setstate(con, skey, "DONE"); break
        rows = []
        for w in results:
            title = w.get("title") or ""
            if not title:
                continue
            inv = w.get("abstract_inverted_index") or {}
            abstract = ""
            if inv:
                pos = {}
                for word, idxs in inv.items():
                    for i in idxs:
                        pos[i] = word
                abstract = " ".join(pos[i] for i in sorted(pos))[:8000]
            if not relevant(title, abstract):
                continue
            venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
            rows.append(("openalex", w["id"], w.get("doi"), None, title, abstract,
                         ", ".join((a.get("author") or {}).get("display_name") or ""
                                   for a in (w.get("authorships") or [])[:12]),
                         w.get("publication_year"), venue, w.get("doi") or w["id"], None,
                         w.get("cited_by_count"), norm(title), topic, lic, redis, now()))
        cur = con.executemany(PAPER_COLS, rows)
        con.commit()
        added += cur.rowcount
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor:
            setstate(con, skey, "DONE"); break
        setstate(con, skey, cursor)
    return added


def adapter_crossref(con, topic, budget):
    lic, redis, _ = SOURCE_TERMS["crossref"]
    added, skey = 0, f"crossref:{topic}"
    cursor = getstate(con, skey, "*")
    if cursor == "DONE":
        return 0
    while added < budget:
        url = ("https://api.crossref.org/works?query=" + urllib.parse.quote(topic)
               + f"&rows=200&cursor={urllib.parse.quote(cursor)}&mailto={MAILTO}"
               + "&select=DOI,title,abstract,author,issued,container-title,is-referenced-by-count")
        body = fetch(url, cache=False)
        if not body:
            break
        try:
            msg = json.loads(body)["message"]
        except Exception:
            break
        items = msg.get("items", [])
        if not items:
            setstate(con, skey, "DONE"); break
        rows = []
        for it in items:
            title = (it.get("title") or [""])[0]
            if not title:
                continue
            abst = strip_tags(it.get("abstract"))
            if not relevant(title, abst):
                continue
            parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
            rows.append(("crossref", "doi:" + it["DOI"], it["DOI"], None, title,
                         abst,
                         ", ".join(f"{a.get('given','')} {a.get('family','')}".strip()
                                   for a in (it.get("author") or [])[:12]),
                         parts[0] if parts else None, (it.get("container-title") or [""])[0],
                         "https://doi.org/" + it["DOI"], None,
                         it.get("is-referenced-by-count"), norm(title), topic, lic, redis, now()))
        cur = con.executemany(PAPER_COLS, rows)
        con.commit()
        added += cur.rowcount
        cursor = msg.get("next-cursor")
        if not cursor:
            setstate(con, skey, "DONE"); break
        setstate(con, skey, cursor)
    return added


PAPER_ADAPTERS = [("openalex", adapter_openalex), ("arxiv", adapter_arxiv),
                  ("crossref", adapter_crossref)]

# ---------------------------------------------------------------- prompt adapter
PROMPT_FIELDS = ["prompt", "system_prompt", "instruction", "act", "text", "input",
                 "question", "query", "content", "human", "message"]


def adapter_hf(con, dataset, budget, any_licence=False):
    lic, verdict = hf_licence(con, dataset)
    if verdict != "ALLOW" and not any_licence:
        return 0, lic, verdict
    ok = 1 if verdict == "ALLOW" else 0
    added = 0
    info = fetch("https://datasets-server.huggingface.co/splits?dataset=" + urllib.parse.quote(dataset))
    if not info:
        return 0, lic, "NO-SPLITS"
    try:
        splits = json.loads(info).get("splits", [])
    except Exception:
        return 0, lic, "BAD-SPLITS"
    for sp in splits[:2]:
        cfg, split = sp.get("config"), sp.get("split")
        skey = f"hf:{dataset}:{cfg}:{split}"
        off = int(getstate(con, skey, 0))
        while added < budget:
            url = ("https://datasets-server.huggingface.co/rows?dataset=" + urllib.parse.quote(dataset)
                   + f"&config={urllib.parse.quote(cfg)}&split={urllib.parse.quote(split)}"
                   + f"&offset={off}&length=100")
            body = fetch(url, cache=False)
            if not body:
                break
            try:
                rows_in = json.loads(body).get("rows", [])
            except Exception:
                break
            if not rows_in:
                break
            out = []
            for n, r in enumerate(rows_in):
                row = r.get("row", {})
                text = ""
                for f in PROMPT_FIELDS:
                    v = row.get(f)
                    if isinstance(v, str) and len(v.strip()) > 12:
                        text = v.strip(); break
                if not text:
                    for v in row.values():
                        if isinstance(v, str) and len(v.strip()) > 40:
                            text = v.strip(); break
                if not text or len(text) > 24000:
                    continue
                title = str(row.get("act") or row.get("title") or text[:70]).strip()
                out.append(("hf:" + dataset, f"{dataset}#{cfg}#{split}#{off+n}", title, text,
                            str(row.get("role") or ""), str(row.get("category") or ""), "",
                            f"https://huggingface.co/datasets/{dataset}", max(1, len(text) // 4),
                            hashlib.sha256(norm(text).encode()).hexdigest()[:32], lic, ok, ok, now()))
            cur = con.executemany(
                """INSERT OR IGNORE INTO prompts(src,ext_id,title,prompt,role,category,tags,
                   source_url,tokens_est,norm_hash,licence,redistribute,commercial_ok,fetched_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", out)
            con.commit()
            added += cur.rowcount
            off += 100
            setstate(con, skey, off)
            if len(rows_in) < 100:
                break
    return added, lic, verdict


# ---------------------------------------------------------------- drivers
def run_papers(target):
    con = db("papers.db")
    print(f"[papers] at {count(con,'papers'):,}  target {target:,}", flush=True)
    while count(con, "papers") < target:
        progressed = False
        for topic in TOPICS:
            for name, fn in PAPER_ADAPTERS:
                if count(con, "papers") >= target:
                    break
                try:
                    n = fn(con, topic, budget=800)
                except Exception as e:
                    print(f"  ! {name}/{topic}: {type(e).__name__} {e}", flush=True); n = 0
                if n:
                    progressed = True
                    print(f"  +{n:5,} {name:9} {topic[:36]:36} total {count(con,'papers'):,}", flush=True)
        if not progressed:
            print("[papers] adapters exhausted for this topic set", flush=True); break
    print(f"[papers] DONE {count(con,'papers'):,}", flush=True)


def run_prompts(target, any_licence=False):
    con = db("prompts.db")
    print(f"[prompts] at {count(con,'prompts'):,}  target {target:,}"
          f"{'  (LICENCE GATE OFF)' if any_licence else '  (commercial-safe only)'}", flush=True)
    while count(con, "prompts") < target:
        progressed = False
        for ds in HF_PROMPT_DATASETS:
            if count(con, "prompts") >= target:
                break
            try:
                n, lic, verdict = adapter_hf(con, ds, 6000, any_licence)
            except Exception as e:
                print(f"  ! hf/{ds}: {type(e).__name__} {e}", flush=True); continue
            if verdict != "ALLOW" and not n:
                print(f"  SKIP  {ds[:44]:44} licence={lic[:24]:24} {verdict}", flush=True)
            if n:
                progressed = True
                print(f"  +{n:5,} {ds[:44]:44} licence={lic[:18]:18} total {count(con,'prompts'):,}", flush=True)
        if not progressed:
            print("[prompts] candidate list exhausted", flush=True); break
    print(f"[prompts] DONE {count(con,'prompts'):,}", flush=True)


def run_licences():
    con = db("prompts.db")
    print(f"{'dataset':46} {'licence':24} verdict")
    print("-" * 84)
    allow = deny = 0
    for ds in HF_PROMPT_DATASETS:
        lic, verdict = hf_licence(con, ds)
        allow += verdict == "ALLOW"
        deny += verdict != "ALLOW"
        print(f"{ds[:46]:46} {lic[:24]:24} {verdict}")
    print("-" * 84)
    print(f"{allow} usable / {deny} refused (unknown fails closed)")


def run_status():
    for name, table in (("papers.db", "papers"), ("prompts.db", "prompts"), ("rules.db", "rules")):
        p = os.path.join(HERE, name)
        if not os.path.exists(p):
            print(f"{table:8}        —  not created yet"); continue
        con = sqlite3.connect(p); con.executescript(SCHEMA)
        n, size = count(con, table), os.path.getsize(p) / 1e6
        extra = ""
        if table == "papers":
            src = con.execute("SELECT src,COUNT(*) FROM papers GROUP BY src ORDER BY 2 DESC").fetchall()
            wa = con.execute("SELECT COUNT(*) FROM papers WHERE LENGTH(abstract)>120").fetchone()[0]
            extra = "  " + ", ".join(f"{s}={c:,}" for s, c in src) + f"  | usable abstracts {wa:,}"
        if table == "prompts":
            ok = con.execute("SELECT COUNT(*) FROM prompts WHERE commercial_ok=1").fetchone()[0]
            extra = f"  commercial-safe {ok:,}"
        print(f"{table:8} {n:>8,} rows {size:7.1f} MB{extra}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["papers", "prompts", "status", "licences"])
    ap.add_argument("--target", type=int, default=40000)
    ap.add_argument("--any-licence", action="store_true",
                    help="DANGEROUS: ingest non-commercial / unknown-licence corpora too")
    a = ap.parse_args()
    random.seed()
    {"papers": lambda: run_papers(a.target),
     "prompts": lambda: run_prompts(a.target, a.any_licence),
     "licences": run_licences,
     "status": run_status}[a.cmd]()

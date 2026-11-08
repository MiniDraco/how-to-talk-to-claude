#!/usr/bin/env python3
"""
Classify mined rules so the dev map can be built from the ones that actually apply.

  python classify.py --limit 3000
  python classify.py --report

The mined corpus is NOT uniform. It contains, mixed together:
  - advice for frontier coding agents            <- what we want
  - general LLM usage advice that still holds    <- also want
  - scaffolding only weak/small models need      <- a frontier model does this itself
  - techniques superseded by model or tooling    <- outdated
  - advice for image / music / video generation  <- different tool entirely
  - training, fine-tuning and benchmark-building <- not usage advice at all

Each rule gets: WHEN (dev stage), APPLIES (audience), an EXAMPLE of it in use,
and a currency judgement. A cheap regex pass handles the obvious non-text
modalities before spending any GPU time on them.
"""
import argparse, json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
_h = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").replace("http://", "").strip("/")
BASE = "http://" + (_h.replace("0.0.0.0", "127.0.0.1") if ":" in _h else _h + ":11434")
PREFERRED = ["hermes3:8b", "dolphin-llama3", "aya-expanse", "qwen2.5:3b"]

# WHEN — the nine development stages, in order.
STAGES = ["intent", "literacy", "design", "scaffold", "build",
          "verify", "integrate", "harden", "ship"]
STAGE_HELP = {
    "intent": "deciding what to build and to what standard, before any design",
    "literacy": "learning the domain; understanding what you don't understand",
    "design": "architecture, decomposition, interfaces, boundaries",
    "scaffold": "harness, tests, probes, environment, constraints — before features",
    "build": "generating the actual implementation",
    "verify": "checking the result is correct",
    "integrate": "making the parts work together as a whole",
    "harden": "edge cases, failure paths, performance, security",
    "ship": "release, documentation, handover, capturing what was learned",
}

# APPLIES — who the rule is actually for.
AUDIENCES = ["coding-agent", "any-llm", "weak-model", "outdated",
             "other-modality", "research-only", "commentary", "ops"]

# Cheap pre-filter: obviously a different modality or a training-time concern.
OTHER_MODALITY = re.compile(
    r"\b(diffusion|stable diffusion|midjourney|dall-?e|image generation|text-to-image"
    r"|text-to-video|video generation|inpaint|outpaint|denois|latent space image"
    r"|music|audio generation|text-to-speech|speech recognition|voice clon|suno"
    r"|spectrogram|waveform|melody|timbre|point cloud|segmentation mask|optical flow"
    r"|object detection|super-resolution|nerf|gaussian splat)", re.I)
RESEARCH_ONLY = re.compile(
    r"\b(pre-?train|fine-?tun|lora|qlora|quantiz|distill|reward model|rlhf pipeline"
    r"|gradient|checkpoint averaging|learning rate|batch size|epoch|tokenizer training"
    r"|corpus construction|annotate a dataset|human annotators|crowdsourc"
    r"|ablation study|leaderboard|benchmark construction)", re.I)

SYS = """You classify a practitioner rule about using AI language models.

Return STRICT JSON:
{"stage":..., "applies":..., "example":..., "current":true/false}

"stage" — WHEN in a development cycle you would apply this. Exactly one of:
  intent, literacy, design, scaffold, build, verify, integrate, harden, ship

"applies" — WHO this is actually for. Exactly one of:
  coding-agent   : specific to an agentic coding assistant that reads/writes files and runs commands
  any-llm        : general text/code LLM usage advice that still holds for a frontier model
  weak-model     : scaffolding only a small or older model needs; a frontier model already does this
  outdated       : superseded by model capability or by tooling that now does it automatically
  other-modality : about image, video, audio or music generation, not text/code
  research-only  : about training, fine-tuning, or building benchmarks - not about USING a model
  ops            : serving, deployment, inference infrastructure, cost/latency engineering
  commentary     : ethics, policy, education, societal impact, or a vague "be aware that..."
                   observation. If it does not tell you to DO something specific, it is commentary.

"example" — ONE concrete sentence showing the rule in use. Write it as something a
person would actually type or do. No preamble. If you cannot give a concrete
example, the rule is too vague: set applies to "outdated".

"current" — false if a frontier model in 2026 makes this unnecessary (e.g. "tell it
to think step by step", "ask it to be concise so it doesn't ramble", basic
role-play framing). true otherwise.

Judge honestly. Most mined rules are NOT coding-agent specific, and a large share are
commentary dressed as advice. "Consider the implications of X" is commentary. "Be aware
that Y exists" is commentary. A real rule survives the test: could two people disagree
about whether you followed it? If not, it is commentary."""


def api(path, payload=None, timeout=180):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(payload).encode() if payload else None,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def pick_model():
    try:
        names = [m["name"] for m in api("/api/tags").get("models", [])]
    except Exception as e:
        sys.exit(f"Ollama unreachable at {BASE}: {e}")
    for p in PREFERRED:
        for n in names:
            if n.startswith(p):
                return n
    return names[0] if names else sys.exit("no models")


MIGRATE = [
    "ALTER TABLE rules ADD COLUMN stage TEXT",
    "ALTER TABLE rules ADD COLUMN applies TEXT",
    "ALTER TABLE rules ADD COLUMN example TEXT",
    "ALTER TABLE rules ADD COLUMN current INTEGER",
    "ALTER TABLE rules ADD COLUMN classified_at TEXT",
]


def ensure(con):
    for stmt in MIGRATE:
        try:
            con.execute(stmt)
        except sqlite3.OperationalError:
            pass
    con.commit()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(limit):
    con = sqlite3.connect(os.path.join(HERE, "rules.db"), timeout=60)
    ensure(con)
    model = pick_model()

    # cheap pass first — never spend GPU time on an obvious other-modality rule
    pre = 0
    for rid, rule, mech in con.execute(
            "SELECT id, rule, mechanism FROM rules WHERE applies IS NULL").fetchall():
        blob = f"{rule} {mech or ''}"
        aud = ("other-modality" if OTHER_MODALITY.search(blob)
               else "research-only" if RESEARCH_ONLY.search(blob) else None)
        if aud:
            con.execute("UPDATE rules SET applies=?, current=0, classified_at=? WHERE id=?",
                        (aud, now(), rid))
            pre += 1
    con.commit()
    print(f"regex pre-pass: {pre:,} rules routed without the model", flush=True)

    todo = con.execute("""SELECT id, rule, mechanism FROM rules
                          WHERE applies IS NULL LIMIT ?""", (limit,)).fetchall()
    print(f"model={model}  classifying {len(todo):,}", flush=True)
    t0, ok = time.time(), 0
    for i, (rid, rule, mech) in enumerate(todo):
        try:
            r = api("/api/chat", {
                "model": model, "stream": False, "format": "json",
                "options": {"temperature": 0.1, "num_gpu": 99, "num_ctx": 4096,
                            "num_predict": 260},
                "messages": [{"role": "system", "content": SYS},
                             {"role": "user",
                              "content": f"RULE: {rule}\nWHY: {mech or ''}"}]})
            d = json.loads(r["message"]["content"])
        except Exception:
            continue
        stage = str(d.get("stage", "")).strip().lower()
        aud = str(d.get("applies", "")).strip().lower()
        ex = str(d.get("example", "")).strip()
        if stage not in STAGES:
            stage = None
        if aud not in AUDIENCES:
            aud = "any-llm"
        cur = 0 if d.get("current") is False else 1
        con.execute("""UPDATE rules SET stage=?, applies=?, example=?, current=?,
                       classified_at=? WHERE id=?""",
                    (stage, aud, ex[:400], cur, now(), rid))
        ok += 1
        if i % 25 == 0:
            con.commit()
            rate = (i + 1) / max(1e-9, time.time() - t0)
            left = (len(todo) - i) / max(1e-6, rate) / 60
            print(f"  [{i:5,}/{len(todo):,}] ok={ok:,} {rate:.2f}/s  ~{left:.0f} min left",
                  flush=True)
    con.commit()
    print(f"classified {ok:,}", flush=True)


def report():
    con = sqlite3.connect(os.path.join(HERE, "rules.db"))
    ensure(con)
    tot = con.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    done = con.execute("SELECT COUNT(*) FROM rules WHERE applies IS NOT NULL").fetchone()[0]
    print(f"{done:,} of {tot:,} classified\n")
    print("WHO it's for:")
    for a, n in con.execute("""SELECT applies, COUNT(*) FROM rules WHERE applies IS NOT NULL
                               GROUP BY applies ORDER BY 2 DESC"""):
        print(f"  {a:16} {n:6,}")
    print("\nWHEN to apply it:")
    for s, n in con.execute("""SELECT stage, COUNT(*) FROM rules WHERE stage IS NOT NULL
                               GROUP BY stage ORDER BY 2 DESC"""):
        print(f"  {s:16} {n:6,}")
    keep = con.execute("""SELECT COUNT(*) FROM rules
                          WHERE applies IN ('coding-agent','any-llm') AND current=1
                            AND stage IS NOT NULL AND LENGTH(example)>15""").fetchone()[0]
    print(f"\nUSABLE for the dev map: {keep:,}")
    print("\nsamples that survived:")
    for r, ex, s, a in con.execute("""SELECT rule, example, stage, applies FROM rules
        WHERE applies IN ('coding-agent','any-llm') AND current=1 AND stage IS NOT NULL
          AND LENGTH(example)>15 ORDER BY RANDOM() LIMIT 5"""):
        print(f"  [{s}/{a}] {r[:96]}\n      e.g. {ex[:110]}")
    print("\nsamples that were REJECTED:")
    for r, a in con.execute("""SELECT rule, applies FROM rules
        WHERE applies NOT IN ('coding-agent','any-llm') OR current=0
        ORDER BY RANDOM() LIMIT 5"""):
        print(f"  [{a}] {r[:104]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    report() if a.report else run(a.limit)

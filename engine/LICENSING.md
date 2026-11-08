# Licensing — what is free, what is legal, what you may redistribute

Two hard constraints on this project: **everything must be free** (keyless, no
paid API, no quota) and **everything must be legal** (no licence we can't honour).
This file records exactly how each obligation is met, per source.

There is no API key anywhere in this repository. Every source below is reachable
anonymously.

---

## The gate

Prompt corpora are gated at **runtime**, not from memory. `harvest.py` fetches each
dataset's declared licence from the Hugging Face API before ingesting a single row,
records it in the `licences` table, and applies:

- **ALLOW** — licence appears in `LICENCE_ALLOW` (CC0, CC-BY, CC-BY-SA, MIT,
  Apache-2.0, BSD, ODC-BY, CDLA-Permissive, Unlicense, …)
- **DENY** — licence matches `LICENCE_DENY_PAT` (`-nc`, non-commercial, `-nd`,
  research-only, proprietary, model-specific community licences)
- **DENY** — anything else, **including unknown**. The gate **fails closed**.

Failing closed is deliberate. An unlabelled dataset is not a permissive dataset;
it's an unanswered question, and unanswered questions don't go in a database you
might one day ship.

Run the gate at any time without harvesting:

```bash
python harvest.py licences
```

### What the gate actually caught

On first run, 21 of 30 candidate corpora passed. The refusals matter more than
the passes:

| Dataset | Licence | Why refused |
|---|---|---|
| `vicgalle/alpaca-gpt4` | `cc-by-nc-4.0` | **Non-commercial.** The exact trap. |
| `teknium/OpenHermes-2.5` | unspecified | Unknown → fails closed |
| `garage-bAInd/Open-Platypus` | unspecified | Mixed upstream licences |
| `THUDM/AgentInstruct` | unspecified | Unknown → fails closed |
| `princeton-nlp/SWE-bench` | unspecified | Unknown → fails closed |
| `gaia-benchmark/GAIA` | unspecified | Unknown → fails closed |

`microsoft/orca-agentinstruct-1M-v1` was initially refused as unknown; on checking,
`cdla-permissive-2.0` (Community Data License Agreement – Permissive) **does** permit
commercial use, so it was added to the allowlist explicitly. That is the correct way
to widen the gate: verify the licence, then name it. Never widen a bound just to make
a row pass.

Every prompt row carries `licence`, `redistribute`, and `commercial_ok`, so a
downstream consumer can filter without trusting this document:

```sql
SELECT * FROM prompts WHERE commercial_ok = 1;
```

---

## Papers

Bibliographic **metadata** and **full text** have completely different statuses, and
the database keeps them apart.

| Source | Metadata | Abstract text | `redistribute` |
|---|---|---|---|
| **OpenAlex** | CC0 — public domain | CC0 (reconstructed from an inverted index OpenAlex publishes as CC0) | `1` |
| **arXiv** | CC0 | **Author copyright.** arXiv holds a distribution licence; we don't. | `0` |
| **Crossref** | Openly reusable | Publisher-supplied, varies, often all-rights-reserved | `0` |

So:

- **Safe to publish:** the OpenAlex-sourced rows, and titles / DOIs / authors / years
  / citation counts from every source. Those are facts and CC0 metadata.
- **Not safe to publish:** arXiv and Crossref abstract *text*. Index it, search it,
  read it, derive from it — do not republish it as a corpus.

To export only the publishable subset:

```sql
SELECT * FROM papers WHERE redistribute = 1;
```

---

## Rules

The rules database is derived from paper abstracts, and this is the part people get
wrong, so it's worth being precise.

**Copyright protects expression, not ideas.** "Give the model a verification signal
it can run" is a fact about the world; the particular sentence an author used to say
it is their expression. Extracting the former is fine. Copying the latter is not.

So the extractor is constrained to output **its own phrasing plus a citation**, and
there is a mechanical guard: any candidate rule sharing a long verbatim n-gram with
its source abstract is rejected rather than stored. A rule that can only be expressed
by copying the source sentence doesn't go in.

Each rule keeps `source_ref` (DOI / arXiv id) and `source_title` so every claim is
attributable and checkable. Citation isn't a licence — it doesn't make copying legal —
but combined with original phrasing it makes the derived work genuinely ours.

---

## Politeness

Legality isn't only licensing; it's also not abusing the hosts that give this away free.

- Per-host serialisation with a minimum gap plus jitter (`Gate`), tuned per host —
  arXiv gets 3.2s per their published request, OpenAlex 0.15s per their polite pool.
- A real `User-Agent` with a contact address, and `mailto=` on OpenAlex and Crossref,
  which is what puts requests in their polite pools rather than the anonymous one.
- On-disk response cache, so a re-run costs the source nothing.
- Exponential backoff on 429/5xx, and a hard stop rather than a hammer on 4xx.

## Summary

| Asset | Free | Redistributable | Commercial |
|---|---|---|---|
| Paper metadata (all sources) | ✅ | ✅ | ✅ |
| Abstracts — OpenAlex | ✅ | ✅ | ✅ |
| Abstracts — arXiv / Crossref | ✅ | ❌ index only | ✅ internal use |
| Prompts where `commercial_ok = 1` | ✅ | ✅ per licence terms | ✅ |
| Prompts where `commercial_ok = 0` | — | not ingested by default | — |
| Rules (original phrasing + citation) | ✅ | ✅ | ✅ |

If you relax the gate with `--any-licence`, this table stops being true and the
obligation moves to you.

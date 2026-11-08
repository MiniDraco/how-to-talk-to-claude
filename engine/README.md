# claude-rules-db

Three databases about how to work with language models well — assembled from
free, keyless sources under licences we can actually honour.

| DB | What's in it | Target |
|---|---|---|
| `papers.db` | Research papers on prompting, agents, LLM software engineering | 40,000+ |
| `prompts.db` | Real prompts from permissively-licensed instruction corpora | 40,000+ |
| `rules.db` | Actionable rules extracted from the papers, in our own words, cited | 3,000+ |

```bash
python harvest.py papers  --target 40000     # arXiv + OpenAlex + Crossref
python harvest.py prompts --target 40000     # HuggingFace, licence-gated
python extract_rules.py   --target 3000      # local Ollama over abstracts
python harvest.py status                     # where everything is
python harvest.py licences                   # what would and would not be ingested
python extract_rules.py --report             # rules by control surface, samples
```

---

## The two hard constraints

**Free.** There is no API key in this repository and none is required. arXiv,
OpenAlex, Crossref and the HuggingFace datasets-server are all reachable
anonymously; rule extraction runs on a local Ollama. Nothing here has a quota
or a bill.

**Legal.** Every row records the licence it arrived under. Prompt corpora are
gated on a licence *fetched at runtime*, and the gate **fails closed** — unknown
is refused, not assumed. See [LICENSING.md](LICENSING.md) for the full picture,
including which abstracts may be republished and which may only be indexed.

The gate earns its place: on the first run it refused `vicgalle/alpaca-gpt4`
(`cc-by-nc-4.0`) and five unlabelled corpora, and passed 21 others.

---

## Design notes

**It's an engine, not a script.** Sources are adapters and topics are inputs.
Adding a line to `TOPICS` widens the whole harvest; adding an adapter function
and one tuple entry adds a source. Nothing about the pipeline knows what a
"paper" is beyond the schema.

**Everything is resumable.** Each adapter checkpoints its cursor to a `state`
table after every page, and the rules extractor records every processed paper.
A kill costs one page, not one run. This was not theoretical — the harvest was
killed and restarted mid-flight during construction and lost nothing.

**Polite by construction.** Per-host serialisation with a minimum gap plus
jitter, tuned per host (arXiv gets 3.2s as they ask; OpenAlex 0.15s in their
polite pool). Real User-Agent with a contact address, `mailto=` on OpenAlex and
Crossref, on-disk response cache, exponential backoff on 429/5xx.

**The relevance gate exists because volume lied.** OpenAlex and Crossref use
fuzzy search, and sorting by citation count surfaced the most-cited deep-learning
papers that merely brushed the query — DeepLab, AlphaFold, Grad-CAM. The first
extraction run produced rules about atrous convolution and protein folding. A
third of the harvested corpus (10,706 of 31,237 rows) was off-topic and was
deleted. Row count is not a quality metric; every row must now name an actual
LLM anchor to be stored.

That failure is the reason `extract_rules.py --report` exists. Looking at the
output caught in thirty seconds what the row counter would never have shown.

---

## Schemas

```sql
papers(src, ext_id, doi, arxiv_id, title, abstract, authors, year, venue, url,
       cats, cited_by, norm_title, topic, licence, redistribute, fetched_at)

prompts(src, ext_id, title, prompt, role, category, tags, source_url,
        tokens_est, norm_hash, licence, redistribute, commercial_ok, fetched_at)

rules(rule, mechanism, category, source_kind, source_ref, source_title,
      confidence, norm_hash, extracted_at)
```

`rules.category` is one of the seven control surfaces from
[MAP.md](../prompting-rules/MAP.md) — `intent`, `context`, `persistence`,
`comprehension`, `process`, `verification`, `termination` — so the database
indexes straight back onto the written reference.

Useful queries:

```sql
-- only what you may redistribute
SELECT * FROM papers  WHERE redistribute = 1;
SELECT * FROM prompts WHERE commercial_ok = 1;

-- the verification literature, most-cited first
SELECT rule, mechanism, source_ref FROM rules
WHERE category = 'verification' ORDER BY confidence DESC;
```

---

## Rule extraction, and why it's clean

Copyright protects expression, not ideas. The extractor is instructed to state
the idea in its own words, and there is a mechanical guard behind that
instruction: any candidate rule sharing six or more consecutive words with its
source abstract is rejected rather than stored. In testing that guard fires
often — roughly as many candidates are rejected as kept — which is what you want
from a guard that's actually load-bearing rather than decorative.

Every rule keeps `source_ref` (DOI or arXiv id) and `source_title`, so any claim
can be traced back and checked. Citation is not a licence; it does not make
copying lawful. It's original phrasing that makes the derived work ours, and the
citation that makes it honest.

## Environment notes

This machine has a GTX 1660 SUPER at CUDA index 0 and an RTX 3060 at index 1.
Ollama must be pinned to index 1 or it silently falls back to CPU:

```bash
CUDA_VISIBLE_DEVICES=1 ollama serve
```

`OLLAMA_HOST` is set to a bind address (`0.0.0.0`) in this environment, which is
not connectable; `extract_rules.py` rewrites it to `127.0.0.1` rather than failing.

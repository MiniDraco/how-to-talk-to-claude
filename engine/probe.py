import urllib.request, urllib.parse, json, re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
MAILTO = os.environ.get('CONTACT_EMAIL', 'you@example.com')
UA = {'User-Agent': f'claude-rules-db/0.1 (research; {MAILTO})'}

def get(url, timeout=30):
    r = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(r, timeout=timeout).read()

print("=== arXiv ===")
try:
    q = 'all:"large language model" OR all:"prompt engineering" OR all:"LLM agent"'
    u = "http://export.arxiv.org/api/query?search_query=" + urllib.parse.quote(q) + "&start=0&max_results=1"
    b = get(u).decode('utf-8', 'replace')
    m = re.search(r'opensearch:totalResults[^>]*>(\d+)<', b)
    print("  reachable: YES   total hits:", m.group(1) if m else "?")
except Exception as e:
    print("  FAIL:", type(e).__name__, e)

print("=== OpenAlex ===")
for term in ["prompt engineering", "large language model", "LLM agent", "chain of thought"]:
    try:
        u = "https://api.openalex.org/works?search=" + urllib.parse.quote(term) + "&per-page=1&mailto=" + MAILTO
        d = json.loads(get(u))
        print(f"  '{term}': {d['meta']['count']:,} works")
    except Exception as e:
        print(f"  '{term}' FAIL:", type(e).__name__, e)

print("=== Crossref ===")
try:
    u = "https://api.crossref.org/works?query=prompt+engineering+large+language+model&rows=1&mailto=" + MAILTO
    d = json.loads(get(u))
    print("  total:", f"{d['message']['total-results']:,}")
except Exception as e:
    print("  FAIL:", type(e).__name__, e)

print("=== GitHub API (keyless) ===")
try:
    u = "https://api.github.com/search/repositories?q=awesome+prompts+llm&per_page=1"
    d = json.loads(get(u))
    print("  reachable: YES   repo hits:", f"{d.get('total_count',0):,}")
except Exception as e:
    print("  FAIL:", type(e).__name__, e)

print("=== HuggingFace datasets (keyless) ===")
try:
    u = "https://huggingface.co/api/datasets?search=prompt&limit=3"
    d = json.loads(get(u))
    print("  reachable: YES   sample:", [x['id'] for x in d][:3])
except Exception as e:
    print("  FAIL:", type(e).__name__, e)

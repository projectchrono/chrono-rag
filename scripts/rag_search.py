import sys
import json
import urllib.request


def search_api(query: str, top_k: int = 5) -> str:
    payload = json.dumps({"query": query, "top_k": top_k}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["answer"]


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("Usage: rag_search.py <query>", file=sys.stderr)
        sys.exit(1)
    print(search_api(query))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import re
import os
import json
import chromadb
from chromadb.config import Settings

app = Flask(__name__, static_folder='static')
CORS(app)

# ─── Confluence Cloud konfig ──────────────────────────────────────────────────
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_URL",   "https://troyhu.atlassian.net/wiki")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
CONFLUENCE_TOKEN = os.getenv("CONFLUENCE_TOKEN", "")
CONFLUENCE_SPACE    = os.getenv("CONFLUENCE_SPACE",  "SZOFTVERFE")

# ─── Engedélyezett space-ek ───────────────────────────────────────────────────
ALLOWED_SPACES = [
    "SZOFTVERFE",
    "WEBFEJL",
    "",
]

# ─── Ollama konfig ────────────────────────────────────────────────────────────
OLLAMA_URL      = os.getenv("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
EMBED_MODEL     = "nomic-embed-text"  # embedding modell

# ─── ChromaDB konfig ─────────────────────────────────────────────────────────
CHROMA_PATH = "./chroma_db"
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(
    name="confluence_pages",
    metadata={"hnsw:space": "cosine"}
)

# ─── Auth ─────────────────────────────────────────────────────────────────────
def get_auth():    return (CONFLUENCE_EMAIL, CONFLUENCE_TOKEN)
def get_headers(): return {"Accept": "application/json"}

# ─── HTML tisztítás ───────────────────────────────────────────────────────────
def strip_html(html):
    # Kód blokkok tartalmát MEGTARTJUK (ac:plain-text-body)
    html = re.sub(r'<ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body>',
                  lambda m: ' ' + m.group(1) + ' ', html, flags=re.DOTALL)
    # Többi ac: tag eltávolítása
    html = re.sub(r'<ac:[^>]+>', ' ', html)
    html = re.sub(r'</ac:[^>]+>', ' ', html)
    # HTML tagek eltávolítása
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'&nbsp;', ' ', html)
    html = re.sub(r'&amp;',  '&', html)
    html = re.sub(r'&lt;',   '<', html)
    html = re.sub(r'&gt;',   '>', html)
    html = re.sub(r'\s+',    ' ', html).strip()
    return html

# ─── Embedding generálás Ollama-val ──────────────────────────────────────────
def get_embedding(text):
    """Szövegből embedding vektor Ollama nomic-embed-text modellel"""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text[:4000]},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["embedding"]

# ─── Confluence oldalak lekérése ──────────────────────────────────────────────
def fetch_pages_from_space(space):
    try:
        cql = f'space="{space}" AND type=page ORDER BY lastmodified DESC'
        url = f"{CONFLUENCE_BASE_URL}/rest/api/content/search"
        params = {"cql": cql, "limit": 50, "expand": "body.storage,title,space,version"}
        resp = requests.get(url, params=params, auth=get_auth(), headers=get_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception:
        try:
            url = f"{CONFLUENCE_BASE_URL}/rest/api/content"
            params = {"spaceKey": space, "type": "page", "limit": 50, "expand": "body.storage,title,version"}
            resp = requests.get(url, params=params, auth=get_auth(), headers=get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception:
            return []

# ─── Index építés ─────────────────────────────────────────────────────────────
def index_pages(spaces=None):
    """Confluence oldalak indexelése ChromaDB-be embedding-gel"""
    spaces = spaces or ALLOWED_SPACES
    indexed = 0
    skipped = 0

    for space in spaces:
        pages = fetch_pages_from_space(space)
        for page in pages:
            page_id  = page.get("id", "")
            title    = page.get("title", "")
            body_raw = page.get("body", {}).get("storage", {}).get("value", "")
            text     = strip_html(body_raw)
            version  = str(page.get("version", {}).get("number", "0"))

            if not text or len(text) < 50:
                continue

            # Ellenőrzés – már indexelve van-e ugyanez a verzió?
            existing = collection.get(ids=[page_id])
            if existing["ids"] and existing["metadatas"][0].get("version") == version:
                skipped += 1
                continue

            # Embedding generálás
            try:
                full_text = f"{title}\n\n{text}"
                embedding = get_embedding(full_text)
                page_url  = f"{CONFLUENCE_BASE_URL}/pages/viewpage.action?pageId={page_id}"

                collection.upsert(
                    ids=[page_id],
                    embeddings=[embedding],
                    documents=[full_text[:5000]],
                    metadatas=[{
                        "title":   title,
                        "url":     page_url,
                        "space":   space,
                        "version": version
                    }]
                )
                indexed += 1
                print(f"  ✅ Indexelve: {title}")
            except Exception as e:
                print(f"  ❌ Hiba ({title}): {e}")

    return {"indexed": indexed, "skipped": skipped, "total": indexed + skipped}

# ─── Szemantikus keresés ──────────────────────────────────────────────────────
def semantic_search(query, space_key=None, n_results=4):
    """Embedding alapú szemantikus keresés ChromaDB-ben"""
    query_embedding = get_embedding(query)

    where = None
    if space_key:
        where = {"space": space_key}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"]
    )

    pages = []
    for i in range(len(results["ids"][0])):
        pages.append({
            "title":    results["metadatas"][0][i]["title"],
            "url":      results["metadatas"][0][i]["url"],
            "text":     results["documents"][0][i],
            "distance": results["distances"][0][i]
        })

    return pages

# ─── Ollama válasz ────────────────────────────────────────────────────────────
def ask_ollama(question, context):
    system = (
        "Te egy belső vállalati tudásbázis asszisztens vagy. "
        "KIZÁRÓLAG a megadott Confluence dokumentáció alapján válaszolsz. "
        "Ha az információ nem szerepel a dokumentációban, pontosan ezt mondd: "
        "'Ezt az információt nem találom a Confluence dokumentációban.' "
        "Soha ne találj ki semmit. Légy tömör és pontos. "
        "Magyarul válaszolj, ha magyarul kérdeznek."
    )
    user = f"Confluence dokumentáció:\n---\n{context}\n---\n\nKérdés: {question}\n\nVálasz csak a fenti dokumentáció alapján:"

    payload = {
        "model":    OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192}
    }
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "Nem érkezett válasz.")

# ─── API végpontok ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/ask", methods=["POST"])
def ask():
    data      = request.get_json()
    question  = data.get("question", "").strip()
    space_key = data.get("space_key", "").strip() or None

    if not question:
        return jsonify({"error": "Kérdés megadása kötelező."}), 400

    try:
        # Szemantikus keresés
        results = semantic_search(question, space_key)

        if not results:
            return jsonify({
                "answer":  "Nem találtam releváns oldalt ehhez a kérdéshez a Confluence-ban.",
                "sources": []
            })

        # Kontextus összeállítása
        context = "\n\n---\n\n".join(
            f"### {r['title']}\n{r['text'][:3000]}" for r in results
        )

        answer  = ask_ollama(question, context)
        sources = [{"title": r["title"], "url": r["url"]} for r in results]

        return jsonify({"answer": answer, "sources": sources})

    except requests.exceptions.ConnectionError as e:
        if "11434" in str(e):
            return jsonify({"error": "❌ Ollama nem fut! Terminálban: ollama serve"}), 503
        return jsonify({"error": f"Confluence kapcsolati hiba: {str(e)}"}), 503
    except Exception as e:
        return jsonify({"error": f"Hiba: {str(e)}"}), 500


@app.route("/api/index", methods=["POST"])
def reindex():
    """Manuális újraindexelés – ha új oldalakat adtál hozzá"""
    try:
        data      = request.get_json() or {}
        space_key = data.get("space_key")
        spaces    = [space_key] if space_key else None
        result    = index_pages(spaces)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/index/status", methods=["GET"])
def index_status():
    """Index állapot lekérdezése"""
    count = collection.count()
    return jsonify({"indexed_pages": count, "ready": count > 0})


@app.route("/api/spaces", methods=["GET"])
def list_spaces():
    try:
        url  = f"{CONFLUENCE_BASE_URL}/rest/api/space"
        resp = requests.get(url, params={"limit": 50}, auth=get_auth(), headers=get_headers(), timeout=10)
        resp.raise_for_status()
        spaces = [{"key": s["key"], "name": s["name"]} for s in resp.json().get("results", [])]
        return jsonify({"spaces": spaces})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    status = {"confluence": False, "ollama": False, "embed_model": False,
              "model": OLLAMA_MODEL, "indexed_pages": collection.count()}
    try:
        url = f"{CONFLUENCE_BASE_URL}/rest/api/space"
        r   = requests.get(url, auth=get_auth(), headers=get_headers(), params={"limit": 1}, timeout=5)
        status["confluence"] = r.status_code == 200
    except: pass
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            status["ollama"]       = True
            status["embed_model"]  = any(EMBED_MODEL in m for m in models)
            status["available_models"] = models
    except: pass
    return jsonify(status)


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    print("=" * 55)
    print("  🚀  Confluence RAG AI  –  http://localhost:5000")
    print("=" * 55)
    print(f"  📡  Confluence : {CONFLUENCE_BASE_URL}")
    print(f"  🤖  Ollama     : {OLLAMA_URL}  [{OLLAMA_MODEL}]")
    print(f"  🧠  Embedding  : {EMBED_MODEL}")
    print(f"  📦  ChromaDB   : {CHROMA_PATH}")
    print(f"  📄  Indexelt oldalak: {collection.count()}")
    print("=" * 55)
    print()

    # Automatikus indexelés ha üres az adatbázis
    if collection.count() == 0:
        print("  ⏳ Első indítás – oldalak indexelése...")
        result = index_pages()
        print(f"  ✅ Kész! {result['indexed']} oldal indexelve.")
        print()

    app.run(debug=True, port=5000)

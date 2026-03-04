# 🤖 Confluence AI – Lokális RAG Asszisztens

> Kérdezz a céges Confluence dokumentációból – az AI **kizárólag a saját tudásbázisodból** válaszol, semmi mást nem talál ki. Teljesen lokális, Ollama alapú megoldás.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)
![Ollama](https://img.shields.io/badge/Ollama-local-green)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector--db-orange)
![Confluence](https://img.shields.io/badge/Confluence-Cloud-blue?logo=confluence)

---

## ✨ Funkciók

- 🔍 **Szemantikus keresés** – Embedding alapú RAG, nem csak kulcsszó egyezés
- 🧠 **Lokális AI** – Ollama + qwen2.5:7b, semmi nem megy ki a gépről
- 📡 **Élő Confluence API** – Mindig friss adatok, nincs manuális export
- 🗂️ **Több space támogatás** – Egyszerre több Confluence munkaterület
- 🔄 **Újraindexelés gomb** – Ha új oldalt adsz hozzá, egy kattintás és kész
- 🌐 **Webes UI** – Böngészőből használható chat felület

---

## 🏗️ Architektúra

```
Confluence Cloud API
        ↓
   Oldalak lekérése (REST API)
        ↓
   HTML → tiszta szöveg
        ↓
   nomic-embed-text (Ollama) → vektorok
        ↓
   ChromaDB (lokális vektoros adatbázis)
        ↓
   Kérdés → embedding → legközelebbi oldalak
        ↓
   qwen2.5:7b (Ollama) → válasz a kontextus alapján
        ↓
   Webes chat UI (Flask + HTML/JS)
```

---

## 📋 Követelmények

| Eszköz | Verzió | Leírás |
|--------|--------|--------|
| Python | 3.10+ | Backend |
| Ollama | latest | Lokális AI futtatás |
| Git | bármely | Verziókezelés |
| Confluence | Cloud / Server | Tudásbázis forrása |

**Minimális hardver:**
- RAM: 8GB (16GB ajánlott)
- VRAM: nem szükséges (CPU-n is fut)
- Tárhely: ~8GB (modellek + ChromaDB)

---

## ⚡ Telepítés

### 1. Repo klónozása

```bash
git clone https://github.com/FELHASZNALONEV/confluence-ai.git
cd confluence-ai
```

### 2. Python csomagok telepítése

```bash
pip install flask flask-cors requests chromadb
```

### 3. Ollama telepítése

**Windows / Mac:** Töltsd le: [https://ollama.com](https://ollama.com)

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 4. Modellek letöltése

```bash
# Fő AI modell (~4.7GB)
ollama pull qwen2.5:7b

# Embedding modell (~274MB)
ollama pull nomic-embed-text
```

### 5. Konfiguráció

Nyisd meg az `app.py`-t és töltsd ki a saját adataiddal:

```python
CONFLUENCE_BASE_URL = "https://SAJAT_DOMAIN.atlassian.net/wiki"
CONFLUENCE_EMAIL    = "email@example.com"
CONFLUENCE_TOKEN    = "ATATT3x..."   # Atlassian API token
CONFLUENCE_SPACE    = "SPACE_KEY"    # Alapértelmezett space

ALLOWED_SPACES = [
    "SPACE_KEY_1",
    "SPACE_KEY_2",
]
```

> **API token generálás:** https://id.atlassian.com/manage-profile/security/api-tokens

> **Space key lekérése:**
> ```
> https://SAJAT_DOMAIN.atlassian.net/wiki/rest/api/space
> ```

### 6. Static mappa létrehozása

```bash
mkdir static
# Másold az index.html-t a static/ mappába
```

---

## 🚀 Indítás

```bash
# Terminal 1 – Ollama szerver
ollama serve

# Terminal 2 – Flask backend
python app.py
```

Böngészőben: **http://localhost:5000**

**Első indításkor** az alkalmazás automatikusan indexeli az összes Confluence oldalt (~1-2 perc).

---

## 📁 Projekt struktúra

```
confluence-ai/
├── app.py                  # Flask backend + RAG logika
├── static/
│   └── index.html          # Webes chat UI
├── chroma_db/              # ChromaDB (auto-generált, ne commitold!)
├── requirements.txt        # Python függőségek
└── README.md
```

---

## 🔧 Confluence jogosultságok beállítása

A Confluence Free csomagban az API-hoz szükséges a space publikus elérése:

1. Menj: `https://DOMAIN.atlassian.net/wiki/spaces/SPACE_KEY/settings/permissions`
2. Kattints: **„Jogosultság megadása ehhez a munkatérhez az összes felhasználó részére"**

---

## 💡 Használat

**Kérdezés** – Írd be a kérdésedet, az AI a Confluence dokumentációból válaszol.

**Space szűrés** – A sidebar legördülő menüjéből válaszd ki melyik space-ben keressen.

**Újraindexelés** – Ha új oldalt adtál hozzá Confluence-ban, kattints az **„Újraindexelés"** gombra.

**Új space hozzáadása** – Az `app.py`-ban add hozzá az `ALLOWED_SPACES` listához:
```python
ALLOWED_SPACES = [
    "MEGLEVO_SPACE",
    "UJ_SPACE",        # ← új sor
]
```

---

## 🛠️ Hibaelhárítás

| Hiba | Ok | Megoldás |
|------|----|----------|
| Confluence 🔴 | Hibás API token | Generálj új tokent az Atlassian fiókban |
| Confluence 🔴 | 403 Forbidden | Állítsd be a space jogosultságokat |
| Ollama 🔴 | Nem fut | Futtasd: `ollama serve` |
| „Nem találom..." | Üres index | Kattints az Újraindexelés gombra |
| ChromaDB hiba | Foglalt fájlok | Állítsd le az app.py-t, töröld a `chroma_db` mappát |

---

## 🔒 Adatvédelem

- Az AI **lokálisan fut** – az adatok nem hagyják el a gépedet
- Confluence adatok csak a lokális ChromaDB-be kerülnek
- Nincs külső API hívás (csak Confluence + Ollama, mindkettő a te irányításod alatt)

---

## 📦 requirements.txt

```
flask
flask-cors
requests
chromadb
```

---

## 🤝 Fejlesztési ötletek

- [ ] Streaming válaszok (valós idejű gépelés effekt)
- [ ] Confluence webhook – automatikus újraindexelés új oldalnál
- [ ] Chat előzmények mentése
- [ ] Docker konténerizáció

---

## 📄 Licenc

MIT License – használd szabadon, módosítsd, terjeszd!

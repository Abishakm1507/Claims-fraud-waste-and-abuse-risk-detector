# SETUP — start here

Follow these in order. Nothing to edit except one line (your API key).

---

## Step 0 — Extract

Extract the zip somewhere simple, e.g. `C:\Users\YourName\Desktop\`.

You should end up with a folder called `healthcare-fraud-investigation`
containing `backend`, `frontend`, `scripts`, `README.md`.

Open **that** folder in VS Code (File → Open Folder).

If you see a folder called `healthcare-fraud-investigation` *inside*
`healthcare-fraud-investigation`, you opened one level too high — go one deeper.

---

## Step 1 — Python setup

Open a terminal in VS Code (`Ctrl` + `` ` ``). Run these one at a time:

```
python -m venv .venv
```

```
.venv\Scripts\activate
```
(Mac/Linux: `source .venv/bin/activate`)

You should now see `(.venv)` at the start of your terminal line.

```
pip install -r requirements.txt
```

This is the big one — a few GB, takes several minutes. Let it finish.

---

## Step 2 — Add your API key

Copy the example env file:

```
copy .env.example .env
```
(Mac/Linux: `cp .env.example .env`)

Open the new `.env` file in VS Code. Find this line:

```
LLM_API_KEY=sk-your-key-here
```

Replace `sk-your-key-here` with your real OpenAI key. Save the file.

*(Using Gemini instead? `.env` has a commented OPTION B block — comment out the
four OpenAI lines, uncomment the four Gemini lines. No code changes needed.)*

---

## Step 3a — Data

**Nothing to do if this module sits in the project repo.** The assistant finds
the ETL's curated tables automatically — at the repo root, above this module, or
in a sibling project. Confirm with:

```
python -c "from backend.data import warehouse as wh; print(wh.source())"
```

- `curated` → reading ETL output. Done.
- `local warehouse` → using its own build (see below).
- error → no data connected; knowledge questions still work.

**If the curated tables are elsewhere**, set the path in `.env`:

```
CURATED_DIR=/absolute/path/to/data/curated
```

**Only if there is no ETL output at all** — running standalone — put the source
CSVs in `data_raw/` and run `python scripts/build_data.py`.

---

## Step 3 — Build the knowledge index

```
python scripts/build_index.py
```

First run downloads an 80 MB model. It should end with something like
`204 chunks indexed`.

Only re-run this if you edit files in `backend/knowledge/`.

---

## Step 4 — Test it in the terminal

```
python scripts/ask.py "what is upcoding"
```

If you get a written answer with sources listed, the whole backend works.

---

## Step 5 — Start the backend

```
uvicorn backend.main:app --reload --port 8732
```

Leave this terminal running. Check it by opening http://localhost:8732/docs

---

## Step 6 — Start the frontend

Open a **second** terminal (`Ctrl` + `Shift` + `` ` ``). Then:

```
cd frontend
```

```
npm install
```

```
npm run dev
```

Open **http://localhost:5193**

---

## After integrating into the main repo

No configuration required. Verify with one request:

```
GET http://localhost:8732/api/status
```

| Field | Meaning |
| --- | --- |
| `data.reading_from` | `curated` — reading the ETL's shared tables |
| `data.curated_path` | the exact directory used |
| `model.connected` | provider risk scores loaded |
| `model.multi_agent.connected` | `true` — synthesis scores live |

When `multi_agent.connected` is `true`, provider questions report the
**synthesis score** with the provider model's score shown as one of its
components. When `false`, the message says why and the assistant falls back to
the provider risk score alone.

## Every time after this

Two terminals, from the project folder:

**Terminal 1**
```
.venv\Scripts\activate
uvicorn backend.main:app --reload --port 8732
```

**Terminal 2**
```
cd frontend
npm run dev
```

You do NOT need to rebuild the index or reinstall anything.

---

## Checks and fixes

| Command | Expected |
| --- | --- |
| `python scripts/verify_structure.py` | `20/20 knowledge documents present` |
| `python scripts/ask.py "what is upcoding"` | An answer with sources |
| `python scripts/query.py --status` | 10 tables loaded |
| `python scripts/query.py 1003053851 --peers` | A peer comparison |

**"Cannot reach the backend"** in the UI → Terminal 1 isn't running, or you
forgot `--port 8732`.

**"Knowledge index not available"** → run `python scripts/build_index.py`.

**`ModuleNotFoundError`** → the venv isn't active. Run `.venv\Scripts\activate`.

**`python` not recognised** → try `python3` and `pip3`.

**Port already in use** → pick any other number, but change it in *both*
`frontend/vite.config.js` and your `uvicorn --port` command.

---

## What works right now

- **KNOWLEDGE questions** — "What is upcoding?" → answered from the 20-document
  knowledge base, with sources and similarity scores.
- **DATA questions** — real answers from the datasets: provider lookups, peer
  comparisons, rankings, threshold filters, claim lookups.
- **MODEL questions** — "What is this provider's risk score?" → says the risk
  engine isn't connected. It does not invent a score.
- **INVESTIGATION questions** — explains using knowledge and real data, and
  names what the risk engine would add.

Identifiers are real: providers are 10-digit NPIs (e.g. `1003053851`), claims
are negative integers (e.g. `-10000930037832`).

Phases 1–8 are complete. Phase 9 needs the risk engine.

For how the code works and likely questions about it, read `WALKTHROUGH.md`.

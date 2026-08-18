# Frontend — Investigation Assistant

React + Vite + Axios chat interface.

## Run

Start the backend first, from the project root:

```bash
uvicorn backend.main:app --reload --port 8732
```

Then, in this folder:

```bash
npm install
npm run dev
```

Open http://localhost:5193

`vite.config.js` proxies `/api` to `http://localhost:8732`, so no CORS setup or
environment file is needed for local development.

## Structure

```
src/
├── App.jsx                     state, send loop, layout
├── styles.css                  all styling
├── api/client.js               axios calls + error messages
└── components/
    ├── Message.jsx             one turn
    ├── Answer.jsx              renders Markdown, colour-codes headings
    ├── Composer.jsx            input, Enter to send
    ├── EmptyState.jsx          starter questions
    └── ContextSidebar.jsx      case context + risk factors
```

## The sidebar is conditional

`ContextSidebar` returns `null` unless the API sends a real `risk_score`. Today
that field is `null`, so the chat runs full width and no sidebar appears.

When the detection engine is connected (Phase 9), the same field populates and
the sidebar appears automatically beside the chat — no component changes.

There are no placeholder scores or sample rows anywhere in this UI. A value on
screen is always a value the backend actually returned.

## Answer headings

The assistant writes answers with short `###` headings. `Answer.jsx` colours
them by what they say — legitimate explanations, what it means, what to
investigate next — so an investigator can scan for the part they need.

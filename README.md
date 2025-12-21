# THEO – Personal Multi-Model AI Assistant

THEO is a personal, self-hosted AI assistant designed to route user requests to the most appropriate AI model based on intent, while maintaining continuity across models.

The goal is not “one model to rule them all”, but a system that:
- Uses different models for different tasks
- Preserves user context when models change
- Remains fully under the user’s control

This repository contains both the backend and frontend for THEO.

---

## What THEO Does (Current)

- Chat-based UI similar to ChatGPT
- Multiple AI providers supported (e.g. Mock, OpenAI, Anthropic)
- Provider selection via UI
- Session-based conversations
- Persistent storage using SQLite
- Streaming responses over Socket.IO
- Basic memory capture (“remember X”) stored server-side
- Settings panel (e.g. debug logging toggle)

---

## What THEO Is Becoming (Design Goals)

- Intent-based routing (e.g. coding → one model, general chat → another)
- Cross-model continuity using summaries instead of raw chat history
- Pluggable provider architecture
- Self-hosted, Dockerised deployment (Unraid target)
- Strong guardrails to avoid hallucinations
- Explicit memory control (remember / forget)

The project is deliberately evolving in small, testable steps.

---

## Repository Structure

```
theo/
├── backend/
│   ├── app.py          # Flask app + Socket.IO
│   ├── core/
│   │   ├── router.py   # Intent routing + provider selection
│   │   ├── context.py  # Context & summary construction
│   │   └── memory.py   # SQLite-backed persistence
│   ├── providers/
│   │   ├── mock.py
│   │   ├── openai.py
│   │   └── anthropic.py
│   └── theo.db         # Local SQLite database (ignored in git)
│
├── frontend/
│   ├── src/
│   │   ├── App.svelte
│   │   ├── Chat.svelte
│   │   ├── Settings.svelte
│   │   └── api.js
│   └── public/
│       └── style.css
│
├── README.md
└── .gitignore
```

---

## Running Locally

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Backend runs on:
```
http://localhost:1066
```

---

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on:
```
http://localhost:5174
```

---

## Providers

Providers are defined in the database and surfaced in the UI.

Each provider specifies:
- Type (mock, openai, anthropic, etc.)
- Base URL (if applicable)
- Model name
- API key
- Enabled/disabled state

Routing decisions are made server-side.

---

## Debug Logging

Debug logging can be enabled via:
- Settings panel (UI), or
- API:
```bash
curl -X POST http://localhost:1066/api/settings/debug \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

When enabled, internal routing and context decisions are logged to the backend console.

---

## Important Notes

- This is not a finished product
- Expect breaking changes while architecture settles
- SQLite is used intentionally for simplicity during early development
- Memory handling and cross-model continuity are still evolving

---

## License

No license applied yet.  
This project is currently private / experimental.

---

## Author

Built by Danny Black.  
THEO is being developed as both a tool and a learning platform.

# Eloquence

A local voice-based speaking-assessment app in the style of a TOEFL independent-speaking test.
Log in, answer four spoken questions (45 seconds each), and get a per-dimension score and
TOEFL-style band with examiner reasoning — all evaluated by a **local Ollama** model. Your
progress is tracked across unlimited assessments.

## How it works

```
Browser (login + mic via Web Speech API)
    │  question read aloud (TTS) → you speak 45s → transcript
    ▼
FastAPI  ──►  LangGraph scoring pipeline  ──►  Ollama (qwen2.5)
    │              START ┬─ grammar ──┐
    │                    ├─ ideation ─┤
SQLite              (parallel) flow   ┼─ aggregate ─► band + reasoning
(users, history)          └─ structure┘
```

- **Voice:** browser Web Speech API — speech-to-text for answers, text-to-speech for questions. Use **Chrome or Edge**.
- **Questions:** generated fresh each assessment by the local model (static fallback if Ollama is down), so sessions never repeat.
- **Scoring (TOEFL 2026 "Take an Interview" rubric):** a LangGraph graph scores the four ETS criteria — **Fluency, Intelligibility, Language Use (grammar + vocabulary), Organization** — on the official **0–5** scale in parallel, then an aggregator maps the mean to a **1–6 band** aligned to CEFR (A1 → C2) with examiner reasoning.
  - *Caveat:* the app evaluates the speech-to-text transcript only (no audio), so **Intelligibility (pronunciation/prosody) is approximated** from transcript proxies such as fillers, fragmentation and recycled language.
- **Progress:** per-user auth; every assessment and per-dimension average is stored in SQLite and shown as a trend.

## Setup

```bash
# 1. Ollama must be running with the model pulled
ollama pull qwen2.5
ollama serve        # if not already running

# 2. Python deps
cd TOEFL-VOICE
python -m venv .venv
.venv/Scripts/activate        # Windows (bash):  source .venv/Scripts/activate
pip install -r requirements.txt

# 3. Run (port 8010 — 8000 is often taken on this machine)
cd backend
uvicorn main:app --port 8010
```

Open http://localhost:8010 in **Chrome or Edge** and register an account.

## Performance

Scoring runs 5 model calls per response (4 criteria + 1 examiner summary).

**Fastest option — Groq (free cloud, recommended):** inference drops from minutes to
a few seconds, and quality improves. Get a free key at https://console.groq.com, then:

```bash
export GROQ_API_KEY=gsk_your_key_here     # Windows bash
uvicorn main:app --port 8010              # provider auto-switches to Groq
```

The app auto-selects Groq whenever `GROQ_API_KEY` is set (override with
`ELOQUENCE_PROVIDER=ollama`). Default Groq model: `openai/gpt-oss-120b`.
Note: with a cloud provider, candidate transcripts leave your machine; local Ollama
keeps everything on-device.

**Local, smaller model:** stay on Ollama but use a lighter model:

```bash
ollama pull qwen2.5:3b
ELOQUENCE_MODEL=qwen2.5:3b uvicorn main:app --port 8010
```

The local model is warmed at startup, so the first response after launch is the slowest.

## Config (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `ELOQUENCE_PROVIDER` | `ollama` (or `groq` if key set) | Inference provider: `ollama` or `groq` |
| `GROQ_API_KEY` | — | Groq key; its presence auto-enables Groq |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model |
| `ELOQUENCE_MODEL` | `qwen2.5:latest` | Ollama model for scoring & question generation |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |
| `ELOQUENCE_DB` | `backend/eloquence.db` | SQLite path |

## Notes
- Passwords are salted + PBKDF2-hashed; sessions use bearer tokens in `localStorage`.
- This is a local practice tool and is not affiliated with or endorsed by ETS/TOEFL.

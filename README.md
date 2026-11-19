# Eloquence – AI-Powered Speaking Assessment Platform

Eloquence is a local, voice-based speaking assessment and improvement platform inspired by the TOEFL independent-speaking format. Users can log in, complete four spoken questions (45 seconds per response), and receive dimension-wise scores, examiner-style feedback, and a TOEFL-style performance band.

Built with **Python, FastAPI, LangGraph, Groq GPT-OSS-120B, SQLite, and Ollama**, Eloquence uses parallel LLM evaluation to assess speaking responses and track progress across unlimited practice assessments.

## How It Works

The application follows a browser-to-backend architecture. The browser handles voice interaction, FastAPI manages authentication and requests, and LangGraph orchestrates the evaluation workflow.

### System Architecture

```mermaid
flowchart TD
    subgraph Browser["Browser – Frontend"]
        UI["Login & Assessment Interface"]
        TTS["Text-to-Speech<br/>SpeechSynthesis API"]
        STT["Speech-to-Text<br/>Web Speech API"]
        TRANSCRIPT["Live Transcript"]
        UI --> TTS
        TTS --> UI
        UI --> STT
        STT --> TRANSCRIPT
    end

    subgraph Backend["FastAPI Backend"]
        API["Authentication & API Endpoints"]
        QUESTIONS["Question Generation<br/>Local Ollama Model"]
        SCORE["Assessment Submission<br/>Transcript Text"]
    end

    subgraph Workflow["LangGraph – Scoring Pipeline"]
        START["START"]
        F["Fluency"]
        I["Intelligibility"]
        L["Language Use"]
        O["Organization"]
        AGG["Aggregation & Examiner Feedback"]
        END["END"]

        START --> F
        START --> I
        START --> L
        START --> O
        F --> AGG
        I --> AGG
        L --> AGG
        O --> AGG
        AGG --> END
    end

    subgraph Inference["LLM Inference Layer"]
        GROQ["Groq API<br/>GPT-OSS-120B"]
        OLLAMA["Local Ollama<br/>Qwen 2.5"]
    end

    subgraph Storage["SQLite Database"]
        DB["Users · Assessments · Scores<br/>History · Progress"]
    end

    UI --> API
    API --> QUESTIONS
    API --> SCORE
    QUESTIONS --> OLLAMA
    SCORE --> START
    F -.-> GROQ
    I -.-> GROQ
    L -.-> GROQ
    O -.-> GROQ
    AGG -.-> GROQ
    API <--> DB
    AGG --> API
    API --> UI
```

### 1. Voice Interaction – Browser

- **Speech-to-Text (STT):** Uses the browser's Web Speech API (`webkitSpeechRecognition`) to convert spoken responses into text.
- Recognition runs with `continuous` and `interimResults` enabled, allowing the application to display a live transcript as the user speaks.
- Finalized recognition chunks are appended to the final transcript, while interim results are displayed as provisional text.
- **Text-to-Speech (TTS):** Uses the browser's `speechSynthesis` API and `SpeechSynthesisUtterance` to read the topic and questions aloud.
- The question-reading sequence triggers the preparation countdown when speech synthesis finishes.

**Browser compatibility:** Chrome or Edge is recommended.

**Audio handling:** The application backend receives and evaluates transcript text, not raw audio recordings. Browser speech recognition may use browser-vendor or operating-system speech services, depending on the implementation; therefore, this does not guarantee that audio processing stays entirely on-device.

### 2. Question Generation

Each assessment generates a fresh set of speaking questions using the local Ollama model.

- Questions are generated dynamically rather than relying exclusively on a fixed question bank.
- A static fallback is available if Ollama is unavailable.
- The generated questions are presented through the browser's text-to-speech interface.

### 3. Parallel Evaluation – LangGraph

LangGraph orchestrates four specialized scoring nodes. Each node evaluates the submitted transcript against a separate speaking dimension.

| Scoring node | Evaluation focus |
|---|---|
| **Fluency** | Response flow, continuity, hesitation, and unnecessary repetition |
| **Intelligibility** | Clarity of expression and transcript-based indicators of comprehensibility |
| **Language Use** | Grammar, vocabulary, and language accuracy |
| **Organization** | Coherence, logical sequencing, and development of ideas |

**Workflow:**

`START → Four parallel scoring nodes → Aggregation → END`

- Each scoring node makes a specialized LLM call.
- Each dimension receives a score on a 0–5 scale along with reasoning.
- The four evaluations execute in parallel, rather than sequentially.
- The aggregation stage combines the dimension scores, calculates the mean, maps it to the application's 1–6 performance band, and generates examiner-style feedback.

The scoring workflow uses five model calls: four dimension-specific evaluations and one examiner-summary generation call.

### 4. LLM Inference – Groq and Ollama

Eloquence supports two inference options:

**Groq – Recommended**

- Uses Groq's inference API with `openai/gpt-oss-120b` as the default model.
- Provides faster cloud inference compared with running the model locally.
- Automatically selected when `GROQ_API_KEY` is configured, unless overridden.

**Ollama – Local Inference**

- Supports local inference using Qwen 2.5.
- Can be used for question generation and scoring when configured as the inference provider.
- Keeps model inference local, without sending transcript text to Groq.
- The model is warmed up at application startup; the first response may take longer.

Groq provides the inference infrastructure; GPT-OSS-120B is the model.

### 5. Score Aggregation and Progress Tracking

After the parallel evaluations complete:

1. Individual dimension scores are collected.
2. The mean score is calculated.
3. The mean is mapped to an application-defined 1–6 TOEFL-style performance band.
4. Examiner-style reasoning and feedback are generated.
5. Assessment results are stored in SQLite.

The application supports per-user authentication and maintains assessment history, individual scores, dimension-wise averages, and progress trends across practice sessions.

## Important Evaluation Limitation

Eloquence evaluates the **speech-to-text transcript, not the original audio**.

Consequently, it cannot directly measure acoustic pronunciation, accent, intonation, stress, or prosody. The intelligibility dimension is approximated using textual indicators such as fillers, fragmented expressions, incomplete sentences, and repeated language.

The TOEFL speaking criteria serve as a reference framework. The application's 1–6 band is an internally defined mapping and is not an official ETS score or a validated TOEFL prediction.

Eloquence is an independent practice tool and is not affiliated with or endorsed by ETS.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Speech-to-Text | Browser Web Speech API |
| Text-to-Speech | Browser SpeechSynthesis API |
| Backend | Python, FastAPI |
| Workflow orchestration | LangGraph |
| Cloud inference | Groq API – GPT-OSS-120B |
| Local inference | Ollama – Qwen 2.5 |
| Database | SQLite |
| Authentication | Salted PBKDF2 password hashing, bearer tokens |

## Setup and Installation

### Prerequisites

- Python installed
- [Ollama](https://ollama.com/) installed
- Chrome or Edge browser

### 1. Start Ollama

Pull the required model:

```bash
ollama pull qwen2.5
```

Start the Ollama server if it is not already running:

```bash
ollama serve
```

### 2. Create a Python Environment

From the project root:

```powershell
cd TOEFL-VOICE

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Start the Application

```powershell
cd backend
uvicorn main:app --port 8010
```

Open the application in Chrome or Edge:

**http://localhost:8010**

Register an account and begin your speaking assessment.

## Performance and Model Configuration

### Option 1: Groq Cloud Inference (Recommended)

Groq provides faster inference, reducing the waiting time associated with running larger models locally.

1. Create an API key at [Groq Console](https://console.groq.com/).
2. Configure the key in PowerShell:

```powershell
$env:GROQ_API_KEY="gsk_your_key_here"
```

3. Start the application:

```powershell
uvicorn main:app --port 8010
```

The application automatically selects Groq when `GROQ_API_KEY` is available, unless overridden by `ELOQUENCE_PROVIDER`.

### Option 2: Local Ollama Inference

For a lighter local model:

```bash
ollama pull qwen2.5:3b
```

Configure the model:

```powershell
$env:ELOQUENCE_PROVIDER="ollama"
$env:ELOQUENCE_MODEL="qwen2.5:3b"
```

Then start the application:

```powershell
uvicorn main:app --port 8010
```

**Privacy consideration:** With Groq cloud inference, transcript text is sent to Groq for processing. With local Ollama inference, model inference happens locally. Browser speech recognition may still involve external browser-vendor services.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ELOQUENCE_PROVIDER` | `ollama` (or Groq when a key is configured) | Selects the inference provider |
| `GROQ_API_KEY` | Not set | Groq API authentication |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model selection |
| `ELOQUENCE_MODEL` | `qwen2.5:latest` | Ollama model selection |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server endpoint |
| `ELOQUENCE_DB` | `backend/eloquence.db` | SQLite database location |

## Security

- User passwords are stored as salted PBKDF2 hashes.
- Authentication uses bearer tokens.
- Session tokens are stored in browser `localStorage`.
- API keys should be configured through environment variables and must never be committed to GitHub.
- `.env` files and local database files should be excluded from version control.

## Project Goal

Eloquence aims to make structured speaking practice more accessible by combining browser-based voice interaction, parallel LLM-based assessment, examiner-style feedback, and persistent progress tracking in one application.
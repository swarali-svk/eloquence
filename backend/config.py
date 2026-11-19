import os


def _load_dotenv():
    """Load backend/.env into os.environ (without overriding existing vars)."""
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()

# Inference provider: "ollama" (local, default) or "groq" (fast cloud).
# Auto-selects groq if a GROQ_API_KEY is present and provider isn't forced.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
PROVIDER = os.environ.get(
    "ELOQUENCE_PROVIDER", "groq" if GROQ_API_KEY else "ollama"
).lower()

# Ollama (local)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("ELOQUENCE_MODEL", "qwen2.5:latest")

# Groq (cloud, OpenAI-compatible)
GROQ_HOST = os.environ.get("GROQ_HOST", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

DB_PATH = os.environ.get("ELOQUENCE_DB", os.path.join(os.path.dirname(__file__), "eloquence.db"))

# Seconds a candidate speaks per response (TOEFL-style independent task).
RESPONSE_SECONDS = 45
# Number of questions per assessment.
QUESTIONS_PER_ASSESSMENT = 4

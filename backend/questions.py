import random

from scoring.ollama_client import chat_json, OllamaError

# Topic domains for the single-topic interview. One is picked per assessment,
# and all four questions explore that one topic (2026 "Take an Interview" format).
TOPIC_DOMAINS = [
    "education and learning",
    "technology and the internet",
    "work and careers",
    "environment and sustainability",
    "culture and traditions",
    "health and lifestyle",
    "travel and places",
    "friendship and relationships",
    "media and entertainment",
    "money and consumer choices",
    "city life vs rural life",
    "art, music and creativity",
    "community and social responsibility",
    "food and cooking",
    "sports and competition",
    "family and generations",
]

# Fallback interviews (single topic, 4 connected questions) if the model is down.
_FALLBACK = [
    {
        "topic": "Technology in daily life",
        "questions": [
            "How often do you use technology in your daily life, and for what?",
            "What is one app or device you would find hard to live without, and why?",
            "Do you think people today rely too much on technology? Explain.",
            "How do you imagine technology will change your routine in ten years?",
        ],
    },
    {
        "topic": "Travel and places",
        "questions": [
            "Do you enjoy traveling? Tell me about a place you like to visit.",
            "What makes that place special to you compared to others?",
            "Do you prefer traveling alone or with others? Why?",
            "If you could travel anywhere next year, where would you go and why?",
        ],
    },
    {
        "topic": "Learning and education",
        "questions": [
            "What subject or skill do you most enjoy learning about, and why?",
            "How do you usually learn best — alone, in a group, or hands-on?",
            "Do you think schools focus on the right things? Explain your view.",
            "What is one thing you would like to learn in the future, and why?",
        ],
    },
]

_SYSTEM = (
    "You are an official TOEFL 2026 'Take an Interview' item writer. In this task a "
    "candidate has a simulated interview about ONE everyday topic and answers a series of "
    "connected questions about it.\n\n"
    "Authentic TOEFL interview topics are familiar, personal, and experience-based — things "
    "any test-taker can speak about from their own life. For example: your daily routine, how "
    "you spend free time, your hometown, a favorite meal or restaurant, how you use "
    "technology or social media, study or work habits, shopping, transport and commuting, "
    "travel, friends and family, music/films/books, staying healthy, or online vs in-person "
    "activities. Avoid academic, technical, abstract, or debate-style topics; avoid anything "
    "requiring specialized knowledge.\n\n"
    "Write a short, natural topic label and exactly N connected interview questions that ALL "
    "explore that one topic, in a realistic interviewer's voice. Progress naturally: Q1 is a "
    "broad, easy opener about the candidate's own experience; the middle questions ask for "
    "details, reasons, and examples; the final question invites an opinion or a simple "
    "hypothetical. Each question must be conversational, self-contained, answerable in about "
    "45 seconds, and phrased in plain spoken English. Return strictly valid JSON."
)


def _generate(n: int) -> dict:
    domain = random.choice(TOPIC_DOMAINS)
    seed = random.randint(1000, 9999)
    user = (
        f"Create one authentic TOEFL 'Take an Interview' set on an everyday topic related to "
        f"'{domain}'. Pick a specific, relatable angle a candidate can answer from personal "
        f"experience, and produce exactly {n} connected questions that stay on that single "
        f"topic (easy personal opener first, then detail/reason/example follow-ups, ending "
        f"with an opinion or simple hypothetical). Keep it conversational and fresh; avoid "
        f"textbook phrasing (random seed {seed}). "
        'Return JSON of the exact form: {"topic": "<short natural topic label>", "questions": '
        f'["...", "...", ...]}} with exactly {n} question strings.'
    )
    data = chat_json(_SYSTEM, user, temperature=0.9)
    topic = str(data.get("topic", domain)).strip() or domain
    qs = data.get("questions", [])
    qs = [q.strip() for q in qs if isinstance(q, str) and q.strip()]
    if len(qs) < n:
        raise OllamaError(f"model returned {len(qs)} questions, expected {n}")
    return {"topic": topic, "questions": qs[:n]}


def sample_interview(n: int) -> dict:
    """Return one interview: {"topic": str, "questions": [str] * n}.

    All questions explore a single topic (TOEFL 2026 "Take an Interview"). Generated
    on demand by the local/cloud model; falls back to a fixed set if unreachable.
    """
    try:
        return _generate(n)
    except OllamaError:
        fb = random.choice(_FALLBACK)
        return {"topic": fb["topic"], "questions": fb["questions"][:n]}

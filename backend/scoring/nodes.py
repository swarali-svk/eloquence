"""Scoring nodes for the Eloquence LangGraph pipeline.

Implements the 2026 TOEFL iBT "Take an Interview" speaking rubric. Each 45-second
answer is scored 0-5 on four ETS criteria — fluency, intelligibility, language use
(grammar + vocabulary), and organization — and an aggregator maps the result to a
1-6 band aligned to CEFR, with examiner reasoning.

Note: this app evaluates a speech-to-text transcript only (no audio), so
`intelligibility` (pronunciation/prosody) is necessarily approximated from
transcript-level proxies such as fillers, fragmentation and recycled language.
"""

from scoring.ollama_client import chat_json

# Official 0-5 holistic descriptors (2026 "Take an Interview" rubric).
SCALE_DESCRIPTORS = (
    "0-5 scale: "
    "5 = fully successful; on topic and well elaborated; natural pauses; easily "
    "intelligible; accurate range of grammar and vocabulary. "
    "4 = generally successful; on topic but may lack effective sentence-level "
    "connectors; good pace with some pausing; minor effort to understand. "
    "3 = partially successful; limited elaboration; frequent or lengthy pauses "
    "produce a choppy pace; filler words frequent. "
    "2 = mostly unsuccessful; minimally connected; often recycles language from the "
    "question itself. "
    "1 = unsuccessful; only vaguely connected to the question; mostly unintelligible. "
    "0 = no response, not in English, or unconnected."
)

CRITERIA = {
    "fluency": (
        "You are an examiner judging FLUENCY: speaking rate, length of uninterrupted "
        "runs, and the number of pauses and hesitations. In a transcript, infer this "
        "from sentence completeness, false starts, repetition and filler words."
    ),
    "intelligibility": (
        "You are an examiner judging INTELLIGIBILITY: how easily a listener follows the "
        "response. True pronunciation/prosody is unavailable from text, so judge clarity "
        "from transcript proxies — fragmentation, recycled question language, and whether "
        "meaning comes across without effort."
    ),
    "language_use": (
        "You are an examiner judging LANGUAGE USE (vocabulary and grammar): vocabulary "
        "diversity and richness (less common words), grammaticality, and accuracy."
    ),
    "organization": (
        "You are an examiner judging ORGANIZATION: discourse coherence, a clear position, "
        "logical progression, elaboration, and use of discourse connectives."
    ),
}

CRITERION_LABELS = {
    "fluency": "Fluency",
    "intelligibility": "Intelligibility",
    "language_use": "Language Use",
    "organization": "Organization",
}


def _score_criterion(crit: str, question: str, transcript: str) -> dict:
    system = (
        f"{CRITERIA[crit]} Score strictly per the TOEFL 2026 rubric. {SCALE_DESCRIPTORS} "
        'Respond ONLY as JSON: {"score": <int 0-5>, "reasoning": "<2-3 sentences citing '
        'specific evidence from the response>"}.'
    )
    user = (
        f"QUESTION:\n{question}\n\n"
        f"CANDIDATE RESPONSE (speech-to-text transcript):\n{transcript}\n\n"
        f"Judge only {CRITERION_LABELS[crit].upper()} on the 0-5 scale."
    )
    data = chat_json(system, user)
    score = data.get("score", 0)
    try:
        score = max(0, min(5, int(round(float(score)))))
    except (TypeError, ValueError):
        score = 0
    return {"score": score, "reasoning": str(data.get("reasoning", "")).strip()}


def make_criterion_node(crit: str):
    def node(state: dict) -> dict:
        return {crit: _score_criterion(crit, state["question"], state["transcript"])}

    return node


# 1-6 band -> CEFR label (2026 score scale).
def cefr_band(band: float) -> str:
    if band >= 6:
        return "C2 (Proficient)"
    if band >= 5:
        return "C1 (Effective)"
    if band >= 4:
        return "B2 (Upper-Intermediate)"
    if band >= 3:
        return "B1 (Lower-Intermediate)"
    if band >= 2:
        return "A2 (Elementary)"
    return "A1 (Beginner)"


def band_from_avg(avg5: float) -> float:
    """Map the mean 0-5 criterion score to a 1-6 band in 0.5 increments."""
    band = 1.0 + avg5  # [0,5] -> [1,6]
    band = round(band * 2) / 2
    return max(1.0, min(6.0, band))


def aggregate_node(state: dict) -> dict:
    crits = {c: state[c] for c in CRITERIA}
    avg5 = sum(c["score"] for c in crits.values()) / len(crits)
    band = band_from_avg(avg5)
    cefr = cefr_band(band)

    system = (
        "You are a senior TOEFL speaking examiner. Given four 0-5 sub-scores "
        "(fluency, intelligibility, language use, organization) and the response, "
        "write a concise holistic justification (3-4 sentences) in an examiner's voice: "
        "note whether the answer was on topic and well elaborated, the strongest "
        'criterion, and the clearest area to improve. Respond ONLY as JSON: '
        '{"reasoning": "<text>"}.'
    )
    user = (
        f"QUESTION:\n{state['question']}\n\n"
        f"RESPONSE:\n{state['transcript']}\n\n"
        f"SUB-SCORES (0-5): fluency={crits['fluency']['score']}, "
        f"intelligibility={crits['intelligibility']['score']}, "
        f"language_use={crits['language_use']['score']}, "
        f"organization={crits['organization']['score']}. "
        f"Band {band}/6 ({cefr})."
    )
    try:
        summary = str(chat_json(system, user).get("reasoning", "")).strip()
    except Exception:
        summary = (
            f"Band {band}/6 ({cefr}). Strongest in "
            f"{CRITERION_LABELS[max(crits, key=lambda c: crits[c]['score'])]}; focus on "
            f"{CRITERION_LABELS[min(crits, key=lambda c: crits[c]['score'])]}."
        )

    return {"overall_score": band, "band_label": cefr, "reasoning": summary}

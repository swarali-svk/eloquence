"""LangGraph pipeline that scores one spoken response (TOEFL 2026 rubric).

    START ─┬─> fluency         ─┐
           ├─> intelligibility ─┤
           ├─> language_use    ─┼─> aggregate ─> END
           └─> organization    ─┘

The four criterion nodes fan out from START, then fan in to the aggregate node
which maps the mean 0-5 score to a 1-6 CEFR band with examiner reasoning.
"""

from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from scoring.nodes import make_criterion_node, aggregate_node, CRITERIA


class ScoreState(TypedDict, total=False):
    question: str
    transcript: str
    fluency: dict
    intelligibility: dict
    language_use: dict
    organization: dict
    overall_score: float
    band_label: str
    reasoning: str


def build_graph():
    g = StateGraph(ScoreState)
    for crit in CRITERIA:
        g.add_node(crit, make_criterion_node(crit))
        g.add_edge(START, crit)
    g.add_node("aggregate", aggregate_node)
    for crit in CRITERIA:
        g.add_edge(crit, "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()


_GRAPH = None


def score_response(question: str, transcript: str) -> dict:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()

    transcript = (transcript or "").strip()
    if len(transcript) < 3:
        empty = {"score": 0, "reasoning": "No audible response was transcribed."}
        return {
            "dimensions": {c: dict(empty) for c in CRITERIA},
            "overall_score": 1.0,
            "band_label": "A1 (Beginner)",
            "reasoning": "No meaningful response was provided for evaluation.",
        }

    final = _GRAPH.invoke({"question": question, "transcript": transcript})
    return {
        "dimensions": {c: final[c] for c in CRITERIA},
        "overall_score": final["overall_score"],
        "band_label": final["band_label"],
        "reasoning": final["reasoning"],
    }

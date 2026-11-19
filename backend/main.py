import os

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from config import QUESTIONS_PER_ASSESSMENT, RESPONSE_SECONDS
from questions import sample_interview
from scoring.graph import score_response

app = FastAPI(title="Eloquence")


@app.middleware("http")
async def _no_cache(request, call_next):
    # Local practice tool: never let the browser serve stale HTML/JS/CSS.
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@app.on_event("startup")
def _startup():
    db.init_db()
    # Warm the model so the first assessment doesn't pay a cold load inside
    # the timed parallel scoring burst. Non-fatal if Ollama is unreachable.
    import threading
    from scoring.ollama_client import chat_json, OllamaError

    def _warm():
        try:
            chat_json("Reply with JSON.", 'Return {"ok": true}.', num_predict=8)
        except OllamaError:
            pass

    threading.Thread(target=_warm, daemon=True).start()


# ---------------- schemas ----------------

class Credentials(BaseModel):
    username: str
    password: str


class ScoreRequest(BaseModel):
    assessment_id: int
    question_idx: int
    question_text: str
    transcript: str
    duration: float = 0.0


# ---------------- auth dependency ----------------

def current_user(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    user = db.user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------- auth routes ----------------

@app.post("/api/register")
def register(creds: Credentials):
    if len(creds.username.strip()) < 3 or len(creds.password) < 4:
        raise HTTPException(400, "Username must be 3+ chars and password 4+ chars.")
    if db.get_user_by_name(creds.username):
        raise HTTPException(409, "Username already taken.")
    uid = db.create_user(creds.username.strip(), creds.password)
    token = db.issue_token(uid)
    return {"token": token, "username": creds.username.strip()}


@app.post("/api/login")
def login(creds: Credentials):
    user = db.verify_user(creds.username.strip(), creds.password)
    if not user:
        raise HTTPException(401, "Invalid username or password.")
    token = db.issue_token(user["id"])
    return {"token": token, "username": user["username"]}


@app.post("/api/logout")
def logout(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    db.revoke_token(token)
    return {"ok": True}


# ---------------- assessment routes ----------------

@app.post("/api/assessment/start")
def start_assessment(user=Depends(current_user)):
    interview = sample_interview(QUESTIONS_PER_ASSESSMENT)
    aid = db.start_assessment(user["id"], interview["topic"])
    return {
        "assessment_id": aid,
        "topic": interview["topic"],
        "questions": interview["questions"],
        "response_seconds": RESPONSE_SECONDS,
    }


@app.post("/api/assessment/score")
def score(req: ScoreRequest, user=Depends(current_user)):
    result = score_response(req.question_text, req.transcript)
    db.save_response(
        req.assessment_id, req.question_idx, req.question_text,
        req.transcript, req.duration, result,
    )
    return result


@app.post("/api/assessment/{assessment_id}/complete")
def complete(assessment_id: int, user=Depends(current_user)):
    summary = db.complete_assessment(assessment_id)
    if not summary:
        raise HTTPException(400, "No responses recorded for this assessment.")
    return summary


# ---------------- progress routes ----------------

@app.get("/api/history")
def history(user=Depends(current_user)):
    return {
        "history": db.get_history(user["id"]),
        "stats": db.get_progress_stats(user["id"]),
    }


@app.get("/api/assessment/{assessment_id}")
def assessment_detail(assessment_id: int, user=Depends(current_user)):
    detail = db.get_assessment_detail(user["id"], assessment_id)
    if not detail:
        raise HTTPException(404, "Assessment not found.")
    return detail


# ---------------- static frontend ----------------

@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

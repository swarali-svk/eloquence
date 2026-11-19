// ---------------- Eloquence frontend ----------------
const $ = (id) => document.getElementById(id);
const api = async (path, { method = "GET", body } = {}) => {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("eloq_token");
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch("/api" + path, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  // Stale/invalid saved session: force logout back to the login screen.
  if (res.status === 401 && localStorage.getItem("eloq_token") &&
      !path.startsWith("/login") && !path.startsWith("/register")) {
    localStorage.removeItem("eloq_token");
    localStorage.removeItem("eloq_user");
    $("view-app").classList.add("hidden");
    $("view-auth").classList.remove("hidden");
    throw new Error("Your previous session is no longer valid — please log in again.");
  }
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
};

const VIEWS = ["view-dash", "view-setup", "view-test", "view-report"];
const show = (id) => VIEWS.forEach((v) => $(v).classList.toggle("hidden", v !== id));

// ---------------- in-app history / back-button handling ----------------
let currentView = null;
let assessmentActive = false; // true while an interview is in progress

// Forward navigation triggered by the user: push a history entry so the browser
// Back button moves between in-app views instead of leaving the site.
function navigate(view) {
  show(view);
  currentView = view;
  history.pushState({ view }, "");
}

window.addEventListener("popstate", (e) => {
  const target = (e.state && e.state.view) || "view-dash";
  // If backing out of a live interview, confirm before abandoning it.
  if (assessmentActive && currentView === "view-test") {
    const ok = confirm(
      "Do you want to stop the assessment? Your progress in this interview will be lost."
    );
    if (!ok) {
      history.pushState({ view: "view-test" }, ""); // re-assert current state, stay put
      return;
    }
    stopAssessment();
  }
  show(target);
  currentView = target;
  if (target !== "view-test") assessmentActive = false;
  if (target === "view-dash") loadDashboard();
});

// Guard against accidentally closing/reloading the tab mid-interview.
window.addEventListener("beforeunload", (e) => {
  if (assessmentActive) { e.preventDefault(); e.returnValue = ""; }
});

function stopAssessment() {
  assessmentActive = false;
  answerActive = false;
  clearInterval(timerInt);
  clearInterval(prepInt);
  clearTimeout(speechWatchdog);
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  if (recognition) { try { recognition.stop(); } catch {} }
}

// ---------------- auth ----------------
let authMode = "login";

function renderAuthMode() {
  const isLogin = authMode === "login";
  $("auth-title").textContent = isLogin ? "Welcome back" : "Create your account";
  $("auth-sub").textContent = isLogin
    ? "Log in to continue your progress."
    : "Pick a username and password to get started.";
  $("auth-submit").textContent = isLogin ? "Log in" : "Create account";
  $("auth-switch").innerHTML = isLogin
    ? 'New here? <a id="auth-toggle">Create an account</a>'
    : 'Already registered? <a id="auth-toggle">Log in</a>';
  $("auth-toggle").onclick = () => {
    authMode = isLogin ? "register" : "login";
    $("auth-err").textContent = "";
    renderAuthMode();
  };
}

$("auth-submit").onclick = async () => {
  const username = $("auth-user").value.trim();
  const password = $("auth-pass").value;
  $("auth-err").textContent = "";
  try {
    const data = await api("/" + authMode, { method: "POST", body: { username, password } });
    localStorage.setItem("eloq_token", data.token);
    localStorage.setItem("eloq_user", data.username);
    enterApp();
  } catch (e) {
    $("auth-err").textContent = e.message;
  }
};

$("logout").onclick = async () => {
  try { await api("/logout", { method: "POST" }); } catch {}
  localStorage.removeItem("eloq_token");
  localStorage.removeItem("eloq_user");
  $("view-app").classList.add("hidden");
  $("view-auth").classList.remove("hidden");
};

function enterApp() {
  $("view-auth").classList.add("hidden");
  $("view-app").classList.remove("hidden");
  $("who").textContent = localStorage.getItem("eloq_user") || "";
  currentView = "view-dash";
  history.replaceState({ view: "view-dash" }, "");
  show("view-dash");
  loadDashboard();
}

// ---------------- shared ----------------
const DIMS = ["fluency", "intelligibility", "language_use", "organization"];
const DIM_LABELS = {
  fluency: "Fluency",
  intelligibility: "Intelligibility",
  language_use: "Language Use",
  organization: "Organization",
};
const MAX_BAND = 6;
const MAX_CRIT = 5;

function bandClass(label) {
  const lvl = (label || "").slice(0, 2);
  if (lvl === "C2" || lvl === "C1") return "b-high";
  if (lvl === "B2" || lvl === "B1") return "b-mid";
  return "b-low";
}

// ---------------- dashboard ----------------
async function loadDashboard() {
  const { history, stats } = await api("/history");
  if (stats && stats.assessments) {
    $("stats-wrap").classList.remove("hidden");
    const grid = $("stats-grid");
    grid.innerHTML = "";
    const cells = [
      ["Band", stats.overall, "/6"],
      ...DIMS.map((d) => [DIM_LABELS[d], stats[d], "/5"]),
    ];
    cells.forEach(([lbl, val, suf]) => {
      const el = document.createElement("div");
      el.className = "stat";
      el.innerHTML = `<div class="val">${val != null ? val.toFixed(1) : "–"}<span class="den" style="font-size:13px;color:var(--muted)">${suf}</span></div><div class="lbl">${lbl}</div>`;
      grid.appendChild(el);
    });
    drawTrend(history);
  } else {
    $("stats-wrap").classList.add("hidden");
  }

  const list = $("history-list");
  list.innerHTML = "";
  $("history-empty").classList.toggle("hidden", history.length > 0);
  [...history].reverse().forEach((h) => {
    const el = document.createElement("div");
    el.className = "history-item";
    const date = new Date(h.completed_at).toLocaleString();
    el.innerHTML = `
      <div><div><strong>Band ${h.overall_score}/6</strong> · ${h.topic || "Interview"}</div>
      <div class="meta">${date} · tap to view report</div></div>
      <span class="band ${bandClass(h.band_label)}">${h.band_label}</span>`;
    el.onclick = () => openReport(h.id);
    list.appendChild(el);
  });
}

function drawTrend(history) {
  const svg = $("trend-svg");
  svg.innerHTML = "";
  if (history.length < 1) return;
  const W = 600, H = 120, pad = 10;
  const pts = history.map((h, i) => {
    const x = history.length === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (history.length - 1);
    const y = H - pad - (h.overall_score / MAX_BAND) * (H - 2 * pad);
    return [x, y];
  });
  const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  svg.innerHTML = `
    <path d="${path}" fill="none" stroke="#6c8cff" stroke-width="2.5"/>
    ${pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="#8b5cf6"/>`).join("")}`;
}

// ---------------- setup ----------------
let settings = { prep: 5, responseSeconds: 45 };

function fillTimeSelects(minSel, secSel, maxMin) {
  if (!minSel.options.length) {
    for (let m = 0; m <= maxMin; m++) minSel.add(new Option(String(m), m));
    for (let s = 0; s <= 59; s++) secSel.add(new Option(String(s).padStart(2, "0"), s));
  }
}

function initSetup() {
  fillTimeSelects($("prep-min-select"), $("prep-sec-select"), 2);
  fillTimeSelects($("min-select"), $("sec-select"), 5);
  $("prep-min-select").value = "0";
  $("prep-sec-select").value = "5";
  $("min-select").value = "0";
  $("sec-select").value = "45";
  $("setup-err").textContent = "";
}

$("start-btn").onclick = () => { navigate("view-setup"); initSetup(); };
$("again-btn").onclick = () => { navigate("view-setup"); initSetup(); };
$("to-dash").onclick = () => { navigate("view-dash"); loadDashboard(); };

$("begin-assessment").onclick = async () => {
  const prep = parseInt($("prep-min-select").value, 10) * 60 + parseInt($("prep-sec-select").value, 10);
  const total = parseInt($("min-select").value, 10) * 60 + parseInt($("sec-select").value, 10);
  if (total < 10) {
    $("setup-err").textContent = "Please choose a response time of at least 10 seconds.";
    return;
  }
  settings = { prep, responseSeconds: total };

  const btn = $("begin-assessment");
  btn.disabled = true;
  btn.textContent = "Preparing interview…";
  try {
    const data = await api("/assessment/start", { method: "POST" });
    session = {
      assessment_id: data.assessment_id,
      topic: data.topic,
      questions: data.questions,
      idx: 0,
    };
    assessmentActive = true;
    navigate("view-test");
    $("topic-banner").textContent = "Interview topic: " + (data.topic || "General");
    renderQuestion();
  } catch (e) {
    $("setup-err").textContent = "Could not start: " + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Begin interview";
  }
};

// ---------------- assessment flow ----------------
let session = null;

function renderDots() {
  const dots = $("dots");
  dots.innerHTML = "";
  session.questions.forEach((_, i) => {
    const d = document.createElement("div");
    d.className = "d" + (i < session.idx ? " done" : i === session.idx ? " active" : "");
    dots.appendChild(d);
  });
}

function renderQuestion() {
  renderDots();
  const q = session.questions[session.idx];
  $("qnum").textContent = `QUESTION ${session.idx + 1} OF ${session.questions.length}`;
  $("qtext").textContent = q;
  $("rec-stage").classList.add("hidden");
  $("scoring-stage").classList.add("hidden");
  $("prep-stage").classList.add("hidden");
  $("live").textContent = "";

  // Build what the examiner voice reads: announce the topic before Q1, then the
  // question. The prep countdown + timer only begin once reading has finished.
  const texts = [];
  if (session.idx === 0 && session.topic) {
    texts.push("Today's topic is " + session.topic + ".");
  }
  texts.push(q);

  readingResolved = false;
  $("reading-stage").classList.remove("hidden");
  speakSequence(texts, afterReading);
}

let readingResolved = false;

function afterReading() {
  if (readingResolved) return;  // guard against skip + onend both firing
  readingResolved = true;
  $("reading-stage").classList.add("hidden");
  startPrep();
}

let speechWatchdog = null;

function speakSequence(texts, onDone) {
  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    clearTimeout(speechWatchdog);
    onDone();
  };

  if (!("speechSynthesis" in window)) { done(); return; }
  window.speechSynthesis.cancel();

  let i = 0;
  const next = () => {
    if (i >= texts.length) { done(); return; }
    const u = new SpeechSynthesisUtterance(texts[i]);
    u.rate = 0.95;
    u.onend = () => { i++; next(); };
    u.onerror = () => { i++; next(); };
    window.speechSynthesis.speak(u);
  };
  next();

  // Watchdog: some browsers don't reliably fire onend. Fall back after an
  // estimate based on word count (~2.6 words/sec) so the flow never stalls.
  const words = texts.join(" ").split(/\s+/).length;
  const maxMs = Math.max(4000, (words / 2.6) * 1000 + 4000);
  speechWatchdog = setTimeout(done, maxMs);
}

$("skip-reading").onclick = () => {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  clearTimeout(speechWatchdog);
  afterReading();
};

// ---- prep countdown (auto-starts recording) ----
let prepInt = null;
const RING_C = 2 * Math.PI * 52; // circumference of the prep ring

function setPrepRing(left, total) {
  const ring = $("prep-ring");
  ring.style.strokeDasharray = RING_C;
  const frac = total > 0 ? left / total : 0;
  ring.style.strokeDashoffset = RING_C * (1 - frac);
}

function startPrep() {
  clearInterval(prepInt);
  const prepStage = $("prep-stage");
  if (settings.prep <= 0) { prepStage.classList.add("hidden"); beginAnswer(); return; }
  const total = settings.prep;
  let left = total;
  prepStage.classList.remove("hidden");
  $("prep-timer").textContent = fmtTime(left);
  setPrepRing(left, total);
  prepInt = setInterval(() => {
    left--;
    $("prep-timer").textContent = fmtTime(left);
    setPrepRing(left, total);
    if (left <= 0) { clearInterval(prepInt); prepStage.classList.add("hidden"); beginAnswer(); }
  }, 1000);
}

function fmtTime(s) {
  return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : String(s);
}

$("skip-prep").onclick = () => {
  clearInterval(prepInt);
  $("prep-stage").classList.add("hidden");
  beginAnswer();
};

// ---- recording ----
let recognition = null;
let finalTranscript = "";
let timerInt = null;
let secondsLeft = 0;
let answerActive = false;

function setupRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR();
  r.lang = "en-US";
  r.continuous = true;
  r.interimResults = true;
  r.onresult = (ev) => {
    let interim = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalTranscript += t + " ";
      else interim += t;
    }
    $("live").textContent = (finalTranscript + interim).trim();
  };
  r.onend = () => { if (answerActive) { try { r.start(); } catch {} } };
  return r;
}

function beginAnswer() {
  window.speechSynthesis.cancel();
  finalTranscript = "";
  secondsLeft = settings.responseSeconds;
  answerActive = true;

  $("rec-stage").classList.remove("hidden");
  $("mic").classList.add("rec");
  updateTimer();

  recognition = setupRecognition();
  if (!recognition) {
    $("speech-warn").classList.remove("hidden");
    $("speech-warn").textContent =
      "Speech recognition isn't supported in this browser. Use Chrome or Edge for voice input.";
  } else {
    $("speech-warn").classList.add("hidden");
    try { recognition.start(); } catch {}
  }

  timerInt = setInterval(() => {
    secondsLeft--;
    updateTimer();
    if (secondsLeft <= 0) finishAnswer();
  }, 1000);
}

function updateTimer() {
  const m = Math.floor(secondsLeft / 60);
  const s = String(secondsLeft % 60).padStart(2, "0");
  const t = $("timer");
  t.textContent = `${m}:${s}`;
  t.classList.toggle("low", secondsLeft <= 10);
}

$("stop-btn").onclick = () => finishAnswer();

async function finishAnswer() {
  if (!answerActive) return;
  answerActive = false;
  clearInterval(timerInt);
  $("mic").classList.remove("rec");
  if (recognition) { try { recognition.stop(); } catch {} }

  const transcript = ($("live").textContent || finalTranscript).trim();
  const duration = settings.responseSeconds - secondsLeft;

  if (transcript.length < 3) {
    alert("No speech was captured. Please allow microphone access and try speaking again.");
    $("mic").classList.remove("rec");
    $("rec-stage").classList.add("hidden");
    startPrep();
    return;
  }

  const isLast = session.idx === session.questions.length - 1;
  $("rec-stage").classList.add("hidden");
  $("scoring-stage").classList.remove("hidden");
  $("scoring-text").textContent = isLast
    ? "Scoring your interview…"
    : "Saving response… next question coming up.";

  try {
    await api("/assessment/score", {
      method: "POST",
      body: {
        assessment_id: session.assessment_id,
        question_idx: session.idx,
        question_text: session.questions[session.idx],
        transcript,
        duration,
      },
    });
  } catch (e) {
    alert("Scoring failed: " + e.message);
  }

  if (isLast) {
    try { await api(`/assessment/${session.assessment_id}/complete`, { method: "POST" }); } catch {}
    openReport(session.assessment_id, true);
  } else {
    session.idx++;
    renderQuestion();
  }
}

// ---------------- report (after whole test) ----------------
async function openReport(assessmentId, fromTest = false) {
  assessmentActive = false;
  currentView = "view-report";
  // When finishing the test, replace the test history entry so Back doesn't
  // re-enter the completed interview; from history, push a new entry.
  if (fromTest) history.replaceState({ view: "view-report" }, "");
  else history.pushState({ view: "view-report" }, "");
  show("view-report");
  $("report-drawers").innerHTML = '<div class="center"><div class="spinner"></div></div>';
  const { assessment, responses } = await api(`/assessment/${assessmentId}`);

  $("report-topic").textContent = "Topic: " + (assessment.topic || "General interview");
  $("s-score").textContent = assessment.overall_score ?? "–";
  const b = $("s-band");
  b.textContent = assessment.band_label || "";
  b.className = "band " + bandClass(assessment.band_label);

  const wrap = $("report-drawers");
  wrap.innerHTML = "";
  responses.forEach((r, i) => {
    const drawer = document.createElement("div");
    drawer.className = "drawer";
    const dimsHtml = DIMS.map((d) => {
      const score = r[d + "_score"];
      const reason = r[d + "_reason"] || "";
      const pct = (score / MAX_CRIT) * 100;
      return `
        <div class="dim-row">
          <div class="dim-head"><span class="name">${DIM_LABELS[d]}</span><span>${score}/5</span></div>
          <div class="bar"><span style="width:${pct}%"></span></div>
          <div class="dim-reason">${reason}</div>
        </div>`;
    }).join("");

    drawer.innerHTML = `
      <div class="drawer-head">
        <div class="drawer-title">
          <span class="qbadge">Q${i + 1}</span>
          <span class="drawer-q">${r.question_text}</span>
        </div>
        <div class="drawer-right">
          <span class="band ${bandClass(r.band_label)}">${r.band_label}</span>
          <span class="chev">▾</span>
        </div>
      </div>
      <div class="drawer-body">
        <div class="section-title" style="margin-top:4px;">Your response</div>
        <div class="live-transcript" style="margin-top:0;">${r.transcript || "<em>(no transcript)</em>"}</div>
        <div class="section-title">Scores &amp; reasoning</div>
        ${dimsHtml}
        <div class="section-title">Examiner notes</div>
        <div class="examiner">${r.reasoning || ""}</div>
      </div>`;

    drawer.querySelector(".drawer-head").onclick = () => drawer.classList.toggle("open");
    wrap.appendChild(drawer);
  });
}

// ---------------- boot ----------------
renderAuthMode();
if (localStorage.getItem("eloq_token")) {
  enterApp();
}

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.measure import assess_rep
from app.overlay import (
    bar_point,
    choose_side,
    collect,
    load_video_landmarker,
    smooth_bars,
    smooth_side,
)
from app.reps import find_reps, hip_series
from app.skill import load_skill
from app.video import VideoRejected, inspect_video

app = FastAPI()
ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "uploads"

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SquatSide</title>
  <style>
    :root {
      --ink: #171717;
      --muted: #525252;
      --line: #e5e5e5;
      --paper: #ffffff;
      --card: #ffffff;
      --green: #146c2e;
      --red: #8a1c1c;
      --amber: #9a3412;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      color: var(--ink);
      background: var(--paper);
      line-height: 1.45;
    }
    .wrap { max-width: 1080px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
    header { margin-bottom: 1.5rem; }
    .eyebrow { margin: 0 0 0.35rem; letter-spacing: 0.08em; text-transform: uppercase; font-size: 0.75rem; color: var(--muted); }
    h1 { margin: 0 0 0.4rem; font-size: 2.2rem; font-weight: 650; letter-spacing: -0.03em; }
    .lede { margin: 0; max-width: 40rem; color: var(--muted); }
    .setup { display: grid; grid-template-columns: 1.4fr 1fr; gap: 1rem; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 1.1rem 1.15rem; }
    h2 { margin: 0 0 0.6rem; font-size: 1rem; }
    .drop {
      position: relative;
      display: grid;
      gap: 0.2rem;
      min-height: 7.5rem;
      place-content: center;
      border: 1.5px dashed #d4d4d4;
      border-radius: 12px;
      background: #ffffff;
      text-align: center;
      margin-bottom: 0.9rem;
    }
    .drop strong { font-size: 1.05rem; }
    .drop span, .hint { color: var(--muted); font-size: 0.92rem; }
    .drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
    button {
      border: 0;
      border-radius: 999px;
      background: var(--ink);
      color: white;
      font: inherit;
      padding: 0.7rem 1.2rem;
      cursor: pointer;
    }
    button:disabled { opacity: 0.55; cursor: progress; }
    progress { width: 100%; height: 0.55rem; margin-top: 0.8rem; accent-color: var(--ink); }
    progress[hidden] { display: none; }
    #status { min-height: 1.3rem; margin: 0.7rem 0 0; color: var(--muted); }
    #error { margin: 0.4rem 0 0; color: var(--red); }
    .reqs { margin: 0; padding-left: 1.1rem; color: var(--muted); }
    .legend { list-style: none; margin: 0.8rem 0 0; padding: 0; display: grid; gap: 0.4rem; }
    .legend li { display: flex; align-items: center; gap: 0.5rem; color: var(--muted); }
    .swatch { width: 0.75rem; height: 0.75rem; border-radius: 99px; display: inline-block; }
    .swatch.green { background: #7CFF4D; }
    .swatch.orange { background: #ff8c00; }
    .swatch.yellow { background: #ffe14a; }
    #results[hidden] { display: none; }
    #results { margin-top: 1.25rem; display: grid; gap: 1rem; }
    .summary h2 { font-size: 1.45rem; margin-bottom: 0.25rem; }
    .summary p { margin: 0.25rem 0 0; }
    .workspace { display: grid; grid-template-columns: minmax(240px, 380px) 1fr; gap: 1rem; align-items: start; }
    #stage { position: relative; }
    video { width: 100%; display: block; background: #111; border-radius: 16px; }
    #overlay { position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; }
    .rep { border: 1px solid var(--line); border-radius: 16px; background: var(--card); margin-bottom: 0.8rem; overflow: hidden; }
    .rep header { display: flex; justify-content: space-between; gap: 1rem; padding: 0.8rem 1rem; border-bottom: 1px solid var(--line); }
    .rep h3 { margin: 0; font-size: 1rem; }
    .rep header span { color: var(--muted); }
    .row { padding: 0.75rem 1rem; border-top: 1px solid #eeeeee; }
    .row:first-child { border-top: 0; }
    .row-top { display: flex; align-items: center; gap: 0.55rem; }
    .name { font-weight: 650; }
    .badge { font-size: 0.75rem; border-radius: 999px; padding: 0.15rem 0.5rem; background: #f5f5f5; color: var(--muted); }
    .meets .badge { background: #e5f6ea; color: var(--green); }
    .does_not_meet .badge { background: #fde8e8; color: var(--red); }
    .explain, .pages { margin: 0.35rem 0 0; }
    .pages { color: var(--muted); font-size: 0.85rem; }
    @media (max-width: 800px) {
      .setup, .workspace { grid-template-columns: 1fr; }
      h1 { font-size: 1.8rem; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <p class="eyebrow">Side-view squat check</p>
      <h1>SquatSide</h1>
      <p class="lede">Upload a side-view barbell squat. The page marks the body, draws an estimated bar path, and checks each rep against the squat chapter.</p>
    </header>
    <section class="setup">
      <form id="form" class="card">
        <label class="drop" for="file">
          <strong>Choose a video</strong>
          <span id="filename">__FORMATS__ · up to __SECONDS__ seconds · __MB__ MB</span>
          <input id="file" name="video" type="file" accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm" required>
        </label>
        <button id="submit" type="submit">Analyze</button>
        <p id="status"></p>
        <progress id="bar" value="0" max="100" hidden></progress>
        <p id="error"></p>
      </form>
      <aside class="card">
        <h2>How to record</h2>
        <ul class="reqs">
          <li>__CAMERA__</li>
          <li>Formats: __FORMATS__.</li>
        </ul>
        <ul class="legend">
          <li><span class="swatch green"></span> Green dots are body joints</li>
          <li><span class="swatch orange"></span> Orange is a bar estimate, not the plate</li>
          <li><span class="swatch yellow"></span> Yellow marks the bottom of a rep</li>
        </ul>
      </aside>
    </section>
    <section id="results" hidden>
      <div id="summary" class="card summary"></div>
      <div class="workspace">
        <div id="stage">
          <video id="player" controls playsinline></video>
          <canvas id="overlay"></canvas>
        </div>
        <div id="findings"></div>
      </div>
    </section>
  </div>
  <script>
    const NAMES = {
      depth: "Depth",
      back_angle: "Back angle",
      segment_angles: "Hip and knee angles",
      bar_over_midfoot: "Bar over the midfoot",
      knee_vs_toes: "Knees and toes",
      hip_drive: "Hip drive",
      gaze: "Eye gaze",
      heels_down: "Feet flat",
      bar_placement: "Low-bar placement",
      knees_out: "Knees shoved out",
      stance_width: "Stance width",
      toe_angle: "Toe angle",
      grip: "Grip and wrists",
      rack_setup: "Rack and walk-out"
    };
    const form = document.getElementById("form");
    const status = document.getElementById("status");
    const bar = document.getElementById("bar");
    const error = document.getElementById("error");
    const player = document.getElementById("player");
    const canvas = document.getElementById("overlay");
    const findings = document.getElementById("findings");
    const summary = document.getElementById("summary");
    const results = document.getElementById("results");
    const submit = document.getElementById("submit");
    const file = document.getElementById("file");
    const filename = document.getElementById("filename");
    file.onchange = () => {
      filename.textContent = file.files.length ? file.files[0].name : filename.textContent;
    };
    let marks = [];
    let clipFps = 30;
    let bottoms = {};

    function paint() {
      const ctx = canvas.getContext("2d");
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      if (!marks.length || !w || !h) return;
      let index = Math.round(player.currentTime * clipFps);
      if (index < 0) index = 0;
      if (index >= marks.length) index = marks.length - 1;
      ctx.lineWidth = Math.max(2, w / 400);
      ctx.strokeStyle = "rgb(255,140,0)";
      ctx.beginPath();
      let started = false;
      for (let i = 0; i <= index; i++) {
        const point = marks[i].bar;
        if (!point) continue;
        const x = point[0] * w;
        const y = point[1] * h;
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.fillStyle = "lime";
      for (const joint of marks[index].joints) {
        ctx.beginPath();
        ctx.arc(joint[0] * w, joint[1] * h, Math.max(4, w / 180), 0, Math.PI * 2);
        ctx.fill();
      }
      const barPoint = marks[index].bar;
      if (barPoint) {
        ctx.fillStyle = "rgb(255,140,0)";
        ctx.beginPath();
        ctx.arc(barPoint[0] * w, barPoint[1] * h, Math.max(5, w / 150), 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowColor = "rgba(0,0,0,0.75)";
        ctx.shadowBlur = 6;
        ctx.fillStyle = "rgb(255,140,0)";
        ctx.font = Math.max(18, Math.round(w / 40)) + "px sans-serif";
        ctx.fillText("bar estimate", 16, 36);
        ctx.shadowBlur = 0;
      }
      for (const frame in bottoms) {
        if (Math.abs(index - Number(frame)) <= clipFps * 0.4) {
          ctx.shadowColor = "rgba(0,0,0,0.75)";
          ctx.shadowBlur = 6;
          ctx.fillStyle = "yellow";
          ctx.font = Math.max(18, Math.round(w / 40)) + "px sans-serif";
          ctx.fillText("rep " + bottoms[frame] + " bottom", 16, 72);
          ctx.shadowBlur = 0;
          break;
        }
      }
    }

    player.onloadedmetadata = () => {
      canvas.width = player.videoWidth;
      canvas.height = player.videoHeight;
      paint();
    };
    player.ontimeupdate = paint;
    player.onseeked = paint;
    player.onplay = () => {
      const loop = () => {
        paint();
        if (!player.paused && !player.ended) requestAnimationFrame(loop);
      };
      requestAnimationFrame(loop);
    };

    function esc(text) {
      return String(text == null ? "" : text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function resultLabel(result) {
      if (result === "meets") return "Meets";
      if (result === "does_not_meet") return "Does not meet";
      return "Cannot assess";
    }

    function renderSummary(items) {
      const ids = [];
      for (const item of items) {
        if (item.rep != null && !ids.includes(item.rep)) ids.push(item.rep);
      }
      const title = ids.length === 0 ? "No reps found" : ids.length === 1 ? "1 rep found" : ids.length + " reps found";
      const depth = items.filter((item) => item.criterion === "depth" && item.rep != null);
      const meets = depth.filter((item) => item.result === "meets").length;
      const miss = depth.filter((item) => item.result === "does_not_meet").length;
      const unknown = depth.filter((item) => item.result === "cannot_assess").length;
      const parts = [];
      if (meets) parts.push(meets === 1 ? "1 rep meets depth" : meets + " reps meet depth");
      if (miss) parts.push(miss === 1 ? "1 rep needs to go deeper" : miss + " reps need to go deeper");
      if (unknown) parts.push(unknown === 1 ? "1 rep is too close to call" : unknown + " reps are too close to call");
      const sentence = parts.length ? parts.join(". ") + "." : "Depth could not be checked.";
      summary.innerHTML = "<p class='eyebrow'>Result</p><h2>" + title + "</h2><p>" + sentence +
        "</p><p class='hint'>Only depth can pass or fail. A number on another rule is evidence, not a grade.</p>";
    }

    function renderFindings(items) {
      findings.innerHTML = "";
      const groups = [];
      for (const item of items) {
        let group = groups.find((entry) => entry.rep === item.rep);
        if (!group) {
          group = { rep: item.rep, time: item.time_seconds, items: [] };
          groups.push(group);
        }
        group.items.push(item);
      }
      for (const group of groups) {
        const article = document.createElement("article");
        article.className = "rep";
        const when = group.time == null ? "" : group.time + "s";
        const title = group.rep == null ? "No rep" : "Rep " + group.rep;
        let rows = "";
        for (const item of group.items) {
          let extra = "";
          if (item.criterion === "depth" && item.measurement && item.measurement.gap != null) {
            const gap = Number(item.measurement.gap);
            const place = gap > 0 ? "below" : "above";
            extra = "<p class='pages'>The hip joint is " + Math.abs(gap) + " of the picture height " + place + " the knee joint.</p>";
          }
          rows += "<div class='row " + esc(item.result) + "'>" +
            "<div class='row-top'><span class='badge'>" + resultLabel(item.result) + "</span>" +
            "<span class='name'>" + esc(NAMES[item.criterion] || item.criterion) + "</span></div>" +
            "<p class='explain'>" + esc(item.explanation) + "</p>" +
            extra +
            "<p class='pages'>Pages " + esc(item.source_pages.join(", ")) + "</p></div>";
        }
        article.innerHTML = "<header><h3>" + title + "</h3><span>" + when + "</span></header>" + rows;
        findings.appendChild(article);
      }
    }

    form.onsubmit = (event) => {
      event.preventDefault();
      error.textContent = "";
      findings.innerHTML = "";
      summary.innerHTML = "";
      results.hidden = true;
      submit.disabled = true;
      bar.hidden = false;
      bar.value = 0;
      status.textContent = "Uploading...";
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/analyze");
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable) return;
        bar.value = ev.loaded / ev.total * 100;
      };
      xhr.upload.onload = () => {
        status.textContent = "Analyzing the squat. This takes a few seconds.";
      };
      xhr.onload = () => {
        bar.hidden = true;
        submit.disabled = false;
        let body;
        try {
          body = JSON.parse(xhr.responseText);
        } catch (err) {
          status.textContent = "";
          error.textContent = "The analysis did not return a result.";
          return;
        }
        if (xhr.status >= 400) {
          status.textContent = "";
          error.textContent = body.detail || "The video was rejected.";
          return;
        }
        status.textContent = "Played from the " + body.side + " side. " + body.frame_count + " frames.";
        marks = body.marks;
        clipFps = body.fps;
        bottoms = body.bottoms;
        results.hidden = false;
        player.src = body.video_url;
        renderSummary(body.findings);
        renderFindings(body.findings);
        results.scrollIntoView({ behavior: "smooth", block: "start" });
      };
      xhr.onerror = () => {
        bar.hidden = true;
        submit.disabled = false;
        status.textContent = "";
        error.textContent = "The upload failed.";
      };
      xhr.send(new FormData(form));
    };
  </script>
</body>
</html>
"""


def page() -> str:
    recording = load_skill()["recording"]
    return (
        PAGE.replace("__FORMATS__", ", ".join(recording["formats"]))
        .replace("__SECONDS__", str(recording["max_duration_seconds"]))
        .replace("__MB__", str(recording["max_upload_mb"]))
        .replace("__CAMERA__", " ".join(recording["camera"].split()))
    )


MEDIA_TYPES = {".webm": "video/webm", ".mp4": "video/mp4", ".mov": "video/quicktime"}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return page()


@app.get("/videos/{name}")
def video(name: str) -> FileResponse:
    path = (UPLOADS / name).resolve()
    if path.parent != UPLOADS.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Video not found.")
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"))


@app.post("/analyze")
def analyze(video: UploadFile = File(...)) -> dict:
    UPLOADS.mkdir(exist_ok=True)
    suffix = Path(video.filename or "").suffix.lower()
    saved = UPLOADS / f"{uuid.uuid4().hex}{suffix}"
    saved.write_bytes(video.file.read())
    try:
        report = inspect_video(saved)
    except VideoRejected as exc:
        saved.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    skill = load_skill()
    landmarker = load_video_landmarker()
    try:
        fps, frames = collect(saved, landmarker)
    finally:
        landmarker.close()
    side = choose_side(frames)
    reps = find_reps(hip_series(frames, side), fps)
    bottoms = {
        rep["bottom_frame"]: rep["rep"]
        for rep in reps
        if rep.get("bottom_frame") is not None
    }
    smoothed = smooth_side(frames, side)
    bars = smooth_bars([bar_point(points, side) for points in frames])
    marks = []
    for row, bar in zip(smoothed, bars):
        marks.append({
            "joints": [[round(x, 4), round(y, 4)] for x, y in row.values()],
            "bar": None if bar is None else [round(bar[0], 4), round(bar[1], 4)],
        })
    findings = []
    for rep in reps:
        findings.extend(assess_rep(frames, rep, side, skill))
    return {
        "side": side,
        "frame_count": report["frame_count"],
        "fps": fps,
        "video_url": f"/videos/{saved.name}",
        "marks": marks,
        "bottoms": bottoms,
        "findings": findings,
    }
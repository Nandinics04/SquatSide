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
  <title>SquatSide</title>
  <style>
    body { font-family: Georgia, serif; margin: 2rem auto; max-width: 48rem; line-height: 1.45; }
    progress { width: 100%; height: 1rem; }
    #stage[hidden] { display: none; }
    #stage { position: relative; display: inline-block; max-width: 100%; }
    video { width: 100%; background: #111; display: block; }
    #overlay { position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; }
    .finding { border-top: 1px solid #ccc; padding: 0.6rem 0; }
    .cannot_assess { color: #555; }
    .meets { color: #146c2e; }
    .does_not_meet { color: #8a1c1c; }
    #error { color: #8a1c1c; }
  </style>
</head>
<body>
  <h1>SquatSide</h1>
  <p>Upload a side-view video of barbell squats. The page draws the joints, an estimated bar path, and a finding for every rule in the skill file.</p>
  <ul>
    <li>Formats: __FORMATS__</li>
    <li>Maximum length: __SECONDS__ seconds</li>
    <li>Maximum size: __MB__ MB</li>
    <li>__CAMERA__</li>
  </ul>
  <form id="form">
    <input id="file" name="video" type="file" required>
    <button type="submit">Analyze</button>
  </form>
  <p id="status"></p>
  <progress id="bar" value="0" max="100" hidden></progress>
  <p id="error"></p>
  <div id="stage" hidden>
    <video id="player" controls playsinline></video>
    <canvas id="overlay"></canvas>
  </div>
  <div id="findings"></div>
  <script>
    const form = document.getElementById("form");
    const status = document.getElementById("status");
    const bar = document.getElementById("bar");
    const error = document.getElementById("error");
    const stage = document.getElementById("stage");
    const player = document.getElementById("player");
    const canvas = document.getElementById("overlay");
    const findings = document.getElementById("findings");
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
        ctx.fillStyle = "rgb(255,140,0)";
        ctx.font = Math.max(18, Math.round(w / 40)) + "px sans-serif";
        ctx.fillText("bar estimate", 16, 36);
      }
      for (const frame in bottoms) {
        if (Math.abs(index - Number(frame)) <= clipFps * 0.4) {
          ctx.fillStyle = "yellow";
          ctx.font = Math.max(18, Math.round(w / 40)) + "px sans-serif";
          ctx.fillText("rep " + bottoms[frame] + " bottom", 16, 72);
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

    form.onsubmit = (event) => {
      event.preventDefault();
      error.textContent = "";
      findings.innerHTML = "";
      stage.hidden = true;
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
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 400) {
          status.textContent = "";
          error.textContent = body.detail;
          return;
        }
        status.textContent = "Side used: " + body.side + ". Frames: " + body.frame_count + ".";
        marks = body.marks;
        clipFps = body.fps;
        bottoms = body.bottoms;
        stage.hidden = false;
        player.src = body.video_url;
        for (const item of body.findings) {
          const block = document.createElement("div");
          block.className = "finding " + item.result;
          const when = item.time_seconds == null ? "" : " at " + item.time_seconds + "s";
          block.innerHTML = "<strong>Rep " + item.rep + " · " + item.criterion + "</strong> " +
            item.result.replaceAll("_", " ") + when +
            "<br>Pages " + item.source_pages.join(", ") +
            "<br>" + item.explanation;
          findings.appendChild(block);
        }
      };
      xhr.onerror = () => {
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
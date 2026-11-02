import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.measure import assess_rep
from app.overlay import (
    bar_point,
    choose_side,
    collect,
    draw,
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
OUTPUTS = ROOT / "outputs"

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SquatSide</title>
  <style>
    body { font-family: Georgia, serif; margin: 2rem auto; max-width: 48rem; line-height: 1.45; }
    progress { width: 100%; height: 1rem; }
    video { width: 100%; background: #111; }
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
  <video id="player" controls hidden></video>
  <div id="findings"></div>
  <script>
    const form = document.getElementById("form");
    const status = document.getElementById("status");
    const bar = document.getElementById("bar");
    const error = document.getElementById("error");
    const player = document.getElementById("player");
    const findings = document.getElementById("findings");

    form.onsubmit = (event) => {
      event.preventDefault();
      error.textContent = "";
      findings.innerHTML = "";
      player.hidden = true;
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
        player.hidden = false;
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


def playable(path: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return path
    dest = path.with_name(path.stem + "_play.mp4")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(path), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dest)],
        check=True,
        capture_output=True,
    )
    return dest


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return page()


@app.get("/videos/{name}")
def video(name: str) -> FileResponse:
    path = (OUTPUTS / name).resolve()
    if path.parent != OUTPUTS.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Video not found.")
    return FileResponse(path, media_type="video/mp4")


@app.post("/analyze")
def analyze(video: UploadFile = File(...)) -> dict:
    UPLOADS.mkdir(exist_ok=True)
    OUTPUTS.mkdir(exist_ok=True)
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
    drawn = OUTPUTS / f"{saved.stem}.mp4"
    draw(
        saved,
        fps,
        smooth_side(frames, side),
        smooth_bars([bar_point(points, side) for points in frames]),
        drawn,
        bottoms,
    )
    play = playable(drawn)
    findings = []
    for rep in reps:
        findings.extend(assess_rep(frames, rep, side, skill))
    return {
        "side": side,
        "frame_count": report["frame_count"],
        "video_url": f"/videos/{play.name}",
        "findings": findings,
    }
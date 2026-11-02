# SquatSide

SquatSide checks a side-view barbell squat against the standards in the supplied squat chapter. The chapter is the reference. The file the program loads is [skill/squat_skill.yaml](skill/squat_skill.yaml). Each rule cites reference pages 1–35. A reference page is the combined PDF page minus 3.

The local page at `http://127.0.0.1:8000` accepts a video, draws the joints and an estimated bar path, marks each rep bottom, and lists a finding for every skill rule. A finding is `meets`, `does not meet`, or `cannot assess`, with the source pages and a short explanation.

Depth is the only rule the program measures. The other 13 rules stay `cannot assess`. A front-view clip is kept as the unsuitable recording.

No API key is required. There is no `.env` file.

## What the skill decides

The skill has 14 rules.

| Side view | Rules |
|---|---|
| Assessable | Depth. The hip crease must drop below the top of the kneecap. Pages 2, 15, and 17. |
| Partial | Back angle, hip and knee angles, bar over midfoot, knees versus toes, hip drive, gaze, heels down, bar placement. |
| Not assessable | Knees shoved out, stance width, toe angle, grip and wrists, rack height and walk-out. A side camera cannot see them. |

`segment_angles` is report-only. The chapter describes open and closed hip and knee angles and gives no degree cutoff, so those angles must not be passed or failed. The page prints them as `cannot assess`.

Numbers the chapter does not state are labeled `owner: us` under `assumptions` in the skill file:

- Pose points are the hip joint and the knee joint. The chapter uses the hip crease and the top of the kneecap.
- Angles are 2D image measurements. They describe the body only on a true side view.
- A landmark with visibility below 0.5 is not usable.
- A repetition requires the hip to drop and then rise by 0.08 of the image height. The chapter does not give that number.
- At least half of the frames must show the hip, or the clip is `cannot assess`.
- The bar point is placed a little above the visible shoulder and behind the nose. MediaPipe does not detect a barbell.
- `depth_margin` is 0.03 of the image height. A smaller gap between the hip joint and the knee joint is `cannot assess`, because those joints are not the crease and the kneecap.

The video gate reads `recording` from the skill: `mp4`, `mov`, and `webm`, 60 seconds, 100 MB. Those limits are not copied into Python. Changing them in the YAML changes what `app/video.py` accepts and what the upload page prints.

## Architecture

```text
video file
  -> app/video.py        format, size, and duration from the skill
  -> app/overlay.py      MediaPipe Pose Landmarker on every frame
  -> visible side        higher average visibility of shoulder, hip, knee, ankle
  -> app/reps.py         bottoms from the hip height
  -> app/measure.py      depth at each bottom; every other rule is cannot assess
  -> app/web.py          upload, overlay playback, and the findings list
```

Pose runs locally with MediaPipe 1.2 and the Full pose model. OpenCV reads the video, draws the overlay, and writes MPEG-4. The page asks `ffmpeg` to remux that file to H.264 (`libx264`, `yuv420p`) so a browser can play it. If `ffmpeg` is not on the server's `PATH`, the page serves the MPEG-4 file and the player stays black at 0:00.

The visible side is smoothed with a five-frame average. Points under 0.5 visibility are left out of the average. The bar path is a separate orange trail, labeled `bar estimate` on the frame. Each measured bottom is labeled `rep N bottom` in yellow for about 0.8 seconds.

Rep counting uses the hip's vertical position. In the image, a larger `y` is lower. A rep starts when the hip falls 0.08 of the image height from its high point. The bottom is the lowest hip before it rises by the same amount. A pause at the bottom still counts as one rep.

Depth compares the visible hip joint with the visible knee joint at that bottom. Image `y` increases downward, so a positive gap means the hip is lower than the knee. A gap larger than `depth_margin` is `meets`. A gap below the negative margin is `does not meet`, and the explanation is the skill's `miss_feedback`. A smaller gap, a hidden joint, or a rep with no bottom is `cannot assess`.

Every frame is passed to MediaPipe, including a frame with no person. The timestamp still increases on that frame. Skipping it makes the next call reuse the same timestamp, and MediaPipe rejects the video.

## Setup

Python 3.13 and [uv](https://docs.astral.sh/uv/) are required. `ffmpeg` is required for browser playback and for a single merged download of a YouTube sample. It is installed with winget on this machine, but a terminal opened before the install does not see it until the path is refreshed.

```powershell
uv sync
New-Item -ItemType Directory -Force models
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task" -OutFile "models/pose_landmarker_full.task"
```

In Cursor, select the interpreter at `.venv\Scripts\python.exe`. Otherwise `cv2`, `numpy`, and `pytest` show as unresolved even though `uv run` can import them.

`models/`, `uploads/`, and `outputs/` are gitignored. Do not commit the pose model, uploaded videos, or generated videos. The sample clips under `samples/` are local too.

## Run

Print the 14 rules:

```powershell
uv run python -m app.skill
```

Run the tests. They do not need a squat video. The video tests write tiny clips. The rep tests use a fake hip signal, including a slow squat with a pause. The depth tests check a clear pass, a clear miss, a hidden knee, a gap inside `depth_margin`, and a front-view rule that must stay `cannot assess`.

```powershell
uv run pytest tests/test_video.py tests/test_reps.py tests/test_measure.py -q
```

Draw landmarks on one still image:

```powershell
uv run python -m app.pose samples/side_squat.jpg
```

The marked image is `outputs/pose_frame.jpg`.

Download the common sample. Without `ffmpeg`, yt-dlp saves the picture and the sound separately. The picture is the file the pipeline uses.

```powershell
uv run yt-dlp -o "samples/squat.mp4" "https://youtube.com/shorts/TRvg083BrXY"
uv run python -m app.overlay "samples/squat.mp4.f313.webm"
uv run python -m app.reps "samples/squat.mp4.f313.webm"
uv run python -m app.measure "samples/squat.mp4.f313.webm"
```

`samples/squat.mp4.f251.webm` is audio only. Do not run pose on it.

To make a file Cursor can play:

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
ffmpeg -y -i outputs\pose_video.mp4 -c:v libx264 -pix_fmt yuv420p outputs\pose_video_play.mp4
```

Start the page from a terminal that can see `ffmpeg`:

```powershell
uv run python -m uvicorn app.web:app --reload
```

Open `http://127.0.0.1:8000`. The form shows the formats, length, size, and camera note from the skill. Upload progress is shown, then the overlay and one finding per rule per rep. A file the skill rejects returns the rejection text on the page.

On this PC, `uv run uvicorn ...` can fail because Application Control blocks `uvicorn.exe`. `python -m uvicorn` is the command that starts.

## Changing a grade without changing Python

`depth_margin` in [skill/squat_skill.yaml](skill/squat_skill.yaml) is `0.03`. On the common sample the depth gaps are about `-0.009` and `-0.017`, so both depth findings are `cannot assess`.

Set `depth_margin` to `0.001`, restart is unnecessary while `--reload` is running, and upload the same clip again. Both depth findings become `does not meet`, the text comes from the skill's `miss_feedback`, and the cited pages stay 2, 15, and 17. Put the value back to `0.03` and they return to `cannot assess`.

## Evidence from the common sample

Source: https://youtube.com/shorts/TRvg083BrXY

The processed file is `samples/squat.mp4.f313.webm`: 236 frames, 30 fps, 1080×1920, about 8 seconds. The program chose the left side. The hip was visible on every frame. Its image height moved from about `0.655` standing to `0.821` at the lowest point.

Two repetitions were measured:

| Rep | Bottom | Hip y | Knee y | Gap | Depth |
|---|---|---|---|---|---|
| 1 | 1.97 s, frame 59 | 0.821 | 0.830 | -0.009 | cannot assess |
| 2 | 6.27 s, frame 188 | 0.812 | 0.828 | -0.017 | cannot assess |

Both gaps are inside `0.03`, so the page says the hip and knee are too close to call. The other 13 rules on each rep are `cannot assess` because they are not measured, or because a side camera cannot see them.

Checked by eye on `outputs/pose_video.mp4`:

- The green dots for the foot, ankle, knee, and the hip at the shorts stay near those body parts through both reps.
- One green dot stays on the weight plate. The plate hides the head and the shoulder, so that point is not a joint that can be graded.
- The orange bar trail does not stay on the barbell. During the descent it climbs off the plate toward the gymnastic rings, then falls back down the shirt. The metal bar itself barely travels horizontally. The trail is an estimate, and on this clip it is not good enough to grade bar path or bar placement.
- The camera is behind the plate, not a true side view. Depth, back angle, and hip drive from this clip stay uncertain even where the hip and knee dots look plausible.

`samples/side_squat.jpg` is a cleaner side-view still, without a barbell. On that image the hip, knee, ankle, and shoulder dots sit on the body, and the far knee is below the 0.5 visibility cutoff. It shows the pose model can place joints when the plate is not in the way. It is not the common sample.

## Evidence from a front-view clip

Source: https://www.youtube.com/watch?v=Pe8-lHhtsb8

The file is `samples/front_view.webm`: 1080×1906, about 60 fps, about 30 seconds. The container reports 1822 frames. The pose pass kept 1820. The program chose the right side and measured five reps, with bottoms at 8.93 s, 13.41 s, 17.65 s, 21.89 s, and 26.49 s.

Depth was `cannot assess` on every rep. The hip-to-knee gaps were about 0.015 to 0.026, all inside `depth_margin`. The other rules were `cannot assess` as well. The program does not detect that the camera is in front. The small image gap, and the rules this side view cannot measure, are what keep the grade from becoming a pass or a fail.

The first upload of this file failed before any finding was produced. A frame with no pose left the MediaPipe timestamp unchanged, and the next frame raised `Input timestamp must be monotonically increasing`. `collect` now stores that empty frame and advances the timestamp.

## Build note

**Models and tools.** MediaPipe Pose Landmarker Full for the body. OpenCV for video reading, drawing, and MPEG-4 writing. PyYAML for the skill. pytest for the video gate, the rep counter, and the depth verdicts. yt-dlp to fetch the samples. ffmpeg for the H.264 file the browser plays. FastAPI and uvicorn for the upload page.

**Cost.** No paid API and no GPU. The pose model is a one-time download. The 8-second common sample takes roughly 10 seconds on CPU. The 30-second front-view clip takes about a minute. Build cost and per-video cost are about zero.

**Trade-offs.** A structured skill file is the grading source, not retrieval over the PDF. The chapter is 35 pages and every relevant rule applies to every rep. A 2D side-view pose was chosen instead of a trained bar detector or a 3D pose model. The bar position is computed from the shoulder so the result can be labeled as an estimate. Reps are counted from hip height so a pause at the bottom is one rep. Only depth is graded. The partial rules stay `cannot assess` rather than receiving a cutoff the chapter does not give.

**Known limits.** The common sample's bar path is not reliable. The shoulder landmark is stuck on the plate. A front view can still produce rep bottoms, because hip height changes in the image, but those bottoms are not a side-view depth judgment. `cannot assess` is the correct grade when the needed point is hidden or the gap is inside `depth_margin`. `0.08`, `0.5` visibility, the half-frame visibility fraction, and `0.03` are our cutoffs.

## How AI was used

AI extracted the chapter into the skill checklist, proposed the pipeline, and drafted the overlay, rep counter, depth check, page, and tests. I checked the page citations, ran the tests, and watched the overlay frames rather than trusting the first drawing.

Mistakes that were caught before they became a grade:

- `inspect_video` used `raise` on the success dictionary, so a valid clip was reported as an exception. The other two video tests still passed. The fix was `return`.
- The first rep finder only looked half a second around each frame. The hip drop on the sample was real (`0.166` of the image height), and the program printed no reps. Widening the rule to a full descent and rise found the two bottoms at 1.97 s and 6.27 s.
- yt-dlp did not create `samples/squat.mp4`. ffmpeg was installed but not on the terminal path, so the picture and audio were saved as two `.webm` files. The pose run has to use `samples/squat.mp4.f313.webm`.
- The first depth pass called both common-sample reps `does not meet` on gaps of about `0.009` and `0.017`. Those joints are not the crease and the kneecap, and the camera is not a true side view. `depth_margin` of `0.03` turns that close call into `cannot assess`.
- `collect` advanced its timestamp only when a pose was found. The front-view clip has a frame with no person, so MediaPipe stopped the upload. Empty frames are now kept.

## Still open

- The eight partial rules are explained and cited. None of them is measured yet.
- The bar trail is drawn and labeled as an estimate. It is not graded.
- The page does not decide for itself that a clip is front-view. That limit is written down here and left as `cannot assess` in the findings.

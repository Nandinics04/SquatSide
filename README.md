# SquatSide

SquatSide checks a side-view barbell squat against the standards in the supplied squat chapter. The chapter is the reference. The file the program loads is [skill/squat_skill.yaml](skill/squat_skill.yaml). Each rule cites reference pages 1–35. A reference page is the combined PDF page minus 3.

A local website was the intended product. The upload page is not built yet. What runs today is a command-line pipeline: reject a bad video, draw pose landmarks, draw an estimated bar path, and find the bottom of each repetition. Depth and the other skill rules are not graded yet.

No API key is required. There is no `.env` file.

## What the skill decides

The skill has 14 rules.

| Side view | Rules |
|---|---|
| Assessable | Depth. The hip crease must drop below the top of the kneecap. Pages 2, 15, and 17. |
| Partial | Back angle, hip and knee angles, bar over midfoot, knees versus toes, hip drive, gaze, heels down, bar placement. |
| Not assessable | Knees shoved out, stance width, toe angle, grip and wrists, rack height and walk-out. A side camera cannot see them. |

`segment_angles` is report-only. The chapter describes open and closed hip and knee angles and gives no degree cutoff, so those angles must not be passed or failed.

Numbers the chapter does not state are labeled `owner: us` under `assumptions` in the skill file:

- Pose points are the hip joint and the knee joint. The chapter uses the hip crease and the top of the kneecap.
- Angles are 2D image measurements. They describe the body only on a true side view.
- A landmark with visibility below 0.5 is not usable.
- A repetition requires the hip to drop and then rise by 0.08 of the image height. The chapter does not give that number.
- At least half of the frames must show the hip, or the clip is `cannot assess`.
- The bar point is placed a little above the visible shoulder and behind the nose. MediaPipe does not detect a barbell.

The video gate reads `recording` from the skill: `mp4`, `mov`, and `webm`, 60 seconds, 100 MB. Those limits are not copied into Python. Changing them in the YAML changes what `app/video.py` accepts.

## Architecture

```text
video file
  -> app/video.py        format, size, and duration from the skill
  -> app/overlay.py      MediaPipe Pose Landmarker on every frame
  -> visible side        higher average visibility of shoulder, hip, knee, ankle
  -> app/reps.py         bottoms from the hip height
  -> app/measure.py      not written yet; depth is the next check
```

Pose runs locally with MediaPipe 1.2 and the Full pose model. OpenCV reads the video, draws the overlay, and writes `outputs/pose_video.mp4`. The overlay codec is MPEG-4. Cursor's player often rejects that file. The Windows video player opened it. `ffmpeg` can remux it to H.264 when a browser has to play it.

The visible side is smoothed with a five-frame average. Points under 0.5 visibility are left out of the average. The bar path is a separate orange trail, labeled `bar estimate` on the frame.

Rep counting uses the hip's vertical position. In the image, a larger `y` is lower. A rep starts when the hip falls 0.08 of the image height from its high point. The bottom is the lowest hip before it rises by the same amount. A pause at the bottom still counts as one rep.

## Setup

Python 3.13 and [uv](https://docs.astral.sh/uv/) are required. `ffmpeg` is required only when you want an H.264 copy or a single merged download of the sample. It is installed with winget on this machine, but a terminal opened before the install does not see it until the path is refreshed.

```powershell
uv sync
New-Item -ItemType Directory -Force models
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task" -OutFile "models/pose_landmarker_full.task"
```

In Cursor, select the interpreter at `.venv\Scripts\python.exe`. Otherwise `cv2`, `numpy`, and `pytest` show as unresolved even though `uv run` can import them.

`models/` and `outputs/` are gitignored. Do not commit the pose model or generated videos.

## Run

Print the 14 rules:

```powershell
uv run python -m app.skill
```

Run the tests. They do not need a squat video. The video tests write tiny clips. The rep tests use a fake hip signal, including a slow squat with a pause. 

```powershell
uv run pytest tests/test_video.py tests/test_reps.py -q
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
```

`samples/squat.mp4.f251.webm` is audio only. Do not run pose on it.

To make a file Cursor can play:

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
ffmpeg -y -i outputs\pose_video.mp4 -c:v libx264 -pix_fmt yuv420p outputs\pose_video_play.mp4
```

## Evidence from the common sample

Source: https://youtube.com/shorts/TRvg083BrXY

The processed file is `samples/squat.mp4.f313.webm`: 236 frames, 30 fps, 1080×1920, about 8 seconds. The program chose the left side. The hip was visible on every frame. Its image height moved from about `0.655` standing to `0.821` at the lowest point.

Two repetitions were measured:

| Rep | Bottom | Hip y |
|---|---|---|
| 1 | 1.97 s, frame 59 | 0.821 |
| 2 | 6.27 s, frame 188 | 0.812 |

Checked by eye on `outputs/pose_video.mp4`:

- The green dots for the foot, ankle, knee, and the hip at the shorts stay near those body parts through both reps.
- One green dot stays on the weight plate. The plate hides the head and the shoulder, so that point is not a joint that can be graded.
- The orange bar trail does not stay on the barbell. During the descent it climbs off the plate toward the gymnastic rings, then falls back down the shirt. The metal bar itself barely travels horizontally. The trail is an estimate, and on this clip it is not good enough to grade bar path or bar placement.
- The camera is behind the plate, not a true side view. Depth, back angle, and hip drive from this clip stay uncertain even where the hip and knee dots look plausible.

`samples/side_squat.jpg` is a cleaner side-view still, without a barbell. On that image the hip, knee, ankle, and shoulder dots sit on the body, and the far knee is below the 0.5 visibility cutoff. It shows the pose model can place joints when the plate is not in the way. It is not the common sample.

## Build note

**Models and tools.** MediaPipe Pose Landmarker Full for the body. OpenCV for video reading, drawing, and MPEG-4 writing. PyYAML for the skill. pytest for the video gate and the rep logic. yt-dlp to fetch the sample. ffmpeg only for an H.264 copy. FastAPI and uvicorn are installed for the upload page and are not used yet.


**Cost.** No paid API and no GPU. The pose model is a one-time download. Processing this 8-second clip takes roughly 10 seconds on CPU. Build cost and per-video cost are about zero.

**Trade-offs.** A structured skill file is the grading source, not retrieval over the PDF. The chapter is 35 pages and every relevant rule applies to every rep. A 2D side-view pose was chosen instead of a trained bar detector or a 3D pose model. The bar position is computed from the shoulder so the result can be labeled as an estimate. Reps are counted from hip height so a pause at the bottom is one rep.

**Known limits.** There is no upload page, no per-criterion verdict yet, and no annotated bottom marker on the video. The common sample's bar path is not reliable. The shoulder landmark is stuck on the plate. A result of `cannot assess` is the correct grade when the needed point is hidden. `0.08`, `0.5` visibility, and the half-frame visibility fraction are our cutoffs.

## How AI was used

AI extracted the chapter into the skill checklist, proposed the pipeline, and drafted the overlay, rep counter, and tests. I checked the page citations, ran the tests, and watched the overlay frames rather than trusting the first drawing.

Mistakes that were caught before they became a grade:

- `inspect_video` used `raise` on the success dictionary, so a valid clip was reported as an exception. The other two video tests still passed. The fix was `return`.
- The first rep finder only looked half a second around each frame. The hip drop on the sample was real (`0.166` of the image height), and the program printed no reps. Widening the rule to a full descent and rise found the two bottoms at 1.97 s and 6.27 s.
- yt-dlp did not create `samples/squat.mp4`. ffmpeg was installed but not on the terminal path, so the picture and audio were saved as two `.webm` files. The pose run has to use `samples/squat.mp4.f313.webm`.

## Not built yet

- Depth at each bottom, then the other partial rules, all read from the skill.
- A bottom marker on the overlay video.
- The upload page: progress, processing status, errors, playback, and the findings.
- A second, unsuitable clip kept beside the common sample as a permanent `cannot assess` case. The common sample already shows a failed bar track. A front-view or heavily occluded clip is still worth adding.

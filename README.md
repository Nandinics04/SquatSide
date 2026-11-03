# SquatSide

SquatSide is a local web page that accepts a side-view video of barbell squats, draws the body and an estimated bar path on the video, finds each repetition, and grades the movement from the supplied squat chapter.

The chapter is the reference. The file the program loads is [skill/squat_skill.yaml](skill/squat_skill.yaml). Each rule cites reference pages 1–35. A reference page is the combined PDF page minus 3. The skill file is the grading source. The page does not invent advice from a general squat model.

Open `http://127.0.0.1:8000` after the setup below. No API key is required. There is no `.env` file. Hosting was not used. A local launch is the submission.

## What the assignment asked for

| Requirement | What shipped |
|---|---|
| Turn the chapter into a skill the app actually uses, with page citations, and mark what a side view can and cannot see. | `skill/squat_skill.yaml`, loaded by `app/skill.py` on every analysis. 14 rules. `side_view` is `assessable`, `partial`, or `not_assessable`. |
| Let a person upload a side-view video, see progress and errors, and state the formats, length, size, and camera. | The page reads those limits from the skill. Accepted files are mp4, mov, and webm, up to 60 seconds and 100 MB. A rejected file shows the rejection text. The upload bar shows progress, then a status line while pose runs. |
| Support more than one repetition. | `app/reps.py` finds every descent and rise of the hip and marks each bottom. |
| Track hips, knees, ankles, and the points needed for the torso. Track the bar and show its path. Mark bottoms. Return a playable annotated video or a synchronized overlay. | MediaPipe pose draws the visible joints in green. The orange mark is a bar estimate placed from the shoulder. The browser plays the original upload. A canvas draws the joints, the orange trail, and `rep N bottom` in time with the video. |
| Separate observed points from estimates. Prefer `cannot assess` when the picture is not enough. | Green dots are pose landmarks. The orange mark is labeled `bar estimate`. A hidden joint, a missing bottom, or a gap inside our depth band is `cannot assess`. |
| For each rep and each rule: the result `meets`, `does not meet`, or `cannot assess`, the source pages, a timestamp, the measurement when one exists, an explanation, and feedback grounded in the chapter. | `app/measure.py` returns that record. Depth is the only rule with a measurement. The other 13 copy the skill's uncertainty sentence and stay `cannot assess`. |
| Do not present a cutoff the chapter does not state as if the chapter required it. | `depth_margin` of 0.03 is under `assumptions` with `owner: us`. The chapter's line remains the hip crease below the top of the kneecap. |
| Run upload, analysis, annotation, and feedback on a newly uploaded video. | `POST /analyze` does that path. Nothing is precomputed for the browser. |
| Evidence on the common sample and one unsuitable recording, a build note, an AI-use note, and a way to change a rule without rewriting Python. | The evidence and notes are below. Changing `depth_margin` in the YAML changes the depth verdict. |

## What you see after Analyze

The player stays hidden until a video is accepted. Then the original file plays. Chrome plays the uploaded webm or mp4 directly. The page does not remux the file and does not call ffmpeg.

On the picture:

- Green dots are the visible-side joints from MediaPipe: shoulder, hip, knee, ankle, heel, foot, nose, and ear, after a five-frame smooth. A point below 0.5 visibility is left out.
- The orange dot and the orange line are the bar estimate. The program places that point a little above the visible shoulder and a little behind the nose. It is not the center of the plate. It is not used in any grade.
- Yellow text, `rep N bottom`, appears for about 0.4 seconds around the frame where the hip is lowest.

Under the player, every rule is listed once per rep. A `meets` line is green, a `does not meet` line is red, and a `cannot assess` line is gray. Each line shows the rule id, the time of the bottom, the source pages, and one explanation sentence.

## The 14 rules

Only depth is measured. The other results are `cannot assess` on every video, including a squat that looks correct.

| Rule | Pages | Side view | What the page prints |
|---|---|---|---|
| Depth | 2, 15, 17 | Assessable | `meets`, `does not meet`, or `cannot assess`. This is the only graded rule. |
| Back angle | 9, 22, 32, 35 | Partial | `cannot assess`. "No numeric pass band is stated in the chapter." |
| Hip angle and knee angle | 9, 13 | Partial | `cannot assess`. "Report the degrees. The graded result is cannot assess." The degrees are not calculated. |
| Bar over the midfoot | 8, 9, 11, 32 | Partial | `cannot assess`. "Cannot assess when the foot or the bar track is missing. The bar track is an estimate." |
| Knees relative to the toes | 17, 22 | Partial | `cannot assess`. "A borderline position is cannot assess. Grade it only when the knee and the toes are visible." |
| Hip drive | 23, 32, 35 | Partial | `cannot assess`. "Judged from hip and shoulder motion on the ascent." |
| Eye gaze | 24, 26, 35 | Partial | `cannot assess`. "The side view can separate chin-down from chin-up. It cannot measure the distance to the gaze point." |
| Feet flat | 22 | Partial | `cannot assess`. "Cannot assess when the heel is hidden." |
| Low-bar placement | 13, 29, 35 | Partial | `cannot assess`. "A side view usually cannot see the scapular spine. Use cannot assess unless the bar is clearly on the neck or clearly below the shoulder." |
| Knees shoved out | 14, 22, 35 | Not assessable | `cannot assess`. "This is a front-view check. A side camera cannot see it." |
| Stance width | 19, 32, 35 | Not assessable | `cannot assess`. "Shoulder-width heels need a front view." |
| Toe angle | 19, 22, 35 | Not assessable | `cannot assess`. "The chapter states about 30 degrees. A side view cannot measure it." |
| Grip and wrists | 27, 28 | Not assessable | `cannot assess`. "Hands and wrists are not reliable in a side view of the set." |
| Rack height and walk-out | 26, 30, 31, 35 | Not assessable | `cannot assess`. "The rack and the walk-out are not part of the squat video being graded." |

`meets` on depth uses the skill's uncertainty sentence as the explanation, because the measurement is a joint stand-in. `does not meet` uses `miss_feedback`: "Go deeper. Drop the hip crease below the top of the kneecap." The skill's `standard` text is not printed. For every rule except depth, `miss_feedback` is stored and is not shown, because the result never becomes `does not meet`.

### Depth

The chapter's line is visual. The hip crease must drop below the top of the kneecap. Thighs level with the floor are still high. The chapter gives no pixel cutoff.

The pose model marks the hip joint and the knee joint. In the image, down is a larger `y`, so the gap is hip `y` minus knee `y`. A positive gap means the hip joint is lower than the knee joint.

`depth_margin` is 0.03 of the picture height. We own that number.

| Gap at the bottom | Result |
|---|---|
| Hip lower than the knee by more than 0.03 | `meets` |
| Hip higher than the knee by more than 0.03 | `does not meet` |
| The two joints are within 0.03 | `cannot assess`. "The hip and knee are too close to call." |
| Hip or knee hidden, or the rep has no bottom | `cannot assess` |

### Why the other rules stay cannot assess

A side view can support a measurement for some of the partial rules. The chapter still does not give a pass band, so the page does not turn our own number into `meets`.

- Back angle is about 45 degrees, and both a too-upright back and a collapsed back are faults. "About 45" is not a range that passes. Showing the degrees would still leave the middle as `cannot assess`.
- Hip and knee angles are described, and the skill says to report them and not pass or fail them.
- The bar should stay over the middle of the foot. The "12 inches" in the chapter is an example of bad leverage, not a cutoff. The orange mark is a shoulder guess, so the page never compares it with the foot.
- The knees should finish only a little in front of the toes. "A little" has no inch limit.
- Hip drive means the hips go straight up and the chest does not rise first. The chapter gives no angle for that motion.
- Gaze should be at the floor about 4 or 5 feet ahead, with the chin slightly down. The video has no scale for that floor distance.
- The heels should stay on the floor. The model marks a heel point. It does not see the sole touching the floor.
- The bar should sit just under the spine of the shoulder blade. A side camera usually cannot see that ridge.
- Knees out, stance width, toe angle, grip, and the rack need a front view or happen outside the set. No assumption makes a side video show them.

## Assumptions we own

These are not chapter requirements.

In the skill file:

- Pose points stand in for the hip crease and the top of the kneecap.
- Angles, when measured, are 2D image angles and describe the body on a true side view.
- Visibility below 0.5 means the point is missing and the result is `cannot assess`.
- `depth_margin` is 0.03 of the image height.
- The back-angle note records that any future extreme cutoff must stay labeled as ours. No numeric band is stored, and the angle is not measured.

In Python, because the chapter gives no rep counter:

- `MIN_DROP` in `app/reps.py` is 0.08 of the image height. The hip must fall that far, then rise that far, to count one rep. A pause at the bottom is still one rep. A clip that ends while the hip is down still counts.
- `MIN_VISIBLE_FRACTION` is 0.5. If the hip is missing on more than half the frames, the clip is `cannot assess` and no bottoms are marked.
- The bar estimate in `app/overlay.py` is 0.18 of the torso length above the shoulder and 0.12 of the torso length behind the nose. MediaPipe does not detect a barbell.

The upload limits in the skill are `recording`, not body-measurement cutoffs: mp4, mov, webm, 60 seconds, 100 MB, camera about hip height, true side view, one person, bar and feet in frame. `app/video.py` reads those values. They are not copied into the gate as separate numbers.

## Architecture

```text
video file
  -> app/video.py        format, size, and duration from the skill
  -> app/overlay.py      MediaPipe Pose Landmarker on every frame
  -> visible side        higher average visibility of shoulder, hip, knee, ankle
  -> app/reps.py         bottoms from the hip height
  -> app/measure.py      depth at each bottom; every other rule is cannot assess
  -> app/web.py          upload, original-video playback, canvas overlay, findings
```

Pose runs locally with MediaPipe 1.2 and `models/pose_landmarker_full.task`. OpenCV reads the frames. The browser plays the file the user uploaded. The canvas reads `marks` and `bottoms` from the JSON response and draws on top of `video.currentTime`. The command-line overlay in `app/overlay.py` can still write `outputs/pose_video.mp4` with the `mp4v` codec. That file is for a local check. The page does not serve it. `mp4v` plays as a black frame in Chrome, which is why the page keeps the original upload.

The visible side is the side with the higher mean visibility of shoulder, hip, knee, and ankle. A tie uses the right side. Points are smoothed with a five-frame average. Points under 0.5 visibility are left out of the average.

Every frame is passed to MediaPipe, including a frame with no person. The timestamp still increases. Skipping an empty frame makes the next call reuse the same timestamp, and MediaPipe rejects the video.

Rep counting uses the hip's vertical position. A larger `y` is lower. A rep starts when the hip falls 0.08 of the image height from its high point. The bottom is the lowest hip before it rises by the same amount.

## Setup

Python 3.13 and [uv](https://docs.astral.sh/uv/) are required.

```powershell
uv sync
New-Item -ItemType Directory -Force models
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task" -OutFile "models/pose_landmarker_full.task"
```

In Cursor, select the interpreter at `.venv\Scripts\python.exe`. Otherwise `cv2`, `numpy`, and `pytest` show as unresolved even though `uv run` can import them.

`models/`, `uploads/`, and `outputs/` are gitignored. Do not commit the pose model, uploaded videos, generated videos, or the book PDF. The sample clips under `samples/` are local too.

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

The marked image is `outputs/pose_frame.jpg`. `samples/side_squat.jpg` is a bodyweight side view. It is a pose check only. Graded examples are barbell squats.

The common sample is already on disk as `samples/squat.mp4.f313.webm`. `samples/squat.mp4.f251.webm` is audio only. Do not run pose on it.

```powershell
uv run python -m app.overlay "samples/squat.mp4.f313.webm"
uv run python -m app.reps "samples/squat.mp4.f313.webm"
uv run python -m app.measure "samples/squat.mp4.f313.webm"
```

Start the page:

```powershell
uv run python -m uvicorn app.web:app --reload
```

Open `http://127.0.0.1:8000`. Choose a file and click Analyze once. Leave the request running. Stopping the server during Analyze cancels the job and produces no findings. On this PC, `uv run uvicorn ...` can fail because Application Control blocks `uvicorn.exe`. `python -m uvicorn` is the command that starts.

## Changing a grade without changing Python

`depth_margin` in [skill/squat_skill.yaml](skill/squat_skill.yaml) is `0.03`. On the common sample the depth gaps are about `-0.009` and `-0.017`, so both depth findings are `cannot assess`.

Set `depth_margin` to `0.001` and upload the same clip again. Both depth findings become `does not meet`. The text comes from the skill's `miss_feedback`. The cited pages stay 2, 15, and 17. Put the value back to `0.03` and they return to `cannot assess`.

That edit is the walkthrough a reviewer can do during the session. The other rules have no cutoff to edit. Adding a pass band for "about 45 degrees", "a little in front of the toes", or "4 or 5 feet" would be a rule the chapter does not state.

## Evidence from the common sample

Source: https://youtube.com/shorts/TRvg083BrXY

The processed file is `samples/squat.mp4.f313.webm`: 236 frames, 30 fps, 1080×1920, about 8 seconds. The program chose the left side. The hip was visible on every frame. Its image height moved from about `0.655` standing to `0.821` at the lowest point.

Two repetitions were measured:

| Rep | Bottom | Hip y | Knee y | Gap | Depth |
|---|---|---|---|---|---|
| 1 | 1.97 s, frame 59 | 0.821 | 0.830 | -0.009 | cannot assess |
| 2 | 6.27 s, frame 188 | 0.812 | 0.828 | -0.017 | cannot assess |

Both gaps are inside `0.03`, so the page says the hip and knee are too close to call. The other 13 rules on each rep are `cannot assess`.

Checked by eye:

- The green dots for the foot, ankle, knee, and the hip at the shorts stay near those body parts through both reps.
- One green dot stays on the weight plate. The plate hides the head and the shoulder, so that point is not a joint that can be graded.
- The orange bar trail does not stay on the barbell. During the descent it leaves the plate. The metal bar itself barely travels horizontally. The trail is an estimate, and on this clip it is not good enough to grade bar path or bar placement.
- The camera is behind the plate, not a true side view. Depth from this clip stays uncertain even where the hip and knee dots look plausible.

`samples/side_squat.jpg` is a cleaner side-view still, without a barbell. On that image the hip, knee, ankle, and shoulder dots sit on the body, and the far knee is below the 0.5 visibility cutoff. It shows the pose model can place joints when the plate is not in the way. It is not a graded sample.

## Evidence from a front-view clip

Source: https://www.youtube.com/watch?v=Pe8-lHhtsb8

The file is `samples/front_view.webm`: 1080×1906, about 60 fps, about 30 seconds. The container reports 1822 frames. The pose pass kept 1820. The program chose the right side and measured five reps, with bottoms at 8.93 s, 13.41 s, 17.65 s, 21.89 s, and 26.49 s.

Depth was `cannot assess` on every rep. The hip-to-knee gaps were about 0.015 to 0.026, all inside `depth_margin`. The other rules were `cannot assess` as well. The program does not detect that the camera is in front. A front camera can see knees-out, stance width, toe angle, both heels, and the grip. This page does not measure those, and it cannot grade depth from the front. The small image gap is what keeps depth from becoming a pass or a fail.

The first upload of this file failed before any finding was produced. A frame with no pose left the MediaPipe timestamp unchanged, and the next frame raised `Input timestamp must be monotonically increasing`. `collect` now stores that empty frame and advances the timestamp.

## Build note

**Models and tools.** MediaPipe Pose Landmarker Full for the body. OpenCV for reading frames. PyYAML for the skill. pytest for the video gate, the rep counter, and the depth verdicts. yt-dlp to fetch the samples. FastAPI and uvicorn for the page. The browser plays the original file and draws the overlay. ffmpeg is not part of the page.

**Time.** The recorded working time for the build is about 6 hours 50 minutes, past the 4–6 hour box. Later playback fixes are not added as a new total.

**Cost.** No paid API and no GPU. The pose model is a one-time download. The 8-second common sample takes roughly 10 seconds on CPU. The 30-second front-view clip takes about a minute. Build cost and per-video cost are about zero.

**Trade-offs.** A structured skill file is the grading source, not a search over the PDF. The chapter is 35 pages and every rule is listed for every rep, so a reviewer can see what was considered. A 2D side-view pose was chosen instead of a trained bar detector or a 3D pose model. The bar position is computed from the shoulder so it can be labeled as an estimate. Reps are counted from hip height so a pause at the bottom is one rep. Only depth is graded. The partial rules stay `cannot assess` rather than receiving a cutoff the chapter does not give.

**Known limits.** The common sample's bar path is not reliable. The shoulder landmark sticks on the plate. A front view can still produce rep bottoms, because hip height changes in the image, but those bottoms are not a side-view depth judgment. `cannot assess` is the result when the needed point is hidden or the gap is inside `depth_margin`. `0.08`, `0.5` visibility, the half-frame visibility fraction, the shoulder offsets `0.12` and `0.18`, and `0.03` are our cutoffs.

## How AI was used

AI extracted the chapter into the skill checklist, proposed the pipeline, and drafted the overlay, rep counter, depth check, page, tests, and this note. I checked the page citations against the skill file, ran the tests, and watched the overlay on the sample rather than trusting the first drawing.

Mistakes that were caught before they became a grade:

- `inspect_video` used `raise` on the success dictionary, so a valid clip was reported as an exception. The fix was `return`.
- The first rep finder only looked half a second around each frame. The hip drop on the sample was real (`0.166` of the image height), and the program printed no reps. A full descent and rise found the two bottoms at 1.97 s and 6.27 s.
- The first depth pass called both common-sample reps `does not meet` on gaps of about `0.009` and `0.017`. Those joints are not the crease and the kneecap, and the camera is not a true side view. `depth_margin` of `0.03` turns that close call into `cannot assess`.
- `collect` advanced its timestamp only when a pose was found. The front-view clip has a frame with no person, so MediaPipe stopped the upload. Empty frames are now kept.
- An OpenCV `mp4v` file played black in Chrome. The page now plays the original upload and draws the marks on a canvas.

## Still open

- The eight partial rules are explained and cited. None of them is measured. A later measurement can show a number. It still cannot mark `meets` unless the chapter has a yes-or-no line, which only depth has.
- The bar trail is drawn and labeled as an estimate. It is not graded. Plate detection was tried and removed, because the orange dot did not sit on the bar.
- The page does not decide for itself that a clip is a front view or a back view. That limit is written here, and the findings stay `cannot assess`.

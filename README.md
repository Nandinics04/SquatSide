# SquatSide

SquatSide checks a side-view barbell squat against the standards in the supplied squat chapter. The chapter is the reference. The file that the program grades from is [skill/squat_skill.yaml](skill/squat_skill.yaml). Each rule cites reference pages 1–35. A reference page is the combined PDF page minus 3.

The app is in progress. What runs today is the skill loader, the video gate, and pose landmarks on one image. Rep detection, bar path, grading, and the upload page are not built yet.

## Assumptions

- The product is a local website. This repository does not have that page yet.
- Input is one side-view video. Accepted formats, the 60-second limit, and the 100 MB limit live in the skill file under `recording`. The video check reads those values. They are not copied into Python.
- Pose points are 2D estimates. The model marks the hip joint and the knee joint. The chapter’s depth test uses the hip crease and the top of the kneecap, so depth is an estimate.
- A landmark with visibility below 0.5 is not usable. That cutoff is ours, not a number from the chapter.
- The pose model is MediaPipe Pose Landmarker Full. One side of the body is usually hidden in a side view. The visible side is the one with the higher visibility.
- Rules that need a front view, including stance width, toe angle, and knees-out, stay `not_assessable`.
- No LLM API key is required. There is no RAG step. The skill file is the grading source.

## Setup

Python 3.13 and [uv](https://docs.astral.sh/uv/) are required.

```powershell
uv sync
```

Download the pose model once. It is gitignored.

```powershell
New-Item -ItemType Directory -Force models
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task" -OutFile "models/pose_landmarker_full.task"
```

In Cursor, select the interpreter at `.venv\Scripts\python.exe`. Otherwise `cv2`, `numpy`, and `pytest` show as unresolved even though `uv run` can import them.

## Run

Print the 14 rules and whether a side view can grade each one:

```powershell
uv run python -m app.skill
```

Check the video gate. This writes tiny test clips. It does not need a squat video.

```powershell
uv run pytest tests/test_video.py -q
```

Draw pose landmarks on one side-view image. A sample frame is in `samples/side_squat.jpg`. The marked image is written to `outputs/pose_frame.jpg`.

```powershell
uv run python -m app.pose samples/side_squat.jpg
```

Open the output and confirm the hip, knee, ankle, and shoulder dots sit on the body before using the pose result on a full clip.

## Common sample

Submissions are compared on this clip: https://youtube.com/shorts/TRvg083BrXY

That video is not downloaded by the commands above.

## Layout

- `skill/squat_skill.yaml` holds the rules, page citations, and side-view limits.
- `app/skill.py` loads that file and rejects duplicate rule ids.
- `app/video.py` accepts `mp4`, `mov`, and `webm`, and refuses a clip past the skill’s duration or size limit.
- `app/pose.py` runs the pose model on one image.
- `models/` and `outputs/` are local. Do not commit them.

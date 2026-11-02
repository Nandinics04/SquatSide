from pathlib import Path
import sys
import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options

from app.pose import MODEL_PATH, NAMED
from app.video import inspect_video

VISIBLE=0.5
WINDOW=5
SIDE_JOINTS=("shoulder", "hip", "knee", "ankle")

def load_video_landmarker()-> vision.PoseLandmarker:
    options=vision.PoseLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )
    return vision.PoseLandmarker.create_from_options(options)

def visibility_of(point)->float:
    if point is None or point.visibility is None:
        return 0.0
    return point.visibility

def collect(path:Path, landmarker)->tuple[float, list[dict]]:
    capture=cv2.VideoCapture(str(path))
    fps=float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frames=[]
    index=0
    while True:
        ok, frame=capture.read()
        if not ok:
            break
        rgb=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image=mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms=int(index*1000/fps)
        result=landmarker.detect_for_video(mp_image, timestamp_ms)
        points={}
        if result.pose_landmarks:
            landmarks=result.pose_landmarks[0]
            for name, landmark_index in NAMED.items():
                point=landmarks[landmark_index]
                points[name]=(point.x, point.y, visibility_of(point))
        frames.append(points)
        index+=1
    
    capture.release()
    return fps, frames

def choose_side(frames:list[dict])->str:
    totals = {"left": 0.0, "right": 0.0}
    count=0
    for points in frames:
        if not points:
            continue
        count+=1
        for side in totals:
            totals[side]+=sum(points[f'{side}_{joint}'][2] for joint in SIDE_JOINTS)
    if count==0:
        raise SystemExit("No pose detected")
    return "left" if totals["left"] > totals["right"] else "right"



def smooth_side(frames: list[dict], side:str)->list[dict]:
    names=[name for name in NAMED if name.startswith(f"{side}_")]
    smoothed=[]
    for index, _ in enumerate(frames):
        start = max(0, index - WINDOW + 1)
        row={}
        for name in names:
            chunk=[]
            for points in frames[start:index + 1]:
                if name in points and points[name][2] >= VISIBLE:
                    chunk.append(points[name])
            if chunk:
                row[name]=(
                    sum(point[0] for point in chunk) / len(chunk),
                    sum(point[1] for point in chunk) / len(chunk),
                )
        smoothed.append(row)
    return smoothed

def bar_point(points: dict, side: str):
    shoulder=points.get(f"{side}_shoulder")
    hip=points.get(f"{side}_hip")
    if shoulder is None or hip is None:
        return None
    if shoulder[2]<VISIBLE or hip[2] < VISIBLE:
        return None
    sx, sy, _=shoulder
    hx, hy, _=hip
    torso = ((sx - hx) ** 2 + (sy - hy) ** 2) ** 0.5
    if torso == 0:
        return None
    back_x, back_y = 0.0, 0.0
    nose = points.get("nose")
    if nose is not None and nose[2] >= VISIBLE:
        length = ((sx - nose[0]) ** 2 + (sy - nose[1]) ** 2) ** 0.5
        if length > 0:
            back_x = (sx - nose[0]) / length
            back_y = (sy - nose[1]) / length
    return (
        sx+back_x * torso * 0.12,
        sy-torso * 0.18 + back_y * torso * 0.12,
    )

def smooth_bars(bars: list) -> list:
    smoothed=[]
    for index, _ in enumerate(bars):
        chunk=[
            point
            for point in bars[max(0, index - WINDOW + 1):index + 1]
            if point is not None
        ]
        if not chunk:
            smoothed.append(None)
            continue
        smoothed.append((
            sum(point[0] for point in chunk)/len(chunk),
            sum(point[1] for point in chunk)/len(chunk),
        ))
    return smoothed

def draw(
    path: Path,
    fps: float,
    smoothed: list[dict],
    bars: list,
    output: Path,
    bottoms: dict | None = None,
) -> None:
    capture = cv2.VideoCapture(str(path))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output.parent.mkdir(exist_ok=True)
    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    trail = []
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        for x_norm, y_norm in smoothed[index].values():
            center = (int(x_norm * width), int(y_norm * height))
            cv2.circle(frame, center, 5, (0, 255, 0), -1)
        if index < len(bars) and bars[index] is not None:
            bar_center = (int(bars[index][0] * width), int(bars[index][1] * height))
            trail.append(bar_center)
            cv2.circle(frame, bar_center, 6, (0, 140, 255), -1)
        if len(trail) >= 2:
            cv2.polylines(
                frame,
                [np.array(trail, dtype=np.int32)],
                False,
                (0, 140, 255),
                2,
            )
        cv2.putText(
            frame,
            "bar estimate",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 140, 255),
            2,
        )
        if bottoms:
            for frame_index, rep_number in bottoms.items():
                if abs(index - frame_index) <= int(fps * 0.4):
                    cv2.putText(
                        frame,
                        f"rep {rep_number} bottom",
                        (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 255),
                        2,
                    )
                    break
        writer.write(frame)
        index += 1
    capture.release()
    writer.release()



def main(path: Path)->None:
    report=inspect_video(path)
    landmarker=load_video_landmarker()
    try:
        fps, frames=collect(path, landmarker)
    finally:
        landmarker.close()
    side=choose_side(frames)
    bars=smooth_bars([bar_point(points, side) for points in frames])
    output=Path("outputs/pose_video.mp4")
    draw(path, fps, smooth_side(frames, side), bars,output)
    print(f"side={side} frames={report['frame_count']} wrote {output}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run python -m app.overlay samples/side_squat.mp4")
    main(Path(sys.argv[1]))
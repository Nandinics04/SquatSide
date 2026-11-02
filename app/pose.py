import sys
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "pose_landmarker_full.task"
OUTPUT_PATH=Path(__file__).resolve().parents[1]/"outputs"/"pose_frame.jpg"

NAMED={
    "nose":0,
    "left_ear":7,
    "right_ear":8,
    "left_shoulder":11,
    "right_shoulder":12,
    "left_hip":23,
    "right_hip":24,
    "left_knee":25,
    "right_knee":26,
    "left_ankle":27,
    "right_ankle":28,
    "left_heel":29,
    "right_heel":30,
    "left_foot_index":31,
    "right_foot_index":32,
}


def load_landmarker()->vision.PoseLandmarker:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(MODEL_PATH)
    options=vision.PoseLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.IMAGE,
        num_poses=1,
    )
    return vision.PoseLandmarker.create_from_options(options)

def main(image_path: Path)->None:
    image=cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f"Could not read {image_path}")
    height, width = image.shape[:2]
    rgb=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image=mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    landmarker=load_landmarker()
    try:
        result=landmarker.detect(mp_image)
    finally:
        landmarker.close()
    if not result.pose_landmarks:
        print("No pose landmarks detected")
        return

    landmarks=result.pose_landmarks[0]
    for name, index in NAMED.items():
        point=landmarks[index]
        visibility=0.0 if point.visibility is None else point.visibility
        x=int(point.x*width)
        y=int(point.y*height)
        print(f"{name}: x={x}, y={y}, visibility={visibility:.2f}")
        cv2.circle(image, (x,y), 5, (0,255,0), -1)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(OUTPUT_PATH), image)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run python -m app.pose samples/side_squat.jpg")
    main(Path(sys.argv[1]))

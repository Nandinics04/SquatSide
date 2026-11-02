from pathlib import Path
import sys

from app.overlay import VISIBLE, choose_side, collect, load_video_landmarker

MIN_DROP = 0.08
MIN_VISIBLE_FRACTION = 0.5

def find_reps(series: list[float | None], fps: float) -> list[dict]:
    visible = [value for value in series if value is not None]
    if not series or len(visible) / len(series) < MIN_VISIBLE_FRACTION:
        return [{
            "rep": None,
            "status": "cannot_assess",
            "reason": "Hip is not visible enough to find repetitions.",
        }]

    bottoms = []
    high = visible[0]
    trough_frame = 0
    trough_y = visible[0]
    descending = False
    for frame, y in enumerate(series):
        if y is None:
            continue
        if not descending:
            if y < high:
                high = y
            if y - high >= MIN_DROP:
                descending = True
                trough_frame = frame
                trough_y = y
            continue
        if y >= trough_y:
            trough_frame = frame
            trough_y = y
        elif trough_y - y >= MIN_DROP:
            bottoms.append(trough_frame)
            descending = False
            high = y
    if descending:
        bottoms.append(trough_frame)

    return [
        {
            "rep": number,
            "status": "measured",
            "bottom_frame": frame,
            "time_seconds": round(frame / fps, 2),
            "hip_y": round(series[frame], 3),
        }
        for number, frame in enumerate(bottoms, start=1)
    ]
def hip_series(frames: list[dict], side: str) -> list[float | None]:
    series=[]
    for points in frames:
        hip = points.get(f"{side}_hip") if points else None
        if hip is None or hip[2] < VISIBLE:
            series.append(None)
        else:
            series.append(hip[1])
    return series


def main(path: Path)->None:
    landmarker=load_video_landmarker()
    try:
        fps,frames=collect(path, landmarker)
    finally:
        landmarker.close()
    side=choose_side(frames)
    for rep in find_reps(hip_series(frames, side), fps):
        print(rep)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit('Usage: uv run python -m app.reps "samples/squat.mp4.f313.webm"')
    main(Path(sys.argv[1]))
from pathlib import Path
import cv2
from app.skill import load_skill

class VideoRejected(Exception):
    pass

def inspect_video(path: Path, skill: dict| None= None)-> dict:
    skill=skill or load_skill()
    recording=skill["recording"]
    path=Path(path)
    suffix=path.suffix.lower().lstrip(".")
    allowed={fmt.lower() for fmt in recording["formats"]}
    if suffix not in allowed:
        names=", ".join(sorted(allowed))
        raise VideoRejected(f"Use one of the following formats: {names}")
    
    size_mb=path.stat().st_size/ (1024*1024)
    limit_mb=recording["max_upload_mb"]
    if size_mb > limit_mb:
        raise VideoRejected(f"Video is larger than {limit_mb} MB")
    capture=cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise VideoRejected("Could not open the video")
    try:
        fps=float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frame_count=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()

    if fps<=0 or frame_count<=0:
        raise VideoRejected("The video has no frames")
    
    duration=frame_count/fps
    limit_seconds=recording["max_duration_seconds"]
    if duration > limit_seconds:
        raise VideoRejected(f"Video is longer than {limit_seconds} seconds")
    
    return {
        "path": str(path),
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": duration,
    }
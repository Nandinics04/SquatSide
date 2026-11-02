from pathlib import Path
import cv2
import numpy as np
import pytest 
from app.video import inspect_video, VideoRejected

def write_video(path: Path, seconds: float, fps: int= 10)->None:
    size=(64, 64)
    writer=cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not write an mp4")
    frame=np.zeros((size[1], size[0], 3), dtype=np.uint8)
    for _ in range(int(seconds*fps)):
        writer.write(frame)
    writer.release()

def test_short_video_reports_duration(tmp_path: Path)->None:
    path=tmp_path/"short.mp4"
    write_video(path,seconds=1)
    report=inspect_video(path)
    assert report["frame_count"] == 10
    assert report["duration_seconds"] == pytest.approx(1, abs=0.1)

def test_text_file_is_rejected(tmp_path: Path)->None:
    path=tmp_path/"notes.txt"
    path.write_text("not a video", encoding="utf-8")
    with pytest.raises(VideoRejected):
        inspect_video(path)

def test_long_video_is_rejected(tmp_path: Path)->None:
    path=tmp_path/"long.mp4"
    write_video(path,seconds=61)
    with pytest.raises(VideoRejected):
        inspect_video(path)
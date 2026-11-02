from pathlib import Path
import sys

from app.overlay import VISIBLE, choose_side, collect, load_video_landmarker
from app.reps import find_reps, hip_series
from app.skill import load_skill


def depth_finding(frames: list[dict], rep: dict, side: str, rule: dict, margin: float) -> dict:
    finding = {
        "rep": rep["rep"],
        "criterion": rule["id"],
        "section": rule["section"],
        "source_pages": rule["source_pages"],
        "result": "cannot_assess",
        "bottom_frame": rep.get("bottom_frame"),
        "time_seconds": rep.get("time_seconds"),
        "measurement": None,
        "explanation": rule["uncertainty"],
    }
    if rep.get("status") != "measured":
        finding["explanation"] = rep.get("reason", "This rep has no measured bottom.")
        return finding

    points = frames[rep["bottom_frame"]]
    hip = points.get(f"{side}_hip")
    knee = points.get(f"{side}_knee")
    if hip is None or knee is None or hip[2] < VISIBLE or knee[2] < VISIBLE:
        finding["explanation"] = "The hip or knee is not visible at the bottom."
        return finding

    gap = hip[1] - knee[1]
    finding["measurement"] = {
        "hip_y": round(hip[1], 3),
        "knee_y": round(knee[1], 3),
        "gap": round(gap, 3),
    }
    if abs(gap) < margin:
        finding["result"] = "cannot_assess"
        finding["explanation"] = "The hip and knee are too close to call. " + rule["uncertainty"]
    elif gap > 0:
        finding["result"] = "meets"
        finding["explanation"] = rule["uncertainty"]
    else:
        finding["result"] = "does_not_meet"
        finding["explanation"] = rule["miss_feedback"].strip()
    return finding


def assess_rep(frames: list[dict], rep: dict, side: str, skill: dict) -> list[dict]:
    margin = next(item["value"] for item in skill["assumptions"] if item["id"] == "depth_margin")
    findings = []
    for rule in skill["criteria"]:
        if rule["judge"] == "hip_below_knee_estimate":
            findings.append(depth_finding(frames, rep, side, rule, margin))
            continue
        findings.append({
            "rep": rep["rep"],
            "criterion": rule["id"],
            "section": rule["section"],
            "source_pages": rule["source_pages"],
            "result": "cannot_assess",
            "bottom_frame": rep.get("bottom_frame"),
            "time_seconds": rep.get("time_seconds"),
            "measurement": None,
            "explanation": rule["uncertainty"],
        })
    return findings


def main(path: Path) -> None:
    skill = load_skill()
    landmarker = load_video_landmarker()
    try:
        fps, frames = collect(path, landmarker)
    finally:
        landmarker.close()
    side = choose_side(frames)
    for rep in find_reps(hip_series(frames, side), fps):
        for finding in assess_rep(frames, rep, side, skill):
            print(finding)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit('Usage: uv run python -m app.measure "samples/squat.mp4.f313.webm"')
    main(Path(sys.argv[1]))
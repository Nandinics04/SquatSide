import math
import sys
from pathlib import Path

from app.overlay import VISIBLE, choose_side, collect, load_video_landmarker
from app.reps import MIN_DROP, find_reps, hip_series
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


def _point(points: dict, name: str):
    point = points.get(name)
    if point is None or point[2] < VISIBLE:
        return None
    return point


def _blank(rep: dict, rule: dict) -> dict:
    return {
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


def _reported(frames: list[dict], rep: dict, side: str, rule: dict, measure) -> dict:
    finding = _blank(rep, rule)
    if rep.get("status") != "measured":
        finding["explanation"] = rep.get("reason", "This rep has no measured bottom.")
        return finding
    measurement, sentence = measure(frames, rep, side)
    if measurement is None:
        finding["explanation"] = sentence
        return finding
    finding["measurement"] = measurement
    finding["explanation"] = sentence + " " + rule["uncertainty"]
    return finding


def _joint_angle(a, b, c):
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return None
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _back_angle(shoulder, hip):
    dx = shoulder[0] - hip[0]
    dy_up = hip[1] - shoulder[1]
    if dx == 0 and dy_up == 0:
        return None
    return math.degrees(math.atan2(dy_up, abs(dx)))


def _top_frame(frames: list[dict], bottom: int, side: str) -> int:
    best = bottom
    best_y = None
    for frame in range(bottom, -1, -1):
        hip = _point(frames[frame], f"{side}_hip")
        if hip is None:
            continue
        if best_y is None or hip[1] <= best_y:
            best_y = hip[1]
            best = frame
            continue
        if hip[1] >= best_y + MIN_DROP:
            break
    return best


def measure_back_angle(frames: list[dict], rep: dict, side: str):
    points = frames[rep["bottom_frame"]]
    shoulder = _point(points, f"{side}_shoulder")
    hip = _point(points, f"{side}_hip")
    if shoulder is None or hip is None:
        return None, "The shoulder or hip is not visible at the bottom."
    angle = _back_angle(shoulder, hip)
    if angle is None:
        return None, "The shoulder and hip are the same point."
    degrees = round(angle, 1)
    return {"back_angle_deg": degrees}, f"The torso angle against the floor is {degrees} degrees."


def measure_segment_angles(frames: list[dict], rep: dict, side: str):
    points = frames[rep["bottom_frame"]]
    shoulder = _point(points, f"{side}_shoulder")
    hip = _point(points, f"{side}_hip")
    knee = _point(points, f"{side}_knee")
    ankle = _point(points, f"{side}_ankle")
    measurement = {}
    parts = []
    if shoulder is not None and hip is not None and knee is not None:
        angle = _joint_angle(shoulder, hip, knee)
        if angle is not None:
            measurement["hip_angle_deg"] = round(angle, 1)
            parts.append(f"the hip angle is {measurement['hip_angle_deg']} degrees")
    if hip is not None and knee is not None and ankle is not None:
        angle = _joint_angle(hip, knee, ankle)
        if angle is not None:
            measurement["knee_angle_deg"] = round(angle, 1)
            parts.append(f"the knee angle is {measurement['knee_angle_deg']} degrees")
    if not measurement:
        return None, "The shoulder, hip, knee, or ankle is not visible at the bottom."
    return measurement, "At the bottom, " + " and ".join(parts) + "."


def measure_knee_vs_toes(frames: list[dict], rep: dict, side: str):
    points = frames[rep["bottom_frame"]]
    knee = _point(points, f"{side}_knee")
    toe = _point(points, f"{side}_foot_index")
    heel = _point(points, f"{side}_heel")
    if knee is None or toe is None or heel is None:
        return None, "The knee, heel, or toes are not visible at the bottom."
    forward = toe[0] - heel[0]
    if abs(forward) < 1e-6:
        return None, "The foot does not show which way is forward."
    ahead = (knee[0] - toe[0]) * (1 if forward > 0 else -1)
    measurement = {"knee_ahead": round(ahead, 3)}
    amount = abs(measurement["knee_ahead"])
    if measurement["knee_ahead"] >= 0:
        sentence = f"The knee is {amount} of the image width in front of the toes."
    else:
        sentence = f"The knee is {amount} of the image width behind the toes."
    return measurement, sentence


def measure_hip_drive(frames: list[dict], rep: dict, side: str):
    start = rep["bottom_frame"]
    hip0 = _point(frames[start], f"{side}_hip")
    shoulder0 = _point(frames[start], f"{side}_shoulder")
    if hip0 is None or shoulder0 is None:
        return None, "The hip or shoulder is not visible at the bottom."
    end = None
    for frame in range(start + 1, len(frames)):
        hip = _point(frames[frame], f"{side}_hip")
        shoulder = _point(frames[frame], f"{side}_shoulder")
        if hip is None or shoulder is None:
            continue
        end = frame
        if hip0[1] - hip[1] >= 0.04:
            break
    if end is None:
        return None, "No ascent was recorded after the bottom."
    hip1 = _point(frames[end], f"{side}_hip")
    shoulder1 = _point(frames[end], f"{side}_shoulder")
    measurement = {
        "hip_rise": round(hip0[1] - hip1[1], 3),
        "shoulder_rise": round(shoulder0[1] - shoulder1[1], 3),
    }
    sentence = (
        "On the early ascent the hip rose "
        f"{measurement['hip_rise']} and the shoulder rose {measurement['shoulder_rise']} "
        "of the image height."
    )
    return measurement, sentence


def measure_gaze(frames: list[dict], rep: dict, side: str):
    points = frames[rep["bottom_frame"]]
    ear = _point(points, f"{side}_ear")
    nose = _point(points, "nose")
    if ear is None or nose is None:
        return None, "The ear or the nose is not visible at the bottom."
    dx = abs(nose[0] - ear[0])
    dy = nose[1] - ear[1]
    if dx == 0 and dy == 0:
        return None, "The nose and the ear are the same point."
    tilt = round(math.degrees(math.atan2(dy, dx)), 1)
    if tilt > 0:
        sentence = f"The nose is {tilt} degrees below the ear."
    elif tilt < 0:
        sentence = f"The nose is {abs(tilt)} degrees above the ear."
    else:
        sentence = "The nose is level with the ear."
    return {"chin_tilt_deg": tilt}, sentence


def measure_heels(frames: list[dict], rep: dict, side: str):
    bottom = rep["bottom_frame"]
    standing = _top_frame(frames, bottom, side)
    if standing == bottom:
        return None, "No standing position was recorded before the bottom."
    heel0 = _point(frames[standing], f"{side}_heel")
    heel1 = _point(frames[bottom], f"{side}_heel")
    if heel0 is None or heel1 is None:
        return None, "The heel is not visible."
    rise = round(heel0[1] - heel1[1], 3)
    amount = abs(rise)
    if rise > 0:
        sentence = f"The heel point is {amount} of the image height higher at the bottom than when standing."
    elif rise < 0:
        sentence = f"The heel point is {amount} of the image height lower at the bottom than when standing."
    else:
        sentence = "The heel point is at the same height as when standing."
    return {"heel_rise": rise}, sentence


REPORTED = {
    "back_angle_deg": measure_back_angle,
    "report_only": measure_segment_angles,
    "knee_vs_toes": measure_knee_vs_toes,
    "hip_drive_direction": measure_hip_drive,
    "gaze_direction": measure_gaze,
    "heels_down": measure_heels,
}


def assess_rep(frames: list[dict], rep: dict, side: str, skill: dict) -> list[dict]:
    margin = next(item["value"] for item in skill["assumptions"] if item["id"] == "depth_margin")
    findings = []
    for rule in skill["criteria"]:
        if rule["judge"] == "hip_below_knee_estimate":
            findings.append(depth_finding(frames, rep, side, rule, margin))
            continue
        measure = REPORTED.get(rule["judge"])
        if measure is not None:
            findings.append(_reported(frames, rep, side, rule, measure))
            continue
        finding = _blank(rep, rule)
        if rep.get("status") != "measured":
            finding["explanation"] = rep.get("reason", "This rep has no measured bottom.")
        findings.append(finding)
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
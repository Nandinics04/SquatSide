from app.measure import assess_rep, depth_finding

RULE = {
    "id": "depth",
    "section": "Figure 2-1; Squat Depth",
    "source_pages": [2, 15, 17],
    "uncertainty": "Joint estimate.",
    "miss_feedback": "Go deeper.",
}


def finding(hip_y, knee_y, hip_v=1.0, knee_v=1.0):
    frames = [{
        "left_hip": (0.5, hip_y, hip_v),
        "left_knee": (0.5, knee_y, knee_v),
    }]
    rep = {"rep": 1, "status": "measured", "bottom_frame": 0, "time_seconds": 1.0}
    return depth_finding(frames, rep, "left", RULE, margin=0.03)


def test_hip_below_knee_meets():
    assert finding(0.80, 0.70)["result"] == "meets"


def test_hip_above_knee_misses():
    result = finding(0.60, 0.75)
    assert result["result"] == "does_not_meet"
    assert result["source_pages"] == [2, 15, 17]


def test_hidden_knee_is_not_graded():
    assert finding(0.80, 0.70, knee_v=0.2)["result"] == "cannot_assess"


def test_close_hip_and_knee_is_not_called():
    assert finding(0.80, 0.81)["result"] == "cannot_assess"


def _side_pose():
    standing = {
        "left_shoulder": (0.40, 0.30, 1),
        "left_hip": (0.40, 0.55, 1),
        "left_knee": (0.48, 0.75, 1),
        "left_ankle": (0.48, 0.90, 1),
        "left_heel": (0.46, 0.92, 1),
        "left_foot_index": (0.58, 0.92, 1),
        "left_ear": (0.42, 0.22, 1),
        "nose": (0.50, 0.24, 1),
    }
    bottom={
        "left_shoulder": (0.55, 0.40, 1),
        "left_hip": (0.40, 0.70, 1),
        "left_knee": (0.62, 0.78, 1),
        "left_ankle": (0.50, 0.92, 1),
        "left_heel": (0.46, 0.88, 1),
        "left_foot_index": (0.58, 0.92, 1),
        "left_ear": (0.48, 0.32, 1),
        "nose": (0.56, 0.40, 1),
    }
    ascent={
        "left_shoulder": (0.50, 0.28, 1),
        "left_hip": (0.40, 0.64, 1),
        "left_knee": (0.55, 0.78, 1),
        "left_ankle": (0.50, 0.92, 1),
        "left_heel": (0.46, 0.90, 1),
        "left_foot_index": (0.58, 0.92, 1),
        "left_ear": (0.46, 0.24, 1),
        "nose": (0.54, 0.28, 1),
    }
    return [standing,bottom,ascent]


def test_back_angle_is_reported_and_not_graded():
    rule = {
        "id": "back_angle",
        "section": "Back",
        "source_pages": [9],
        "judge": "back_angle_deg",
        "uncertainty": "No band.",
    }
    frames = [{"left_shoulder": (0.50, 0.40, 1), "left_hip": (0.40, 0.50, 1)}]
    rep = {"rep": 1, "status": "measured", "bottom_frame": 0, "time_seconds": 1.0}
    skill = {"assumptions": [{"id": "depth_margin", "value": 0.03}], "criteria": [rule]}
    result = assess_rep(frames, rep, "left", skill)[0]
    assert result["result"] == "cannot_assess"
    assert result["measurement"]["back_angle_deg"] == 45.0


def test_segment_angles_are_reported_and_not_graded():
    rule = {
        "id": "segment_angles",
        "section": "Angles",
        "source_pages": [9],
        "judge": "report_only",
        "uncertainty": "Report only.",
    }
    frames=[{
        "left_shoulder": (0.40, 0.30, 1),
        "left_hip": (0.40, 0.50, 1),
        "left_knee": (0.60, 0.50, 1),
        "left_ankle": (0.60, 0.70, 1),
    }]
    rep = {"rep": 1, "status": "measured", "bottom_frame": 0, "time_seconds": 1.0}
    skill = {"assumptions": [{"id": "depth_margin", "value": 0.03}], "criteria": [rule]}
    result = assess_rep(frames, rep, "left", skill)[0]
    assert result["result"] == "cannot_assess"
    assert result["measurement"]["hip_angle_deg"] == 90.0
    assert result["measurement"]["knee_angle_deg"] == 90.0


def test_knee_heel_gaze_and_drive_numbers_stay_cannot_assess():
    from app.skill import load_skill
    rep = {"rep": 1, "status": "measured", "bottom_frame": 1, "time_seconds": 1.0}
    findings = {item["criterion"]: item for item in assess_rep(_side_pose(), rep, "left", load_skill())}
    assert findings["knee_vs_toes"]["result"] == "cannot_assess"
    assert findings["knee_vs_toes"]["measurement"]["knee_ahead"] > 0
    assert findings["hip_drive"]["result"] == "cannot_assess"
    assert findings["hip_drive"]["measurement"]["shoulder_rise"] > findings["hip_drive"]["measurement"]["hip_rise"]
    assert findings["gaze"]["result"] == "cannot_assess"
    assert findings["gaze"]["measurement"]["chin_tilt_deg"] > 0
    assert findings["heels_down"]["result"] == "cannot_assess"
    assert findings["heels_down"]["measurement"]["heel_rise"] > 0
    assert findings["bar_over_midfoot"]["measurement"] is None
    assert findings["depth"]["result"] in {"meets", "does_not_meet", "cannot_assess"}


def test_front_view_rule_is_not_graded():
    rule = {
        "id": "knees_out",
        "section": "Stance",
        "source_pages": [14],
        "judge": "none",
        "uncertainty": "Front view only.",
    }
    rep = {"rep": 1, "status": "measured", "bottom_frame": 0, "time_seconds": 1.0}
    skill = {"assumptions": [{"id": "depth_margin", "value": 0.03}], "criteria": [rule]}
    result = assess_rep([{}], rep, "left", skill)[0]
    assert result["result"] == "cannot_assess"
    assert result["criterion"] == "knees_out"
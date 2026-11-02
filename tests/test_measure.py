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
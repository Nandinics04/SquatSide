from app.reps import find_reps


def test_two_squats_make_two_reps():
    one=[0.40, 0.50, 0.60, 0.70, 0.60, 0.50, 0.40]
    reps=find_reps(one + one, fps=10)
    assert [rep["bottom_frame"] for rep in reps] == [3, 10]
    assert all(rep["status"] == "measured" for rep in reps)


def test_no_downward_movement_finds_no_reps():
    assert find_reps([0.40] * 15, fps=10)==[]


def test_hidden_hip_is_not_counted():
    reps=find_reps([None] * 12, fps=10)
    assert reps == [{
        "rep": None,
        "status": "cannot_assess",
        "reason": "Hip is not visible enough to find repetitions.",
    }]

def test_slow_squat_with_a_pause_is_one_rep():
    descent=[0.65+index * 0.01 for index in range(18)]
    pause=[0.82] * 10
    ascent=[0.82 - index * 0.02 for index in range(10)]
    reps=find_reps(descent + pause + ascent, fps=30)
    assert len(reps)==1
    assert reps[0]["status"] == "measured"
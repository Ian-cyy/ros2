import cv2
import numpy as np

from robot_vision.ball_detector import BallDetector


def detector():
    return BallDetector({
        "min_ball_area": 300.0,
        "min_ball_radius": 8.0,
        "max_ball_radius": 220.0,
        "min_circularity": 0.60,
        "min_circle_fill": 0.65,
        "morphology_kernel_size": 5,
        "center_score_weight": 0.25,
        "ball_order_min_x": 20.0,
        "ball_order_max_x": 620.0,
        "hsv_ranges": {
            "red": [((0, 70, 35), (12, 255, 255)), ((168, 70, 35), (180, 255, 255))],
            "green": [((35, 45, 30), (90, 255, 255))],
            "blue": [((92, 50, 30), (135, 255, 255))],
        },
    })


def test_detect_red_ball():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(image, (320, 240), 35, (0, 0, 255), -1)
    result, mask, candidates = detector().detect(image, "red")
    assert result is not None
    assert abs(result.x - 320) <= 2
    assert abs(result.y - 240) <= 2
    assert len(candidates) == 1
    assert int(mask.sum()) > 0


def test_rejects_small_noise():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(image, (100, 100), 4, (0, 0, 255), -1)
    result, _, _ = detector().detect(image, "red")
    assert result is None


def test_rejects_ball_outside_x_range():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(image, (10, 240), 35, (0, 0, 255), -1)
    result, _, _ = detector().detect(image, "red")
    assert result is None


def test_selects_best_candidate():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(image, (80, 80), 25, (0, 0, 255), -1)
    cv2.circle(image, (320, 240), 35, (0, 0, 255), -1)
    result, _, candidates = detector().detect(image, "red")
    assert len(candidates) == 2
    assert result is not None
    assert abs(result.x - 320) <= 2
    assert abs(result.y - 240) <= 2

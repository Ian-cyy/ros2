"""颜色小球检测器。

算法按比赛单体的 detect_ball() 移植：HSV 分割、形态学开闭运算、
面积/半径/圆度/圆填充率筛选，再按候选质量和靠近图像中心程度选一颗。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class BallDetection:
    """检测到的小球信息，坐标单位是像素。"""

    x: float
    y: float
    radius: float
    score: float
    contour: np.ndarray


class BallDetector:
    """检测指定颜色的小球，并返回最佳候选和二值掩膜。"""

    def __init__(self, params: Dict[str, object]):
        self.min_area = float(params["min_ball_area"])
        self.min_radius = float(params["min_ball_radius"])
        self.max_radius = float(params["max_ball_radius"])
        self.min_circularity = float(params["min_circularity"])
        self.min_circle_fill = float(params["min_circle_fill"])
        self.kernel_size = int(params["morphology_kernel_size"])
        self.center_weight = float(params["center_score_weight"])
        # 与单体一致：球心 x 超出该范围就不算目标（挡掉贴边/画面外的干扰）
        self.order_min_x = float(params["ball_order_min_x"])
        self.order_max_x = float(params["ball_order_max_x"])
        self.hsv_ranges = params["hsv_ranges"]

    def detect(
        self, frame: np.ndarray, color: str
    ) -> Tuple[Optional[BallDetection], np.ndarray, List[BallDetection]]:
        """返回 (最佳候选, 掩膜, 全部通过筛选的候选)。"""
        if frame is None or frame.ndim != 3:
            raise ValueError("frame must be a BGR color image")
        if color not in self.hsv_ranges:
            raise ValueError(f"unsupported ball color: {color}")

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for low, high in self.hsv_ranges[color]:
            mask |= cv2.inRange(
                hsv, np.asarray(low, dtype=np.uint8), np.asarray(high, dtype=np.uint8)
            )

        kernel = np.ones((self.kernel_size, self.kernel_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        candidates = []
        image_center = (frame.shape[1] / 2.0, frame.shape[0] / 2.0)
        diagonal = max(1.0, float(np.hypot(frame.shape[1], frame.shape[0])))
        for contour in contours:
            area = float(cv2.contourArea(contour))
            perimeter = float(cv2.arcLength(contour, True))
            if area < self.min_area or perimeter <= 0:
                continue
            circularity = 4.0 * np.pi * area / (perimeter * perimeter)
            (x, y), radius = cv2.minEnclosingCircle(contour)
            fill = area / (np.pi * radius * radius) if radius > 0 else 0.0
            if not self.min_radius <= radius <= self.max_radius:
                continue
            if circularity < self.min_circularity or fill < self.min_circle_fill:
                continue
            if not self.order_min_x <= x <= self.order_max_x:
                continue
            quality = area * circularity * fill
            distance = float(np.hypot(x - image_center[0], y - image_center[1]))
            center_score = 1.0 - min(distance / diagonal, 1.0)
            score = quality * (1.0 + self.center_weight * center_score)
            candidates.append(BallDetection(x, y, radius, score, contour))

        best = max(candidates, key=lambda item: item.score) if candidates else None
        return best, mask, candidates

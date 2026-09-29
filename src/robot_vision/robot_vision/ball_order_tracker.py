"""三色小球的连续稳定出现顺序跟踪器。"""


class BallOrderTracker:
    """按单体逻辑记录颜色首次连续稳定出现的顺序。"""

    COLOR_CODES = {"red": 1, "green": 2, "blue": 3}

    def __init__(self, stable_frames=4):
        self.stable_frames = int(stable_frames)
        self.reset()

    def reset(self):
        """清空本次识别流程的顺序和各颜色稳定计数。"""
        self.order = []
        self.stable = {color: 0 for color in self.COLOR_CODES}

    def update(self, visible_colors):
        """输入本帧检测到的颜色集合，返回当前颜色编码顺序。"""
        for color in self.COLOR_CODES:
            if color in visible_colors:
                self.stable[color] += 1
            else:
                self.stable[color] = 0

            if (
                self.stable[color] >= self.stable_frames
                and color not in self.order
            ):
                self.order.append(color)
        return [self.COLOR_CODES[color] for color in self.order]

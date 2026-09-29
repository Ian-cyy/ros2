"""ROS2 视觉节点：当前实现颜色小球检测（active_id=1）。"""

from typing import Dict, List, Tuple

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from robot_interfaces.msg import TargetPos
from sensor_msgs.msg import Image

from .ball_detector import BallDetector, BallDetection


class VisionNode(Node):
    """订阅图像，每帧检测一个激活目标，并持续发布结果。"""

    def __init__(self):
        super().__init__("vision_node")
        self._declare_parameters()
        self.bridge = CvBridge()
        self.target_pub = self.create_publisher(TargetPos, self.target_topic, 10)
        self.debug_pub = self.create_publisher(
            Image, self.debug_topic, qos_profile_sensor_data
        )
        self.detector = BallDetector(self._detector_params())
        self._smooth_x = None
        self._smooth_y = None
        self._subscription = self.create_subscription(
            Image, self.image_topic, self._on_image, qos_profile_sensor_data
        )
        self.add_on_set_parameters_callback(self._on_parameters)
        self.get_logger().info(
            f"vision ready: active_id={self.active_id} color={self.ball_color} "
            f"input={self.image_topic} output={self.target_topic}"
        )

    def _declare_parameters(self):
        """声明 YAML 可覆盖的运行参数。"""
        self.declare_parameter("active_id", 1)
        self.declare_parameter("ball_color", "red")
        self.declare_parameter("position_smoothing_alpha", 0.35)
        self.declare_parameter("min_ball_area", 300.0)
        self.declare_parameter("min_ball_radius", 8.0)
        self.declare_parameter("max_ball_radius", 220.0)
        self.declare_parameter("min_circularity", 0.60)
        self.declare_parameter("min_circle_fill", 0.65)
        self.declare_parameter("morphology_kernel_size", 5)
        self.declare_parameter("center_score_weight", 0.25)
        # 球心 x 允许范围（对标单体 ball_order_min_x / ball_order_max_x）
        self.declare_parameter("ball_order_min_x", 20.0)
        self.declare_parameter("ball_order_max_x", 620.0)
        # ROS2 参数数组只能是一维基础类型，这里每 6 个数表示一个 HSV 区间：
        # low_h, low_s, low_v, high_h, high_s, high_v。
        self.declare_parameter(
            "red_hsv_ranges", [0, 70, 35, 12, 255, 255, 168, 70, 35, 180, 255, 255]
        )
        self.declare_parameter("green_hsv_ranges", [35, 45, 30, 90, 255, 255])
        self.declare_parameter("blue_hsv_ranges", [92, 50, 30, 135, 255, 255])
        self.declare_parameter("publish_debug_image", True)
        self.declare_parameter("image_topic", "/c70/image_raw")
        self.declare_parameter("target_topic", "/vision/target_pos")
        self.declare_parameter("debug_topic", "/vision/debug_image")
        self._refresh_parameters()

    def _refresh_parameters(self):
        self.active_id = int(self.get_parameter("active_id").value)
        self.ball_color = str(self.get_parameter("ball_color").value)
        self.position_alpha = float(
            self.get_parameter("position_smoothing_alpha").value
        )
        self.publish_debug_image = bool(
            self.get_parameter("publish_debug_image").value
        )
        self.image_topic = str(self.get_parameter("image_topic").value)
        self.target_topic = str(self.get_parameter("target_topic").value)
        self.debug_topic = str(self.get_parameter("debug_topic").value)

    def _detector_params(self) -> Dict[str, object]:
        def parse_ranges(name: str) -> List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
            values = [int(value) for value in self.get_parameter(name).value]
            if len(values) == 0 or len(values) % 6 != 0:
                raise ValueError(f"{name} must contain 6*N integers")
            return [
                ((values[index], values[index + 1], values[index + 2]),
                 (values[index + 3], values[index + 4], values[index + 5]))
                for index in range(0, len(values), 6)
            ]

        return {
            "min_ball_area": float(self.get_parameter("min_ball_area").value),
            "min_ball_radius": float(self.get_parameter("min_ball_radius").value),
            "max_ball_radius": float(self.get_parameter("max_ball_radius").value),
            "min_circularity": float(self.get_parameter("min_circularity").value),
            "min_circle_fill": float(self.get_parameter("min_circle_fill").value),
            "morphology_kernel_size": int(
                self.get_parameter("morphology_kernel_size").value
            ),
            "center_score_weight": float(
                self.get_parameter("center_score_weight").value
            ),
            "ball_order_min_x": float(self.get_parameter("ball_order_min_x").value),
            "ball_order_max_x": float(self.get_parameter("ball_order_max_x").value),
            "hsv_ranges": {
                "red": parse_ranges("red_hsv_ranges"),
                "green": parse_ranges("green_hsv_ranges"),
                "blue": parse_ranges("blue_hsv_ranges"),
            },
        }

    def _on_parameters(self, params):
        """参数变更后重建检测器；active_id 改变时清空旧平滑值。"""
        for parameter in params:
            if parameter.name == "position_smoothing_alpha":
                if not 0.0 < float(parameter.value) <= 1.0:
                    return SetParametersResult(
                        successful=False, reason="alpha must be in (0, 1]"
                    )
            if parameter.name == "active_id" and int(parameter.value) != self.active_id:
                self._reset_smoothing()
        self._refresh_parameters()
        self.detector = BallDetector(self._detector_params())
        return SetParametersResult(successful=True)

    def _reset_smoothing(self):
        self._smooth_x = None
        self._smooth_y = None

    def _on_image(self, message: Image):
        """每帧处理：识别、平滑、发布 TargetPos 和可视化图。"""
        frame = self.bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        debug = frame.copy()
        valid = False
        x = -1
        y = -1
        detection = None

        if self.active_id == 1:
            try:
                detection, mask, _ = self.detector.detect(frame, self.ball_color)
            except ValueError as error:
                self.get_logger().error(str(error))
                detection, mask = None, np.zeros(frame.shape[:2], dtype=np.uint8)
            if detection is not None:
                x, y = self._smooth(detection.x, detection.y)
                valid = True
                self._draw_detection(debug, detection, x, y)
            else:
                self._reset_smoothing()
        else:
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            self._reset_smoothing()

        self._draw_status(debug, valid, x, y, mask)
        result = TargetPos()
        result.header = message.header
        result.x = int(x)
        result.y = int(y)
        result.id = self.active_id
        result.valid = valid
        self.target_pub.publish(result)
        if self.publish_debug_image:
            debug_msg = self.bridge.cv2_to_imgmsg(debug, encoding="bgr8")
            debug_msg.header = message.header
            self.debug_pub.publish(debug_msg)

    def _smooth(self, x: float, y: float):
        if self._smooth_x is None:
            self._smooth_x, self._smooth_y = x, y
        else:
            alpha = self.position_alpha
            self._smooth_x = alpha * x + (1.0 - alpha) * self._smooth_x
            self._smooth_y = alpha * y + (1.0 - alpha) * self._smooth_y
        return round(self._smooth_x), round(self._smooth_y)

    @staticmethod
    def _draw_detection(frame, detection: BallDetection, x: int, y: int):
        cv2.drawContours(frame, [detection.contour], -1, (0, 255, 0), 2)
        cv2.circle(frame, (round(detection.x), round(detection.y)), round(detection.radius), (255, 0, 0), 2)
        cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

    def _draw_status(self, frame, valid: bool, x: int, y: int, mask):
        status = f"id={self.active_id} color={self.ball_color} valid={valid} x={x} y={y}"
        cv2.putText(frame, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

    def destroy_node(self):
        self._reset_smoothing()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

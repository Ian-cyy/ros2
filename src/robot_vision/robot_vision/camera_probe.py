"""无头验收小工具：订阅一帧图像并存盘。

订阅 ``/c70/image_raw``，收到第一帧后存成 ``/tmp/c70_probe.jpg``，
这样没有显示器也能确认画面确实发出来了。
"""

import os

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class CameraProbe(Node):
    def __init__(self):
        super().__init__("camera_probe")
        self.declare_parameter("topic", "/c70/image_raw")
        self.declare_parameter("output", "/tmp/c70_probe.jpg")
        self.topic = self.get_parameter("topic").value
        self.output = self.get_parameter("output").value
        self.bridge = CvBridge()
        self.done = False  # 收到一帧就置 True，主循环据此退出
        # ★ 必须用和发布端一致的 sensor_data QoS，否则收不到（QoS 不兼容）
        self.sub = self.create_subscription(
            Image, self.topic, self._on_image, qos_profile_sensor_data
        )
        self.get_logger().info(f"waiting for one frame on {self.topic} ...")

    def _on_image(self, message):
        """收到一帧：bgr8 解码 -> 写 jpg -> 打日志。"""
        if self.done:
            return
        self.done = True
        frame = self.bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        directory = os.path.dirname(self.output)
        if directory:
            os.makedirs(directory, exist_ok=True)
        cv2.imwrite(self.output, frame)
        self.get_logger().info(
            f"received {message.width}x{message.height} "
            f"encoding={message.encoding} "
            f"frame_id={message.header.frame_id} -> {self.output}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = CameraProbe()
    done = False
    try:
        # 转圈直到收到一帧（或 Ctrl-C / 被外部结束）
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.5)
        done = node.done
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()
    return 0 if done else 1  # 收到帧返回 0，否则 1


if __name__ == "__main__":
    raise SystemExit(main())

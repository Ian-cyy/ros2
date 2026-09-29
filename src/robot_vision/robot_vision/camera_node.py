"""C70（眼在手）摄像头的 ROS2 节点。

把摄像头画面发布成 ``/c70/image_raw``（``sensor_msgs/Image``，``bgr8``），
约 30fps，取流行为与比赛单体 ``c70_mode01.py`` 完全一致
（V4L2 + MJPG + 严格分辨率）。

树莓派上 ``/dev/video0`` 就是 C70；笔记本上只要改 ``video_device``
参数即可用自带摄像头模拟，代码不用动。
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from .frame_grabber import open_camera, DEFAULT_FPS


class CameraNode(Node):
    def __init__(self):
        super().__init__("camera_node")

        # ---------- 参数声明 ----------
        # 全部可通过 launch / 命令行 / YAML 覆盖，默认值 = 单体 CONFIG
        self.declare_parameter("video_device", "/dev/video0")
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("fps", DEFAULT_FPS)
        self.declare_parameter("frame_id", "c70_camera")
        self.declare_parameter("strict_resolution", True)

        self.video_device = self.get_parameter("video_device").value
        self.width = int(self.get_parameter("width").value)
        self.height = int(self.get_parameter("height").value)
        self.fps = int(self.get_parameter("fps").value)
        self.frame_id = self.get_parameter("frame_id").value
        self.strict_resolution = bool(self.get_parameter("strict_resolution").value)

        # cv_bridge：OpenCV 的 numpy 图 <-> ROS 的 sensor_msgs/Image
        self.bridge = CvBridge()
        # 图像流用 sensor_data QoS（BEST_EFFORT + depth 5），订阅端也要用同样的 QoS
        self.publisher = self.create_publisher(
            Image, "/c70/image_raw", qos_profile_sensor_data
        )

        self.get_logger().info(
            f"opening device={self.video_device} "
            f"size={self.width}x{self.height} fps={self.fps} "
            f"strict={self.strict_resolution}"
        )
        # 打开失败会抛 RuntimeError，由 main() 捕获后以退出码 1 结束
        self.cap = open_camera(
            self.video_device,
            (self.width, self.height),
            fps=self.fps,
            strict_resolution=self.strict_resolution,
            logger=self.get_logger(),
        )

        self.frame_count = 0
        self.read_fail_count = 0
        # 定时器按 fps 拉帧并发布（固定周期，不阻塞 spin）
        self.timer = self.create_timer(1.0 / float(self.fps), self._on_timer)

    def _on_timer(self):
        """定时回调：读一帧 -> 转 ROS 消息 -> 发布。"""
        ok, frame = self.cap.read()
        if not ok or frame is None:
            # 读失败不要刷屏，前 5 次 + 之后每 100 次才告警一次
            self.read_fail_count += 1
            if self.read_fail_count <= 5 or self.read_fail_count % 100 == 0:
                self.get_logger().warn(
                    f"frame read failed ({self.read_fail_count} times)"
                )
            return
        self.read_fail_count = 0
        # encoding=bgr8 对应 OpenCV 默认的 BGR 三通道
        message = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = self.frame_id
        self.publisher.publish(message)
        self.frame_count += 1

    def destroy_node(self):
        """节点销毁时释放摄像头，避免占住 /dev/video0。"""
        if getattr(self, "cap", None) is not None:
            self.cap.release()
            self.cap = None
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    exit_code = 0
    try:
        node = CameraNode()
        rclpy.spin(node)
    except RuntimeError as error:
        # 相机打不开：打印原因，退出码 1
        if node is not None:
            node.get_logger().fatal(str(error))
        else:
            print(f"camera_node: {error}", flush=True)
        exit_code = 1
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

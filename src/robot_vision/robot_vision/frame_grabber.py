"""C70 UVC 摄像头取流模块（纯 OpenCV，不含 ROS）。

行为 1:1 移植自比赛单体 ``c70_mode01.py`` 的 ``open_camera`` /
``switch_camera``（第 768~822 行）：

* Linux / 树莓派走 V4L2 后端；Windows 先 DSHOW 再 MSMF。
* 固定 MJPG 编码，显式设置宽/高/FPS，并严格校验分辨率。
* 切分辨率 = 先 release 再重新打开，最多重试 5 次。

唯一新增的是 ``strict_resolution`` 参数：笔记本摄像头常虚报分辨率，
开发时置 False 也能开；**树莓派上必须保持 True**，以保持与单体一致。
"""

import os
import time

import cv2

# 单体 CONFIG["fps"] = 30，这里提出来做默认值
DEFAULT_FPS = 30


def open_camera(device, size, fps=DEFAULT_FPS, strict_resolution=True, logger=None):
    """按指定 MJPG 模式打开一个 UVC 设备。

    参数：
        device            —— Windows 下是整数索引；Linux 下是路径（如 /dev/video0）
        size              —— (宽, 高) 元组
        fps               —— 帧率
        strict_resolution —— True 时实际分辨率与请求不符就换后端/报错
        logger            —— 传入 rclpy 的 logger 就走 ROS 日志，否则 print

    打不开或没有一个后端能提供该模式时抛 ``RuntimeError``。
    """
    if os.name == "nt":
        # Windows：设备用索引，后端按 DSHOW -> MSMF 依次尝试
        try:
            source = int(device)
        except ValueError as error:
            raise RuntimeError("On Windows, --device must be an index such as 1") from error
        backends = (cv2.CAP_DSHOW, cv2.CAP_MSMF)
    else:
        # Linux / 树莓派：设备是路径，只尝试 V4L2
        source = device
        backends = (cv2.CAP_V4L2,)

    width, height = size
    expected = (width, height)
    errors = []  # 收集每个后端的失败原因，最后一起抛出
    for backend in backends:
        cap = cv2.VideoCapture(source, backend)
        # 固定 MJPG：USB 上 640x480@30 只有 MJPG 才跑得动（YUYV 带宽不够）
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        if not cap.isOpened():
            errors.append(f"backend={backend}: not opened")
            cap.release()
            continue
        # 读回实际分辨率做校验（很多摄像头会悄悄给你别的分辨率）
        actual = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        if strict_resolution and actual != expected:
            errors.append(f"backend={backend}: returned {actual[0]}x{actual[1]}")
            cap.release()
            continue
        message = (
            f"CAMERA_OPEN device={source} backend={backend} "
            f"resolution={actual[0]}x{actual[1]} fps={fps}"
        )
        if logger is not None:
            logger.info(message)
        else:
            print(message, flush=True)
        return cap
    # 所有后端都失败：把原因拼起来，方便现场排查
    raise RuntimeError(
        f"Cannot open C70 at {source} for {width}x{height}; "
        + "; ".join(errors)
        + ". Close other camera apps and verify the device index."
    )


def switch_camera(cap, device, size, fps=DEFAULT_FPS, strict_resolution=True, logger=None):
    """切换分辨率：先释放旧的，再按新分辨率重新打开（最多重试 5 次）。"""
    if cap is not None:
        cap.release()
    last_error = None
    for _ in range(5):
        time.sleep(0.35)  # 给 USB / V4L2 一点时间释放资源
        try:
            return open_camera(
                device, size, fps=fps,
                strict_resolution=strict_resolution, logger=logger,
            )
        except RuntimeError as error:
            last_error = error
    raise RuntimeError(f"Failed to switch C70 to {size[0]}x{size[1]}: {last_error}")

# robot_vision 学习流程（ROS2 camera_node）

> 2026-09-29 · 环境：Ubuntu 22.04 + ROS2 Humble
> 位置：`~/ros2_ws`（Ubuntu 家目录，**不在 NTFS 共享盘**）
> 用途：树莓派主控 `c70_mode01.py` → ROS2 迁移的**第 4 步 camera_node**
> 本文档带你把这个包从"文件夹"到"能跑起来"整个走一遍

---

## 0. 这个包是干什么的

把 C70（眼在手）摄像头的画面，发布成 ROS2 话题 `/c70/image_raw`。
取流逻辑 1:1 移植自比赛单体 `c70_mode01.py`（V4L2 + MJPG + 严格分辨率）。

```text
[摄像头 /dev/video0] ──cv2──▶ frame_grabber ──▶ camera_node ──▶ /c70/image_raw
                                                                    │
                                            camera_probe(验收) ◀────┘
                                            后续 vision_node  ◀────┘
```

树莓派上 `/dev/video0` = C70；笔记本上用自带摄像头模拟，**只改一个参数**。

---

## 1. 目录结构（每一层是什么）

```text
~/ros2_ws/                              ← ROS2 工作区根目录
├── src/                                ← 源码区（只放功能包，唯一要手写的地方）
│   └── robot_vision/                   ← 功能包
│       ├── package.xml                 ← 包清单：名字 + 依赖（rclpy/sensor_msgs/cv_bridge）
│       ├── setup.py                    ← 安装脚本：注册可执行命令 + launch 文件
│       ├── setup.cfg                   ← 告诉 colcon 把包装到 lib/ 还是 share/
│       ├── resource/robot_vision       ← ament 索引标记（空文件，起占位作用）
│       ├── launch/
│       │   └── camera.launch.py        ← 一键启动 + 命令行参数
│       ├── robot_vision/               ← Python 模块（节点代码都在这）
│       │   ├── __init__.py
│       │   ├── frame_grabber.py        ← 纯取流（不依赖 ROS）
│       │   ├── camera_node.py          ← ROS 节点（发话题）
│       │   └── camera_probe.py         ← 无头验收（订阅一帧存图）
│       └── test/                       ← 自动生成的样式检查（可不管）
├── build/                              ← colcon 编译中间产物（可删，重新 build 会再生成）
├── install/                            ← 编译结果 + setup.bash（**运行时 source 这个**）
├── log/                                ← 每次 build 的日志（可删）
└── robot_vision_学习流程.md             ← 本文件
```

**核心区分**：`src/` 是你写的；`build/install/log/` 是 `colcon build` 生成的，**不要手改、不要提交**。

---

## 2. 各个文件 / 文件夹的作用

### 2.1 工作区三件套（build / install / log）

| 目录 | 作用 | 备注 |
|------|------|------|
| `build/` | 编译时的中间文件 | 出问题可整个删掉重 build |
| `install/` | 装好的包，含 `setup.bash` | **每开新终端都要 `source install/setup.bash`** |
| `log/` | 每次 build 的详细日志 | 编译报错看这里 |

### 2.2 功能包 `robot_vision/`

| 文件/目录 | 作用 |
|-----------|------|
| `package.xml` | 包的身份：名字、版本、依赖（`rclpy`/`sensor_msgs`/`cv_bridge`） |
| `setup.py` | ①`data_files` 把 `launch/` 装进 `share/`；②`entry_points` 注册 `camera_node`、`camera_probe` 两条命令 |
| `setup.cfg` | ament_python 的约定：脚本装 `lib/`、数据装 `share/` |
| `resource/robot_vision` | 空标记文件，`ros2 pkg list` 靠它识别包 |
| `launch/camera.launch.py` | Python 描述"启动哪个节点、传什么参数" |
| `robot_vision/frame_grabber.py` | `open_camera()` / `switch_camera()`，纯 OpenCV，可单独测试 |
| `robot_vision/camera_node.py` | 节点主体：声明参数、开相机、定时发图 |
| `robot_vision/camera_probe.py` | 验收节点：订阅一帧存 `/tmp/c70_probe.jpg` |
| `test/*.py` | `ros2 pkg create` 自动生成的版权/格式检查，可忽略 |

### 2.3 三个源码文件的关系

```text
frame_grabber.py   ← 最底层：只管开相机、读帧（换成别的东西也能用）
      ▲
      │ import
camera_node.py     ← ROS 层：把帧包成 sensor_msgs/Image 发出去
      │ 话题 /c70/image_raw
      ▼
camera_probe.py    ← 验证层：订阅话题、存图、报尺寸/编码
```

---

## 3. 参数说明（camera_node）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `video_device` | `/dev/video0` | 树莓派 C70 / 笔记本 webcam |
| `width` / `height` | `640` / `480` | 单体 idle 分辨率 |
| `fps` | `30` | 单体 `CONFIG["fps"]` |
| `frame_id` | `c70_camera` | 图像消息的坐标系名 |
| `strict_resolution` | `true` | 树莓派保持 true；笔记本虚报时设 false |

---

## 4. 从零复现的学习流程

### 第 1 步：环境准备
```bash
lsb_release -a                 # 22.04 -> Humble；24.04 -> Jazzy
sudo apt install -y ros-$ROS_DISTRO-cv-bridge python3-opencv v4l-utils \
                    python3-colcon-common-extensions
v4l2-ctl --list-devices        # 确认摄像头在哪个 /dev/videoN
```

### 第 2 步：建工作区 + 建包
```bash
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws
source /opt/ros/humble/setup.bash
cd src
ros2 pkg create --build-type ament_python robot_vision \
    --dependencies rclpy sensor_msgs cv_bridge
```

### 第 3 步：写代码
按本文第 2 节，依次写 `frame_grabber.py` → `camera_node.py` → `camera_probe.py`，
再改 `setup.py`（注册命令 + launch）和 `launch/camera.launch.py`。

### 第 4 步：编译
```bash
cd ~/ros2_ws
colcon build --packages-select robot_vision
source install/setup.bash
```

### 第 5 步：运行 + 验收（无头）
```bash
# 终端1：起相机节点
ros2 run robot_vision camera_node
# 终端2：验收
ros2 topic hz /c70/image_raw        # 期望 ~30
ros2 topic bw /c70/image_raw        # 640x480 raw ≈ 27MB/s
ros2 run robot_vision camera_probe  # 存 /tmp/c70_probe.jpg，退出码 0
```

### 第 6 步：用 launch 启动
```bash
ros2 launch robot_vision camera.launch.py
ros2 launch robot_vision camera.launch.py video_device:=/dev/video1
ros2 launch robot_vision camera.launch.py strict_resolution:=false --show-args
```

---

## 5. 命令速查

| 命令 | 作用 |
|------|------|
| `colcon build --packages-select robot_vision` | 只编译这个包 |
| `colcon build --symlink-install` | 改 Python 免重编（软链接） |
| `source install/setup.bash` | 每开新终端必做 |
| `ros2 pkg executables robot_vision` | 看注册了哪些命令 |
| `ros2 node list` / `ros2 topic list` | 看节点/话题 |
| `ros2 topic info /c70/image_raw -v` | 看类型和 QoS |
| `ros2 run robot_vision camera_probe` | 存一帧验收 |
| `ros2 param list /camera_node` | 看运行中参数 |

---

## 6. 踩坑记录（本项目实际遇到）

| # | 现象 | 原因 | 解决 |
|---|------|------|------|
| 1 | probe 提示 QoS 不兼容，收不到 | 发布端用了 `sensor_data`(BEST_EFFORT)，订阅端默认 RELIABLE | probe 订阅也用 `qos_profile_sensor_data` |
| 2 | `'Image' object has no attribute 'frame_id'` | 帧号在 `header` 里 | 用 `message.header.frame_id` |
| 3 | 第二次启动报 `not opened` | 上次 `ros2 run` 的**子进程残留**占着摄像头 | `pkill -f lib/robot_vision/camera_node` |
| 4 | launch 传数字报类型错 | 命令行默认是字符串 | 用 `ParameterValue(..., value_type=int/bool)` |
| 5 | 节点能跑但 launch 找不到文件 | `setup.py` 的 `data_files` 没登记 `launch/` | 加 `('share/.../launch', ['launch/camera.launch.py'])` |
| 6 | 改了代码没变化 | 没重新 build / 没 source | `colcon build` + `source install/setup.bash` |
| 7 | `ros2 topic hz` 显示不到 30 | 定时器 + 发布开销，28~29 属正常 | 接受 |

---

## 7. 与后续节点的衔接

- 本包只负责"出图"。下游 `vision_node`（路线图第 5 步）订阅 `/c70/image_raw`，
  移植单体里的球/桶/靶/轮廓检测 + `mode3_pid`。
- 树莓派部署：把整个 `src/robot_vision` 拷到 Pi 的 `~/ros2_learn_ws_01/src/`
  → `colcon build` → 把 `video_device` 改回 C70 的路径即可（零代码改动）。
- 注意：Pi 上的 `robot_interfaces`/`f407_bridge`/`arm_bridge` **仍在 Pi 上无备份**。

---

## 8. 自测清单

```text
[ ] 能说出 src/build/install/log 各自作用
[ ] 知道 setup.py 的 data_files 和 entry_points 各干什么
[ ] 能独立重建这个包并 build 通过
[ ] 能用 camera_probe 验收出图
[ ] 会用 launch 传 video_device / strict_resolution
[ ] 记住了 QoS、ParameterValue、残留子进程三个坑
```

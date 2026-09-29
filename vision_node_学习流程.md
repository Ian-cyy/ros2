# vision_node 学习流程（图像订阅 + 球检测）

> 2026-09-29 · Ubuntu 22.04 + ROS2 Humble
> 工作区：`~/ros2_ws`
> 阶段目标：`/c70/image_raw` → 球检测 → `/vision/target_pos` + `/vision/debug_image`
> 范围：先只跑球检测，不接 F407、机械臂或 mission_node

## 1. 目录结构

```text
~/ros2_ws/
├── src/robot_interfaces/                  ← 自定义 ROS2 消息（ament_cmake）
│   ├── CMakeLists.txt                     ← rosidl 生成规则
│   ├── package.xml                        ← 接口包依赖
│   └── msg/TargetPos.msg                  ← Header+x+y+id+valid
└── src/robot_vision/                      ← Python 相机/视觉包（ament_python）
    ├── config/vision.yaml                 ← 视觉参数默认值
    ├── launch/
    │   ├── camera.launch.py               ← 启动 camera_node
    │   └── vision.launch.py               ← 启动 vision_node 并加载 YAML
    ├── robot_vision/
    │   ├── frame_grabber.py               ← OpenCV/V4L2 取帧
    │   ├── camera_node.py                 ← 发布 /c70/image_raw
    │   ├── ball_detector.py               ← 不依赖 ROS 的球检测算法
    │   ├── ball_order_tracker.py          ← 三色连续稳定顺序
    │   └── vision_node.py                 ← ROS 订阅/检测/发布
    └── test/test_ball_detector.py         ← 合成图离线算法测试
```

## 2. 数据流与职责

```text
摄像头
  ↓ OpenCV
camera_node ──sensor_msgs/Image──▶ /c70/image_raw
                                      ↓ sensor-data QoS
                                 vision_node
                                   ├─ BallDetector.detect(frame, color)
                                   ├─ 平滑目标中心坐标
                                   ├─ /vision/target_pos (robot_interfaces/TargetPos)
                                   └─ /vision/debug_image (画框、中心点、状态)
```

- `robot_interfaces` 用 CMake 构建，因为 ROS2 自定义接口由 `rosidl` 生成，不由 Python 包生成。
- `ball_detector.py` 只做图像算法，输入 BGR numpy 图，输出最佳球、mask、候选集合，便于离线测试。
- `vision_node.py` 负责 ROS 消息、参数、时间戳、话题和节点生命周期。

## 2.1 三色顺序话题

单体 mode2 会同时检测红/绿/蓝。某颜色连续出现 4 帧后，按首次稳定出现的先后加入顺序，颜色编码为 `1=红、2=绿、3=蓝`。

```text
/vision/ball_order  robot_interfaces/msg/BallOrder
  Header header
  uint8[] order

/vision/reset       std_msgs/msg/Empty
```

`/vision/reset` 用于上层开始一次新的球识别流程：收到后清空 `order`、各颜色稳定计数和目标坐标平滑状态。`/vision/ball_order` 在球检测流程中每帧发布当前顺序；真正的目标索引和是否后退由未来 `mission_node` 决定。

## 3. TargetPos 消息

```text
std_msgs/Header header
int16 x
int16 y
uint8 id
bool valid
```

- `header.stamp`：输入图像的时间戳；`header.frame_id` 沿用相机消息。
- `x/y`：图像像素坐标，原点在左上，单位 pixel。
- `id=1`：颜色小球；约定预留 `2=桶`、`3=轮廓`。
- 未检测到时每帧仍发布：`valid=false, x=-1, y=-1`。
- 当前接口是本地暂定版；Pi 上已有接口包未备份，回到 Pi 后必须核对字段并合并。

## 4. 球检测算法

移植自比赛单体 `c70_mode01.py` 的 `detect_ball()`：

1. BGR 转 HSV。
2. 按 `ball_color` 对红/绿/蓝阈值做 `inRange`；红色使用两个 HSV 区间以跨越色相 0/180 边界。
3. 5x5 morphology open 去小噪点，再 close 补小孔洞。
4. 找外轮廓，按面积、半径、圆度、圆填充率过滤，并要求球心 x 落在 `ball_order_min_x ~ ball_order_max_x`（对标单体的越界防线）。
5. 按 `area * circularity * circle_fill` 和中心偏好综合打分，选一个候选。
6. 用 EMA 平滑中心：`smooth = alpha*new + (1-alpha)*old`。

`vision.yaml` 中所有检测参数通过 ROS 参数声明，运行时可查改；HSV 每 6 个整数是一组 `[low_h,low_s,low_v,high_h,high_s,high_v]`。

## 5. 构建与验证

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-up-to robot_vision
source install/setup.bash
```

### 5.1 离线算法单测（不需要 ROS master 节点或摄像头）

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
python3 -m pytest -q src/robot_vision/test/test_ball_detector.py
```

单测用 OpenCV 生成红色圆形合成图，检查中心坐标、小噪声拒绝和多候选选择。

### 5.2 实时摄像头验证

终端 1：

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run robot_vision camera_node
```

终端 2：

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch robot_vision vision.launch.py active_id:=1 ball_color:=red
```

终端 3 查看输出：

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 topic hz /vision/target_pos
ros2 topic echo /vision/target_pos
ros2 topic hz /vision/debug_image
ros2 topic echo /vision/ball_order
```

预期：图像收到一帧处理一帧（接近 camera 的 30Hz）；没球时持续 `valid: false`；放入红球后 `valid: true` 且 x/y 随位置变化。可用 `rqt_image_view /vision/debug_image` 查看画框图。

重置一次识别流程：

```bash
ros2 topic pub --once /vision/reset std_msgs/msg/Empty "{}"
```

测试顺序时，让红/绿/蓝球依次进入画面并保持稳定；连续 4 帧后，`/vision/ball_order` 应依次出现 `[1]`、`[1, 2]`、`[1, 2, 3]`。

### 5.3 参数检查/运行时调色

```bash
ros2 param list /vision_node
ros2 param get /vision_node active_id
ros2 param set /vision_node ball_color green
ros2 param set /vision_node active_id 2
```

当前仅实现 id=1 的球检测；其他 id 会发对应 id 的 invalid，不会误跑球算法。新增检测器时在 `vision_node.py` 按 id 分派。

## 6. 常见问题

| 现象 | 排查 |
|---|---|
| 找不到 `robot_interfaces.msg` | 先 `colcon build --packages-up-to robot_vision`，并 source 当前 `install/setup.bash` |
| 图像订阅不到 | camera/vision 都使用 sensor-data QoS；检查 `/c70/image_raw` 是否存在、两节点是否同 ROS_DOMAIN_ID |
| debug 图没有窗口 | 这是话题，不自动弹窗；用 `rqt_image_view /vision/debug_image` |
| 检测不到球 | 先看 debug 图和 mask 单测，再调 `ball_color`、HSV ranges、面积/圆度参数，确认光照和球颜色 |
| active_id 改了没检测 | 当前只实现 id=1；其他 id 只发布 invalid，属于预期 |
| 30Hz 变低 | 同步回调会逐帧处理；先测耗时，Pi 性能另阶段评估，不在本阶段预优化 |

## 7. 本阶段完成标准与边界

- 离线检测单测通过。
- 笔记本摄像头链路能发布 `TargetPos`，未检测时逐帧 invalid。
- debug 话题可看到候选框和最终平滑中心。
- 当前不包含 bucket/靶/轮廓算法，不向 F407 发 0xCC，不控制机械臂。
- 迁移到 Pi 前需核对本地 `TargetPos.msg` 与 Pi 原有 `robot_interfaces`，并测 Pi 的真实处理频率。

### 7.1 与单体的差异（有意）
- 选择准则：单体只按 `area*circularity*circle_fill` 取最大；本实现额外加 `center_score_weight` 中心偏好（访谈决定）。
- 发布频率：单体 `position_hz=25Hz` 节流；本实现每帧（~30Hz）发布（访谈决定）。
- 多帧顺序：已移植 `ball_order_stable_frames=4`、三色到达顺序、去重和 reset；目标索引/后退决策留给未来 `mission_node`。
- 相同部分：HSV 阈值、5×5 形态学、面积/半径/圆度/圆填充率、质量分、EMA(0.35) 平滑、无效坐标、`ball_order_min_x/max_x` 越界过滤均与单体一致。

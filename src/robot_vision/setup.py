import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'robot_vision'

setup(
    name=package_name,
    version='0.0.0',
    # 自动找到包内的 Python 模块（robot_vision/ 下的 .py）
    packages=find_packages(exclude=['test']),
    # data_files 决定哪些非代码文件会被装进 install/ 空间
    # 装错地方 / 漏登记，launch 就找不到文件（常见坑）
    data_files=[
        # ament 索引：让 ros2 能发现这个包（必需）
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # 包清单：必须装
        ('share/' + package_name, ['package.xml']),
        # launch 文件装到 share/robot_vision/launch/（launch 才找得到）
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # YAML 参数文件装到 share/robot_vision/config/
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cyy',
    maintainer_email='cyy@todo.todo',
    description='C70 camera node (ROS2 migration of c70_mode01.py)',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    # console_scripts：注册可执行命令，名字 = 节点名（ros2 run 用这个名字）
    #   左边是命令名，右边是 包.模块:函数
    entry_points={
        'console_scripts': [
            'camera_node = robot_vision.camera_node:main',
            'camera_probe = robot_vision.camera_probe:main',
            'vision_node = robot_vision.vision_node:main',
        ],
    },
)

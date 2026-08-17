# conftest.py — pytest 全局配置
# 职责:
#   1. driver fixture: 整个测试流程共享一个 Appium 连接
#      (一台手机同时只能有一个 UiAutomator2 会话, 各脚本不能各自连接)
#   2. gps_bg fixture: 后台持续注入GPS(复用cc-android的Player), 流程结束才停
#   3. RUN_UI 开关: 没设 RUN_UI=1 或无真机时, UI 用例全部跳过

import os
import time
import threading
import subprocess
import importlib.util
from pathlib import Path

import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options

APPIUM_URL = "http://127.0.0.1:4723"
CAPS = {
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Device",
    "appPackage": "com.shiye.cyclingai.ride",
    "noReset": True,
    "fullReset": False,
    "dontStopAppOnReset": True,
    "newCommandTimeout": 300,
    "adbExecTimeout": 60000,
    "autoGrantPermissions": True,
}

# ── 动态加载 cc-android.py (文件名带连字符, 不能直接import) ──
_CC = Path(__file__).parent / "cc-android.py"
_spec = importlib.util.spec_from_file_location("cc_android", _CC)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

GPS_GPX = r"C:\Users\Administrator\Desktop\梦工厂.gpx"  # 默认GPX路线


@pytest.fixture(scope="session")
def driver():
    """Appium 连接, 整个流程只连一次, 结束统一断开"""
    drv = webdriver.Remote(
        APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS)
    )
    yield drv
    try:
        drv.quit()
    except Exception:
        pass


@pytest.fixture
def gps_bg(driver):
    """GPS注入开关: 哪个用例要注入, 就在函数参数里加 gps_bg
    只对声明它的用例生效: 用例开始前启动线程, 用例结束立即停止
    目前只有导航用例声明它 → 导航时注入, 其他步骤不注入
    复用 cc-android 的 load_route/Player 播放逻辑, 注入到共享driver
    """
    stop = threading.Event()          # 停止信号

    def _inject_loop():
        cfg = cc.Config()
        cfg.gpx_file = GPS_GPX
        pts = cc.load_route(cfg.gpx_file)
        if len(pts) < 2:
            print("[GPS] 路线点太少, 注入跳过")
            return
        pl = cc.Player(pts, cfg)
        while not stop.is_set():      # 持续循环播放, 直到用例结束
            for lat, lon, ele, spd in pl.play():
                if stop.is_set():
                    return
                try:
                    driver.set_location(lat, lon, ele, speed=spd)
                except Exception as e:
                    print(f"[GPS] 注入失败: {e}")
                time.sleep(0.5)       # 500ms/2Hz, 匹配app缓冲池

    t = threading.Thread(target=_inject_loop, daemon=True)
    t.start()
    print(f"[GPS] 注入开启: {Path(GPS_GPX).stem}")
    yield
    stop.set()                        # 用例跑完才停
    t.join(timeout=3)
    print("[GPS] 注入停止")


def _has_device():
    """adb 是否连了可用真机"""
    try:
        out = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=5
        ).stdout
    except Exception:
        return False
    lines = out.strip().splitlines()[1:]  # 第一行是表头 "List of devices attached"
    for line in lines:
        # 有效行格式: 序列号 + 状态(device/offline/unauthorized)
        if line.strip() and "device" in line \
                and "offline" not in line and "unauthorized" not in line:
            return True
    return False


def pytest_collection_modifyitems(config, items):
    """收集完用例后: 没开RUN_UI或无真机 → 给 ui 标记用例统一加 skip
    RUN_UI 默认1(PyCharm直接Run就跑), 没真机时照样自动跳过防误跑"""
    run_ui = os.environ.get("RUN_UI", "1") == "1" and _has_device()
    if run_ui:
        return
    skip = pytest.mark.skip(reason="未设置RUN_UI=1或无真机, 跳过UI用例")
    for item in items:
        if "ui" in item.keywords:
            item.add_marker(skip)

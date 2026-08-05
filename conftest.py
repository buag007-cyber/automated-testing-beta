# conftest.py — pytest 全局配置
# 职责:
#   1. driver fixture: 整个测试流程共享一个 Appium 连接
#      (一台手机同时只能有一个 UiAutomator2 会话, 各脚本不能各自连接)
#   2. RUN_UI 开关: 没设 RUN_UI=1 或无真机时, UI 用例全部跳过

import os
import subprocess

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
    """收集完用例后: 没开RUN_UI或无真机 → 给 ui 标记用例统一加 skip"""
    run_ui = os.environ.get("RUN_UI") == "1" and _has_device()
    if run_ui:
        return
    skip = pytest.mark.skip(reason="未设置RUN_UI=1或无真机, 跳过UI用例")
    for item in items:
        if "ui" in item.keywords:
            item.add_marker(skip)

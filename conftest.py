# conftest.py — pytest 全局配置
# 规则:
#   默认只跑纯逻辑单测 (test_unit_gps.py), UI用例全部跳过
#   要跑 UI 用例: 设环境变量 RUN_UI=1 (且需真机在线)
#   CI 里永远不设 RUN_UI → UI 自动跳过, 只跑单测

import os
import subprocess

import pytest


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

# test_gps_inject.py — 流程第2步: GPS注入 (模拟骑行)
# 复用 cc-android.py 的 load_route/Player (不改原脚本), 通过共享 driver 注入坐标
# 注入固定时长, 让App处于"骑行中"状态, 供后续导航/地图下载步骤使用

import importlib.util
import time
from pathlib import Path

import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(600), pytest.mark.order(2)]  # 流程第2步: GPS注入

# ── 动态加载 cc-android.py (文件名带连字符, 不能直接 import) ──
_CC = Path(__file__).parent / "cc-android.py"
_spec = importlib.util.spec_from_file_location("cc_android", _CC)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

INJECT_SECONDS = 60  # 注入时长(秒), 想骑久一点改这个数


def test_gps_inject(driver):
    """注入GPX路线坐标, 模拟骑行 INJECT_SECONDS 秒"""
    cfg = cc.Config()
    pts = cc.load_route(cfg.gpx_file)
    print(f"[GPS] 路线{len(pts)}点, 注入{INJECT_SECONDS}s")

    # 播放器按500ms一步吐出坐标, 注入到共享driver
    pl = cc.Player(pts, cfg)
    t0 = time.time()
    n = 0
    for lat, lon, ele, spd in pl.play():
        driver.set_location(lat, lon, ele, speed=spd)
        n += 1
        time.sleep(0.5)
        if time.time() - t0 >= INJECT_SECONDS:
            break

    print(f"[GPS] 注入完成: {n}次坐标")
    assert n > 0, "没有注入任何坐标"

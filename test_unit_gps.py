# test_unit_gps.py — GPS注入脚本的纯逻辑单测 (CI里真正跑的就是这些)
# 测 cc-android.py 里不依赖手机的部分: 距离计算 / GPX解析 / 插值播放器
# 运行: pytest test_unit_gps.py -v

import importlib.util
from pathlib import Path

import pytest

# ── 动态加载 cc-android.py (文件名带连字符, 不能直接 import) ──
_CC = Path(__file__).parent / "cc-android.py"
_spec = importlib.util.spec_from_file_location("cc_android", _CC)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)


# ═══ dist_m: Haversine 距离公式 ═══

def test_dist_m_same_point():
    assert cc.dist_m(30.0, 120.0, 30.0, 120.0) == 0


def test_dist_m_one_degree_lat():
    # 纬度差0.01度 ≈ 1111.95米 (1度纬度≈111195米)
    d = cc.dist_m(0.0, 0.0, 0.01, 0.0)
    assert d == pytest.approx(1111.95, rel=0.001)


def test_dist_m_symmetric():
    # 距离公式应满足对称性: A→B == B→A
    a = cc.dist_m(30.0, 120.0, 31.0, 121.0)
    b = cc.dist_m(31.0, 121.0, 30.0, 120.0)
    assert a == pytest.approx(b)


# ═══ load_route: GPX 解析 ═══

def _write_gpx(tmp_path):
    """生成3点测试GPX, 返回文件路径"""
    p = tmp_path / "route.gpx"
    p.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="pytest">
  <trk><name>test</name><trkseg>
    <trkpt lat="30.000000" lon="120.000000"><ele>10</ele></trkpt>
    <trkpt lat="30.010000" lon="120.000000"><ele>20</ele></trkpt>
    <trkpt lat="30.020000" lon="120.000000"><ele>30</ele></trkpt>
  </trkseg></trk>
</gpx>''', encoding="utf-8")
    return str(p)


def test_load_route_points(tmp_path):
    pts = cc.load_route(_write_gpx(tmp_path))
    assert len(pts) == 3                                  # 3个路点
    assert pts[0] == (30.0, 120.0, 10.0)                  # 起点: 坐标+海拔
    assert pts[-1] == (30.02, 120.0, 30.0)                # 终点


def test_load_route_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        cc.load_route(str(tmp_path / "no.gpx"))


# ═══ Player: 分段插值播放器 ═══

def test_player_single_point_no_output():
    # 只有1个点 (<2) 直接不产出
    assert list(cc.Player([(0.0, 0.0, 0.0)], cc.Config()).play()) == []


def test_player_two_points():
    # 两点: 距离约111.19m, 速度36km/h(10m/s) → 约11秒走完, 子步约0.5s → 约22步
    pts = [(0.0, 0.0, 0.0), (0.0, 0.001, 100.0)]
    cfg = cc.Config()
    cfg.flat_speed_kmh = 36.0
    pl = cc.Player(pts, cfg)
    out = list(pl.play())

    assert 20 <= len(out) - 1 <= 24          # 子步数≈22
    assert out[0][:2] == (0.0, 0.0)          # 先吐起点

    # 最后一个点=终点 (插值 t=1, 海拔×altitude_scale=2)
    lat, lon, ele, spd = out[-1]
    assert lat == pytest.approx(0.0)
    assert lon == pytest.approx(0.001)
    assert ele == pytest.approx(200.0, rel=0.001)

    # 速度 = 36km/h ±5% 随机波动 → 9.6~10.4 m/s
    assert 9.5 <= spd <= 10.5

    # 累计统计
    assert pl.dist == pytest.approx(111.19, rel=0.05)    # 总里程≈111m
    assert pl.climb == pytest.approx(200.0, rel=0.05)    # 爬升=海拔差×缩放
    assert pl.elapsed == pytest.approx(111.19 / 10, rel=0.05)  # 总时长≈11s


def test_player_descend_no_climb():
    # 下坡段不累计爬升
    pts = [(0.0, 0.0, 100.0), (0.0, 0.001, 0.0)]
    pl = cc.Player(pts, cc.Config())
    list(pl.play())
    assert pl.climb == 0

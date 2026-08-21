# cc-android.py — Android GPS注入脚本 (Appium)
# 用法: python cc-android.py route.gpx [--keep]
# 模式: 分段子步插值, 固定500ms(2Hz)注入, Appium set_location(speed=)

import time, math, sys, random, socket, subprocess, threading
from dataclasses import dataclass
from pathlib import Path
from appium import webdriver
from appium.options.android import UiAutomator2Options
import gpxpy

# ── 配置 ──
@dataclass
class Config:
    appium_server: str = "http://127.0.0.1:4723"  # Appium地址
    app_pkg: str = "com.shiye.cyclingai.ride"      # 目标App包名
    gpx_file: str = r"C:\Users\Administrator\Desktop\6-26骑行.gpx"
    flat_speed_kmh: float = 25.0            # 平路速度(km/h)
    altitude_scale: float = 2.0             # 海拔缩放倍数
    rider_kg: float = 70.0                  # 体重(kg), 卡路里计算用
    loop: bool = True                       # 是否循环播放

# ── 工具函数 ──
def dist_m(lat1, lon1, lat2, lon2):        # Haversine公式, 返回两点距离(米)
    R = 6371000
    a = math.radians(lat2 - lat1)
    b = math.radians(lon2 - lon1)
    s = math.sin(a/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(b/2)**2
    return R * 2 * math.atan2(math.sqrt(s), math.sqrt(1 - s))

# ── 路线加载 ──
def load_route(path):                       # 解析GPX, 返回[(lat,lon,ele), ...]
    with open(path, 'r', encoding='utf-8') as f:
        g = gpxpy.parse(f)
    pts = [(p.latitude, p.longitude, p.elevation or 0.0)
           for t in g.tracks for s in t.segments for p in s.points]
    total = sum(dist_m(pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1])
                for i in range(1, len(pts)))
    print(f"  {len(pts)}点, {total/1000:.2f}km")
    return pts

# ── 播放器: 分段子步插值 ──
class Player:
    # 每段按seg_m/speed_ms等分成N步, 每步插值坐标, 主循环固定sleep(1.0)控频

    def __init__(self, pts, cfg):
        self.pts = pts
        self.cfg = cfg
        self.elapsed = 0.0                  # 已骑行时间(秒)
        self.dist = 0.0                     # 已骑行距离(米)
        self.climb = 0.0                    # 累计爬升(米)
        self.cal = 0.0                      # 累计卡路里
        self.idx = 0                        # 当前路点索引

    def play(self):                         # 生成器: yield (lat, lon, ele, speed_ms)
        pts = self.pts
        n = len(pts)
        cfg = self.cfg
        if n < 2:
            return

        yield pts[0][0], pts[0][1], pts[0][2], 0.5  # 先吐起点
        self.idx = 1

        for i in range(1, n):
            lat1, lon1, e1 = pts[i - 1]
            lat2, lon2, e2 = pts[i]
            seg_m = dist_m(lat1, lon1, lat2, lon2)

            speed_kmh = cfg.flat_speed_kmh * (0.96 + random.random() * 0.08)  # ±5%随机波动
            speed_ms = speed_kmh / 3.6

            seg_time = seg_m / speed_ms     # 走完这段需要几秒
            steps = max(1, round(seg_time / 0.5))  # 每子步≈0.5秒, 500ms频率
            step_m = seg_m / steps
            step_t = seg_time / steps       # ≈0.5秒

            for k in range(1, steps + 1):
                t = k / steps
                lat = round(lat1 + (lat2 - lat1) * t, 6)   # 纬度线性插值
                lon = round(lon1 + (lon2 - lon1) * t, 6)   # 经度线性插值
                ele = (e1 + (e2 - e1) * t) * cfg.altitude_scale

                self.elapsed += step_t
                self.dist += step_m
                if e2 > e1:
                    self.climb += (e2 - e1) * cfg.altitude_scale / steps

                met = 12.0 if speed_kmh > 15 else 6.0      # MET代谢当量
                self.cal += met * cfg.rider_kg * step_t / 3600

                if k == steps:
                    self.idx = i            # 走到路点了
                yield lat, lon, ele, speed_ms

# ── Appium注入器 ──
def port_ok(port=4723):                     # 检查Appium端口是否可用
    s = socket.socket()
    s.settimeout(2)
    try:
        code = s.connect_ex(('127.0.0.1', port))
        return code == 0 or code == 10035   # 10035=WSAEWOULDBLOCK(Windows非阻塞)
    finally:
        s.close()

class Injector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.drv = None
        self.cnt = 0

    def connect(self):                      # 连接Appium
        o = UiAutomator2Options()
        o.platform_name = "Android"
        o.device_name = "Android"
        o.no_reset = True
        o.app_package = self.cfg.app_pkg
        o.skip_server_installation = True
        o.set_capability("newCommandTimeout", 600)
        o.set_capability("appium:disableHiddenApiPolicy", True)
        self.drv = webdriver.Remote(command_executor=self.cfg.appium_server, options=o)
        print("[Appium] 已连接")

    def setup(self):                        # 开启mock定位
        subprocess.run(
            ['adb', 'shell', 'settings', 'put', 'secure', 'mock_location', '1'],
            capture_output=True, timeout=5
        )
        self.drv.update_settings({"locationProvider": "mock"})
        print("[GPS] mock就绪")

    def inject(self, lat, lon, alt, spd, extra=None):   # 注入单个GPS坐标
        if not self.drv:
            return
        try:
            self.drv.set_location(lat, lon, alt, speed=round(float(spd), 2))
        except Exception as e:
            print(f"[GPS] 失败: {e}")
            return
        self.cnt += 1
        # 每次注入输出标准状态行(供服务端/前端解析)
        if extra:
            print(f"|GPS|e={extra.get('elapsed',0):.1f}|d={extra.get('dist_m',0)/1000:.3f}"
                  f"|s={extra.get('speed_kmh',0):.1f}|c={extra.get('climb',0):.0f}"
                  f"|k={extra.get('cal',0):.0f}|i={extra.get('idx',0)}"
                  f"|t={extra.get('total',0)}|lat={lat:.6f}|lon={lon:.6f}"
                  f"|ele={alt:.1f}|spd={spd:.2f}|l={extra.get('lap',0)}|")
        elif self.cnt <= 3 or self.cnt % 50 == 0:
            print(f"[GPS #{self.cnt}] {lat:.5f},{lon:.5f} spd={spd:.1f}m/s")

# ── 主函数 ──
def main():
    cfg = Config()

    # 解析参数: 手动传入的GPX默认删除(--keep保留), 默认GPX不删
    args = sys.argv[1:]
    delete_after = False
    if "--keep" in args:
        args.remove("--keep")
    else:
        delete_after = len(args) > 0 and not args[0].startswith("--")

    if args:
        cfg.gpx_file = args[0]
    gpx_path = Path(cfg.gpx_file)
    if not gpx_path.exists():
        print(f"GPX不存在: {cfg.gpx_file}")
        sys.exit(1)

    # 加载路线
    print(f"cc-android GPS注入 | {cfg.flat_speed_kmh}km/h")
    pts = load_route(cfg.gpx_file)
    print(f"路线: {gpx_path.stem}")

    # 连接Appium
    if not port_ok():
        print("Appium未启动")
        sys.exit(1)
    inj = Injector(cfg)
    inj.connect()
    time.sleep(3)

    try:
        inj.setup()
        p0 = pts[0]

        # 后台预热: 持续注入起点, 避免app冷启动无信号
        stop = threading.Event()
        def bg():
            while not stop.is_set():
                inj.inject(p0[0], p0[1], p0[2], 0.5)
                time.sleep(1)
        t = threading.Thread(target=bg, daemon=True)
        t.start()
        print("[GPS] 预热, 打开app→运动→按Enter")
        if sys.stdin.isatty():               # 交互模式才等用户输入
            input(">>> ")
        else:
            time.sleep(3)                    # 非交互模式等3秒自动继续
        stop.set()
        t.join(timeout=3)

        # 锁定mock provider + 稳定注入
        inj.drv.update_settings({"locationProvider": "mock"})
        for _ in range(3):
            inj.inject(p0[0], p0[1], p0[2], 0.5)
            time.sleep(0.5)                  # 500ms锁定
        inj.inject(p0[0], p0[1], p0[2], 2.0)
        time.sleep(0.5)

        # 主循环: 逐圈播放
        lap = 0
        while cfg.loop:
            lap += 1
            pl = Player(pts, cfg)
            print(f"\n第{lap}圈 | {len(pts)}点")
            print(f"  {'时间':>8} {'里程':>7} {'速度':>5} {'爬升':>5} {'卡路里':>6} {'路点':>5}")
            tp = time.time()

            for lat, lon, ele, spd in pl.play():
                time.sleep(0.5)             # 固定500ms(2Hz)
                inj.inject(lat, lon, ele, spd, {
                    "elapsed": pl.elapsed, "dist_m": pl.dist,
                    "speed_kmh": cfg.flat_speed_kmh,
                    "climb": pl.climb, "cal": pl.cal,
                    "idx": pl.idx, "total": len(pts), "lap": lap
                })

                if time.time() - tp >= 5:   # 每5秒打印状态
                    tp = time.time()
                    av = (pl.dist / 1000) / (pl.elapsed / 3600) if pl.elapsed > 0 else 0
                    print(f"  {int(pl.elapsed//3600):02d}:{int(pl.elapsed%3600//60):02d}:{int(pl.elapsed%60):02d}"
                          f"  {pl.dist/1000:>6.2f}km  {av:>4.0f}kmh"
                          f"  {pl.climb:>4.0f}m  {pl.cal:>5.0f}kcal"
                          f"  {pl.idx:>4}/{len(pts)}")

            av = (pl.dist / 1000) / (pl.elapsed / 3600) if pl.elapsed > 0 else 0
            print(f"\n完成! {pl.dist/1000:.2f}km | {av:.1f}km/h | {pl.cal:.0f}kcal")

    finally:
        if inj.drv:
            inj.drv.quit()
            print("[Appium] 断开")
        if delete_after and gpx_path and gpx_path.exists():
            gpx_path.unlink()
            print(f"[清理] 已删除 {gpx_path.name}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] 中断")
    except Exception as e:
        print(e)

# cc-android.py — Android GPS注入脚本 (Appium)
# 用法: python cc-android.py route.gpx [--keep] | 分段插值 500ms注入(2Hz)
# 通用: 不依赖目标App包名(设备级mock注入), 想测哪个App自己打开哪个
# 口径: 起点海拔发原始值(与旧版一致, App据此起点跳变计一次爬升, 去噪后才"有数据");
#       爬升c=按放大海拔正增量累计但不含起点跳变(数值与旧版相同)
#       航向=路段方位角, mobile:setGeolocation注入bearing, 状态行输出h=

import time, math, sys, random, socket, subprocess, threading
from dataclasses import dataclass
from pathlib import Path

# ├─ 自动加载项目 .venv 的包: 让"python xxx.py"在任何解释器下都能跑 ──
_script_dir = Path(__file__).resolve().parent
_venv_sp = str(_script_dir / ".venv" / "Lib" / "site-packages")
if _venv_sp in sys.path:                    # 已经在路径里就摘掉, 再插到最前
    sys.path.remove(_venv_sp)
if Path(_venv_sp).is_dir():
    sys.path.insert(0, _venv_sp)

from appium import webdriver
from appium.options.android import UiAutomator2Options
import gpxpy

# ── 配置 ──
@dataclass
class Config:
    appium_server: str = "http://127.0.0.1:4723"  # Appium地址
    gpx_file: str = r"C:\Users\Administrator\Desktop\6-26骑行.gpx"
    flat_speed_kmh: float = 25.0            # 平路速度(km/h)
    altitude_scale: float = 2.0             # 海拔放大倍数(起伏太小App不累计爬升)
    rider_kg: float = 70.0                  # 体重(kg), 卡路里计算用
    loop: bool = True                       # 是否循环播放

# ── 工具函数 ──
def dist_m(lat1, lon1, lat2, lon2):         # 两点球面距离(米)
    R = 6371000
    a = math.radians(lat2 - lat1)
    b = math.radians(lon2 - lon1)
    s = math.sin(a/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(b/2)**2
    return R * 2 * math.atan2(math.sqrt(s), math.sqrt(1 - s))

def bearing_deg(lat1, lon1, lat2, lon2):    # A→B初始航向(0=北, 顺时针0-360)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

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

# ── 播放器: 逐段插值, 每次yield一个注入点 (lat,lon,ele,spd) ──
class Player:
    def __init__(self, pts, cfg):
        self.pts = pts
        self.cfg = cfg
        self.elapsed = 0.0                  # 已骑行时间(秒)
        self.dist = 0.0                     # 已骑行距离(米)
        self.climb = 0.0                    # 累计爬升(米, 按注入海拔正增量)
        self.cal = 0.0                      # 累计卡路里
        self.idx = 0                        # 当前路点索引
        self.heading = 0.0                  # 当前航向(度)
        self.lap = 0                        # 第几圈(状态行用)
        self._last_ele = 0.0                # 上一注入海拔(算爬升用)

    def play(self):                         # 生成器, 每次yield一个注入点
        pts, cfg, n = self.pts, self.cfg, len(self.pts)
        if n < 2:
            return
        # 起点: 海拔发原始值(与旧版一致, App按起点跳变计一次爬升, 保证去噪后有数据)
        #       计数器基线用放大值 → c=不含这个跳变, 数值与旧版相同
        e0 = pts[0][2]
        self._last_ele = pts[0][2] * cfg.altitude_scale
        self.heading = bearing_deg(pts[0][0], pts[0][1], pts[1][0], pts[1][1])
        yield pts[0][0], pts[0][1], e0, 0.5
        for i in range(1, n):
            lat1, lon1, e1 = pts[i-1]
            lat2, lon2, e2 = pts[i]
            seg_m = dist_m(lat1, lon1, lat2, lon2)
            if seg_m < 0.5:                 # 太近的路点跳过, 防原地踏步
                self.idx = i
                continue
            self.heading = bearing_deg(lat1, lon1, lat2, lon2)  # 本段航向恒定
            spd = cfg.flat_speed_kmh * (0.96 + random.random() * 0.08) / 3.6  # ±4%波动(m/s)
            seg_t = seg_m / spd
            steps = max(1, round(seg_t / 0.5))  # 每子步≈0.5秒
            for k in range(1, steps + 1):
                t = k / steps
                lat = round(lat1 + (lat2 - lat1) * t, 6)
                lon = round(lon1 + (lon2 - lon1) * t, 6)
                ele = (e1 + (e2 - e1) * t) * cfg.altitude_scale
                dy = ele - self._last_ele   # 只有上坡增量才计入爬升
                if dy > 0:
                    self.climb += dy
                self._last_ele = ele
                self.elapsed += seg_t / steps
                self.dist += seg_m / steps
                met = 12.0 if spd * 3.6 > 15 else 6.0   # MET代谢当量
                self.cal += met * cfg.rider_kg * (seg_t / steps) / 3600
                if k == steps:
                    self.idx = i
                yield lat, lon, ele, spd

# ── Appium注入器 ──
def port_ok(port=4723):                     # Appium端口是否监听
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
        self.errs = 0                       # 连续失败次数(限频提示用)

    def connect(self):                      # 连接Appium
        o = UiAutomator2Options()
        o.platform_name = "Android"
        o.device_name = "Android"
        o.no_reset = True
        o.skip_server_installation = True    # 不重装uiautomator2服务, 连接更快
        # 不指定appPackage: 注入是设备级mock, 不依赖/不启动任何目标App,
        # 想测哪个App就自己打开哪个(实测裸会话mobile:setGeolocation三provider全更新)
        o.set_capability("newCommandTimeout", 600)
        o.set_capability("appium:disableHiddenApiPolicy", True)
        self.drv = webdriver.Remote(command_executor=self.cfg.appium_server, options=o)
        print("[Appium] 已连接")

    def setup(self):                        # 开mock定位开关并锁mock源
        subprocess.run(
            ['adb', 'shell', 'settings', 'put', 'secure', 'mock_location', '1'],
            capture_output=True, timeout=5
        )
        self.drv.update_settings({"locationProvider": "mock"})
        print("[GPS] mock就绪")

    def inject(self, lat, lon, alt, spd, brg=0.0, pl=None):    # 注入一点(带航向)
        if not self.drv:
            return
        try:
            # mobile:setGeolocation真机通道, 支持speed/bearing(0-360)
            self.drv.execute_script("mobile: setGeolocation", {
                "latitude": lat, "longitude": lon, "altitude": round(alt, 1),
                "speed": round(float(spd), 2), "bearing": round(float(brg), 1)})
            self.errs = 0
        except Exception:
            try:                            # 兜底老接口: 无航向但保速度
                self.drv.set_location(lat, lon, alt, speed=round(float(spd), 2))
                self.errs = 0
            except Exception as e:
                self.errs += 1
                if self.errs <= 3 or self.errs % 50 == 0:   # 失败提示限频
                    print(f"[GPS] 注入失败: {e}")
                return
        self.cnt += 1
        # 标准状态行(供服务端/前端解析), h=航向(度); 骑行中每点打, 预热只偶尔打
        if pl:
            print(f"|GPS|e={pl.elapsed:.1f}|d={pl.dist/1000:.3f}|s={spd*3.6:.1f}"
                  f"|c={pl.climb:.0f}|k={pl.cal:.0f}|i={pl.idx}|t={len(pl.pts)}"
                  f"|lat={lat:.6f}|lon={lon:.6f}|ele={alt:.1f}|spd={spd:.2f}"
                  f"|h={brg:.1f}|l={pl.lap}|")
        elif self.cnt <= 3 or self.cnt % 50 == 0:
            print(f"[GPS #{self.cnt}] {lat:.5f},{lon:.5f} spd={spd:.1f}m/s 航向{brg:.0f}°")

# ── 主函数 ──
def main():
    cfg = Config()
    # 解析参数: 手动传入GPX默认用完删(--keep保留), 默认GPX不删
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

    print(f"cc-android GPS注入 | {cfg.flat_speed_kmh}km/h")
    pts = load_route(cfg.gpx_file)
    print(f"路线: {gpx_path.stem}")
    if not port_ok():
        print("Appium未启动")
        sys.exit(1)
    inj = Injector(cfg)
    inj.connect()
    time.sleep(3)

    try:
        inj.setup()
        p0 = pts[0]
        # 预热: 后台持续注入起点, 等App冷启动有信号
        stop = threading.Event()
        def bg():
            while not stop.is_set():
                inj.inject(p0[0], p0[1], p0[2], 0.5)
                time.sleep(1)
        t = threading.Thread(target=bg, daemon=True)
        t.start()
        print("[GPS] 预热, 打开要测的App进入骑行界面→按Enter")
        if sys.stdin.isatty():              # 交互模式等用户, 非交互等3秒
            input(">>> ")
        else:
            time.sleep(3)
        stop.set()
        t.join(timeout=3)
        # 连发起点锁定mock, 再以起步速度开出
        for _ in range(3):
            inj.inject(p0[0], p0[1], p0[2], 0.5)
            time.sleep(0.5)
        inj.inject(p0[0], p0[1], p0[2], 2.0)

        # 主循环: 逐圈播放
        lap = 0
        while cfg.loop:
            lap += 1
            pl = Player(pts, cfg)
            pl.lap = lap                    # 供状态行l=字段
            print(f"\n第{lap}圈 | {len(pts)}点")
            print(f"  {'时间':>8} {'里程':>7} {'均速':>5} {'爬升':>5} {'卡路里':>6} {'航向':>6} {'路点':>5}")
            tp = time.time()
            for lat, lon, ele, spd in pl.play():
                time.sleep(0.5)             # 固定500ms(2Hz)
                inj.inject(lat, lon, ele, spd, pl.heading, pl)
                if time.time() - tp >= 5:   # 每5秒打印状态
                    tp = time.time()
                    av = (pl.dist / 1000) / (pl.elapsed / 3600) if pl.elapsed > 0 else 0
                    print(f"  {int(pl.elapsed//3600):02d}:{int(pl.elapsed%3600//60):02d}:{int(pl.elapsed%60):02d}"
                          f"  {pl.dist/1000:>6.2f}km  {av:>4.0f}kmh"
                          f"  {pl.climb:>4.0f}m  {pl.cal:>5.0f}kcal"
                          f"  {pl.heading:>5.0f}°  {pl.idx:>4}/{len(pts)}")
            av = (pl.dist / 1000) / (pl.elapsed / 3600) if pl.elapsed > 0 else 0
            print(f"\n完成! {pl.dist/1000:.2f}km | {av:.1f}km/h | 爬升{pl.climb:.0f}m | {pl.cal:.0f}kcal")
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

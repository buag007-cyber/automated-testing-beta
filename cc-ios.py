# cc-ios.py — iOS GPS注入脚本 (pymobiledevice3)
# 用法: python cc-ios.py route.gpx [--speed 25] [--no-loop] [--keep]
# 模式: 分段子步插值, 固定500ms注入, 随机速度模拟骑行
#       iOS Core Location自行计算速度, 只注入经纬度

import time, math, sys, asyncio, random
from dataclasses import dataclass
from pathlib import Path

# ├─ 自动加载项目虚拟环境的包 ──
_script_dir = Path(__file__).resolve().parent
_venv_sp = _script_dir / ".venv" / "Lib" / "site-packages"
_py39_sp = Path(r"C:\Users\Administrator\AppData\Local\Programs\Python\Python39\Lib\site-packages")
for _p in [_venv_sp, _py39_sp]:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── 依赖检查 ──
try:
    import gpxpy
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.simulate_location import DtSimulateLocation
except ImportError:
    print("[ERROR] 请先安装: pip install gpxpy pymobiledevice3")
    sys.exit(1)

# ── 配置 ──
@dataclass
class Config:
    gpx_file: str = r"C:\Users\Administrator\Desktop\SHANHAILIANCHENG.gpx"  # GPX路线文件
    flat_speed_kmh: float = 25.0            # 平路速度(km/h)
    altitude_scale: float = 1.0             # 海拔缩放
    loop: bool = True                       # 是否循环

def dist_m(lat1, lon1, lat2, lon2):         # 两点距离(米)
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def load_route(path):                       # 加载GPX → [(lat,lon,ele), ...]
    with open(path, encoding='utf-8') as f:
        g = gpxpy.parse(f)
    pts = [(p.latitude, p.longitude, p.elevation or 0.0)
           for t in g.tracks for s in t.segments for p in s.points]
    total = sum(dist_m(pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1]) for i in range(1, len(pts)))
    print(f"  {len(pts)}点, {total/1000:.2f}km")
    return pts

# ── 播放器 ──
class Player:
    def __init__(self, pts, cfg):
        self.pts = pts
        self.cfg = cfg
        self.elapsed = 0.0                  # 已骑行时间(秒)
        self.dist = 0.0                     # 已骑行距离(米)
        self.climb = 0.0                    # 累计爬升(米)

    def play(self):                         # yield (lat, lon, ele, speed_ms)
        for i in range(1, len(self.pts)):
            lat1, lon1, e1 = self.pts[i-1]
            lat2, lon2, e2 = self.pts[i]
            seg_m = dist_m(lat1, lon1, lat2, lon2)
            if seg_m < 0.5:
                continue                    # 跳过过近的点

            # 随机速度波动, 模拟骑行节奏
            speed_kmh = self.cfg.flat_speed_kmh * (0.96 + random.random() * 0.08)
            speed_ms = speed_kmh / 3.6

            steps = max(1, round(seg_m / speed_ms / 0.5))
            step_m = seg_m / steps

            for k in range(1, steps + 1):
                t = k / steps
                lat = round(lat1 + (lat2 - lat1) * t, 6)
                lon = round(lon1 + (lon2 - lon1) * t, 6)
                ele = (e1 + (e2 - e1) * t) * self.cfg.altitude_scale

                self.elapsed += 0.5
                self.dist += step_m
                if e2 > e1:
                    self.climb += (e2 - e1) * self.cfg.altitude_scale / steps
                yield lat, lon, ele, speed_ms

# ── iOS注入器 ──
class Injector:
    def __init__(self, cfg):
        self.cfg = cfg
        self._lockdown = None
        self._service = None
        self._dvt_ctx = None
        self._loc_ctx = None
        self._is_legacy = True
        self._cnt = 0
        self._start = None

    async def connect(self):
        print("[iOS] 连接iPhone...")
        try:
            self._lockdown = await create_using_usbmux()
            ver = self._lockdown.product_version
            major = int(ver.split('.')[0])
        except Exception as e:
            print(f"[ERROR] 连接失败: {e}"); sys.exit(1)

        if major < 17:                      # iOS<17
            self._is_legacy = True
            self._service = DtSimulateLocation(self._lockdown)
            print("[iOS] DtSimulateLocation (iOS<17)")
        else:                               # iOS>=17 DVT
            self._is_legacy = False
            try:
                from pymobiledevice3.remote.userspace_tunnel import establish_userspace_rsd
                from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
                from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
                rsd = await establish_userspace_rsd(serial=self._lockdown.identifier)
                self._dvt_ctx = DvtProvider(rsd)
                dvt = await self._dvt_ctx.__aenter__()
                self._loc_ctx = LocationSimulation(dvt)
                self._service = await self._loc_ctx.__aenter__()
                print("[iOS] DVT LocationSimulation (iOS>=17)")
            except Exception as e:
                print(f"[ERROR] DVT连接失败: {e}"); sys.exit(1)

    async def inject(self, lat, lon, ele):  # 注入坐标
        if not self._service:
            return
        try:
            await self._service.set(latitude=float(lat), longitude=float(lon))
            self._cnt += 1
            if self._start is None:
                self._start = time.time()
        except Exception as e:
            print(f"[GPS] 失败: {e}")

    async def stop(self):
        try:
            if self._service:
                await self._service.clear()
            if not self._is_legacy:
                if self._loc_ctx:
                    await self._loc_ctx.__aexit__(None, None, None)
                if self._dvt_ctx:
                    await self._dvt_ctx.__aexit__(None, None, None)
        except Exception:
            pass

    @property
    def elapsed(self):
        return time.time() - self._start if self._start else 0

# ── 主函数 ──
async def main():
    cfg = Config()

    # 解析参数: 传了GPX则覆盖默认, 默认不删(--keep保留)
    args = sys.argv[1:]
    delete_after = False
    if "--keep" in args:
        args.remove("--keep")
    else:
        delete_after = len(args) > 0 and not args[0].startswith("--")

    if args and not args[0].startswith("--"):
        cfg.gpx_file = args[0]
        args = args[1:]

    i = 0
    while i < len(args):
        if args[i] == '--speed' and i+1 < len(args):
            cfg.flat_speed_kmh = float(args[i+1]); i += 2
        elif args[i] == '--no-loop':
            cfg.loop = False; i += 1
        else:
            i += 1

    gpx_path = Path(cfg.gpx_file)
    print(f"cc-ios GPS注入 | {cfg.flat_speed_kmh}km/h")
    pts = load_route(cfg.gpx_file)
    if len(pts) < 2:
        print("路线点数不足"); sys.exit(1)
    print(f"路线: {gpx_path.stem}")

    print(f"\n配置: {cfg.flat_speed_kmh}km/h, 循环={'是' if cfg.loop else '否'}")
    print("打开App→运动→按Enter")
    input(">>> ")

    inj = Injector(cfg)
    await inj.connect()

    lap = 0
    try:
        while cfg.loop:
            lap += 1
            pl = Player(pts, cfg)
            print(f"\n第{lap}圈 | {len(pts)}点")
            print(f"  {'时间':>8} {'里程':>7} {'速度':>5} {'爬升':>5} {'路点':>5}")

            for lat, lon, ele, spd in pl.play():
                await inj.inject(lat, lon, ele)
                await asyncio.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[!] 中断")
    finally:
        await inj.stop()
        if pl:
            print(f"\n完成! {pl.dist/1000:.2f}km | {pl.climb:.0f}m | {pl.elapsed:.0f}s")
        if delete_after and gpx_path.exists():
            gpx_path.unlink()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)

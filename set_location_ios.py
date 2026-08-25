# set_location_ios.py — iOS 单次定位注入 (固定坐标)
# 用法: python set_location_ios.py  (PyCharm直接跑, iPhone USB连电脑)
# 场景: 把iPhone定位改到指定坐标, 注入一次生效(如测试固定地点的业务)
# 原理: pymobiledevice3连iPhone → iOS<17用DtSimulateLocation / iOS>=17用DVT
#       → set经纬度 → 断开 (iOS自己算速度, 只注入经纬度)
# 注意: 和安卓版set_location.py结构一致(配置/主函数/入口), 注入方式不同

import sys
import asyncio
from pathlib import Path

# ── 自动加载项目虚拟环境的包 (和cc-ios.py一样, 不依赖系统python) ──
_script_dir = Path(__file__).resolve().parent
_venv_sp = _script_dir / ".venv" / "Lib" / "site-packages"
_py39_sp = Path(r"C:\Users\Administrator\AppData\Local\Programs\Python\Python39\Lib\site-packages")
for _p in [_venv_sp, _py39_sp]:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── 依赖检查 ──
try:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.simulate_location import DtSimulateLocation
except ImportError:
    print("[ERROR] 请先安装: pip install pymobiledevice3")
    sys.exit(1)

# ── 配置: 想改到哪就改这2行 (iOS不注入海拔和速度, 系统自己算) ──
LAT = 22.5244100      # 目标纬度 (深圳)
LON = 113.8961100     # 目标经度


# ── iOS注入器 (从cc-ios.py精简: 只保留连接/注入/断开) ──
class Injector:
    def __init__(self):
        self._lockdown = None     # iPhone连接
        self._service = None      # 注入服务(DtSimulateLocation或DVT)
        self._dvt_ctx = None      # DVT上下文(iOS>=17)
        self._loc_ctx = None      # 定位模拟上下文(iOS>=17)
        self._is_legacy = True    # True=旧方案iOS<17
        self._cnt = 0             # 注入次数

    async def connect(self):
        """连接iPhone, 按系统版本选注入方案"""
        print("[iOS] 连接iPhone...")
        try:
            self._lockdown = await create_using_usbmux()
            ver = self._lockdown.product_version
            major = int(ver.split('.')[0])
        except Exception as e:
            print(f"[ERROR] 连接失败: {e}")
            sys.exit(1)

        if major < 17:                          # iOS<17 老方案
            self._is_legacy = True
            self._service = DtSimulateLocation(self._lockdown)
            print("[iOS] DtSimulateLocation (iOS<17)")
        else:                                   # iOS>=17 DVT方案
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
                print(f"[ERROR] DVT连接失败: {e}")
                sys.exit(1)

    async def inject(self, lat, lon):
        """注入单个坐标 (iOS只传经纬度, 海拔速度系统自己算)"""
        if not self._service:
            return
        try:
            await self._service.set(latitude=float(lat), longitude=float(lon))
            self._cnt += 1
        except Exception as e:
            print(f"[GPS] 失败: {e}")

    async def stop(self):
        """断开: 清除模拟定位 + 释放连接"""
        try:
            if self._service:
                await self._service.clear()     # 清除模拟定位, 恢复真实位置
            if not self._is_legacy:             # iOS>=17 关DVT上下文
                if self._loc_ctx:
                    await self._loc_ctx.__aexit__(None, None, None)
                if self._dvt_ctx:
                    await self._dvt_ctx.__aexit__(None, None, None)
        except Exception:
            pass


# ── 主函数 (和安卓版4步对应: 连接→注入→断开) ──
async def main():
    inj = Injector()
    await inj.connect()                         # 1. 连接iPhone

    try:
        # 2. 注入坐标, 连续3次确保App定位更新生效
        for i in range(3):
            await inj.inject(LAT, LON)
            print(f"[{i+1}/3] 注入: {LAT}, {LON}")
            await asyncio.sleep(1)              # iOS用asyncio.sleep, 禁time.sleep

        print(f"\n[OK] 定位已修改, 打开地图App应显示在: {LAT}, {LON}")
    finally:
        await inj.stop()                        # 3. 断开(清除定位+释放连接)
        print("[iOS] 已断开")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] 中断")
    except Exception as e:
        print(e)

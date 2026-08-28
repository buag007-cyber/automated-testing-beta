# set_location.py — 单次定位注入 (固定坐标)
# 用法: python set_location.py  (PyCharm直接跑, 需Appium在跑+手机连着)
# 场景: 把手机定位改到指定坐标, 注入一次生效(如测试固定地点的业务)
# 原理: 开mock开关 → 连Appium(不需要appPackage, 只注入位置) → set_location() → 断开

import time
import subprocess
from appium import webdriver
from appium.options.android import UiAutomator2Options

# ── 配置: 想改到哪就改这4行 ──
LAT = 52.267763      # 目标纬度 (荷兰Kasteel Keukenhof)
LON = 4.540190       # 目标经度
ELE = 20.2           # 海拔(米)
SPEED = 0.0          # 速度(m/s), 静止就是0

APPIUM_URL = "http://127.0.0.1:4723"
# 只注入位置不操作app, 所以不需要appPackage
CAPS = {
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Device",
    "noReset": True,
    "newCommandTimeout": 300,
}


def main():
    # 1. 打开系统mock定位开关 (Appium自动装的io.appium.settings需要它)
    subprocess.run(["adb", "shell", "settings", "put", "secure", "mock_location", "1"])

    # 2. 连接Appium (无appPackage的空session, 实测可用)
    driver = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))
    try:
        # 3. 指定用mock定位源
        driver.update_settings({"locationProvider": "mock"})

        # 4. 注入坐标, 连续3次确保App定位更新生效
        for i in range(3):
            driver.set_location(LAT, LON, ELE, speed=SPEED)
            print(f"[{i+1}/3] 注入: {LAT}, {LON} 海拔{ELE}m 速度{SPEED}m/s")
            time.sleep(1)

        print(f"\n[OK] 定位已修改, 打开地图App应显示在: {LAT}, {LON}")
    finally:
        driver.quit()
        print("[Appium] 已断开")


if __name__ == "__main__":
    main()

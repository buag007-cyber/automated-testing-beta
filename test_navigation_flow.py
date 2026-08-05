# test_navigation_flow.py — 骑迹GPS 地图导航流程
# 用法: python test_navigation_flow.py（需先启动 Appium Server）
#
# 流程（按 app元素.txt 导航流程）:
#   运动界面 → 地图区域 → 地图长按区域 → 随机长按3s → 发送导航 → 地图导航开始
# 长按用 uiautomator2 原生手势 mobile: longClickGesture（TouchAction 已在 5.x 移除）

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time
import random
import subprocess
import os

import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(600)]  # UI用例: 无真机跳过, 10分钟超时防卡死

# ── 日志（桌面/自动化测试log）──
LOG_DIR = r"C:\Users\Administrator\Desktop\自动化测试log"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "navigation.log")
_logcat_proc = None

# ── 连接 ──
APPIUM_URL = "http://127.0.0.1:4723"
PKG = "com.shiye.cyclingai.ride"
CAPS = {
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Device",
    "appPackage": PKG,
    "noReset": True,
    "fullReset": False,
    "dontStopAppOnReset": True,
    "newCommandTimeout": 300,
    "adbExecTimeout": 60000,
    "autoGrantPermissions": True,
}

# ── 元素（全部来自 app元素.txt 导航流程）──
ID = "com.shiye.cyclingai.ride:id"

SPORT_VIEW   = f"{ID}/mainLlMap"                    # 运动界面(底部导航)
MAP_AREA     = f"{ID}/mapRoadNavigationIv"          # 地图区域(与地图路书同ID)
MAP_LONG_PRESS = (AppiumBy.ANDROID_UIAUTOMATOR,
                  'new UiSelector().className("android.view.ViewGroup").instance(0)')  # 地图长按区域
SEND_NAV     = f"{ID}/itemAlternativeRoutesIvGo"    # 发送导航
NAV_START    = (AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().className("android.widget.ImageView").instance(0)')  # 地图导航开始


def wait_click(driver, locator, timeout=10):
    """等待元素可点击后点击（页面重绘导致元素失效时自动重试）"""
    WebDriverWait(driver, timeout,
                  ignored_exceptions=(StaleElementReferenceException,)).until(
        EC.element_to_be_clickable(locator)).click()

def try_click(driver, locator, timeout=5):
    """尝试点击, 找不到返回False, 不中断流程"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)).click()
        return True
    except Exception:
        return False

def long_press(driver, x, y, ms=3000):
    """uiautomator2原生长按手势(坐标)"""
    driver.execute_script("mobile: longClickGesture",
                          {"x": x, "y": y, "duration": ms})

def random_point_in(el):
    """元素rect内随机取点(留15%边距防点到边缘)"""
    r = el.rect
    x = r["x"] + random.randint(int(r["width"] * 0.15), int(r["width"] * 0.85))
    y = r["y"] + random.randint(int(r["height"] * 0.15), int(r["height"] * 0.85))
    return x, y

# ── logcat 后台抓取 ──

def start_logcat():
    """后台抓 logcat, 写到桌面/自动化测试log/navigation.log"""
    global _logcat_proc
    cmd = ["adb", "logcat", "-v", "time", "-s", "ActivityManager:I", "AndroidRuntime:E",
           "Appium_*:I", "*:S"]
    try:
        _logcat_proc = subprocess.Popen(cmd, stdout=open(LOG_FILE, "w", encoding="utf-8", errors="ignore"))
    except Exception as e:
        print(f"[日志] logcat 启动失败: {e}")

def stop_logcat():
    global _logcat_proc
    if _logcat_proc:
        _logcat_proc.terminate()
        _logcat_proc = None
        print(f"[日志] 已保存: {LOG_FILE}")


def test_navigation_flow():
    """地图导航 完整流程"""
    driver = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))

    try:
        # 强制重启App→主界面, 避免上次停在子页面找不到底部导航
        driver.terminate_app(PKG)
        driver.activate_app(PKG)
        time.sleep(3)

        start_logcat()

        # ═══ 导航流程 ═══
        wait_click(driver, (AppiumBy.ID, SPORT_VIEW))
        print("[1] 点击运动界面")
        time.sleep(2)

        wait_click(driver, (AppiumBy.ID, MAP_AREA))
        print("[2] 点击地图区域")
        time.sleep(2)

        el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(MAP_LONG_PRESS))
        r = el.rect
        print(f"[3] 点击地图长按区域 (rect: {r['x']},{r['y']} {r['width']}x{r['height']})")

        # 随机长按, 没弹出发送导航就换位置重试(最多3次)
        sent = False
        for i in range(3):
            x, y = random_point_in(el)
            print(f"[4.{i+1}] 随机长按 ({x},{y}) 3秒")
            long_press(driver, x, y, 3000)
            time.sleep(2)
            if try_click(driver, (AppiumBy.ID, SEND_NAV), timeout=5):
                print("[5] ✅ 点击发送导航")
                sent = True
                break
            print("    发送导航未出现, 换个位置重试")

        if not sent:
            raise TimeoutError("长按3次均未弹出发送导航, 请检查页面状态")

        # 地图导航开始
        wait_click(driver, NAV_START)
        print("[6] ✅ 点击地图导航开始")

        print("\n🎉 地图导航流程完成")
    finally:
        stop_logcat()
        driver.quit()


if __name__ == "__main__":
    test_navigation_flow()

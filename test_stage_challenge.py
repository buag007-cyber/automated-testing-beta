# test_stage_challenge.py — 骑迹GPS 赛段挑战 创建→删除 完整流程
# 用法: python test_stage_challenge.py（需先启动 Appium Server）
#
# 流程（按 app元素.txt 赛段挑战自动化）：
#   挑战训练 → 赛段挑战创建 → 赛段选择 → 第一条 → 速度要求 →
#   下滑 → 保存 → 运动记录返回 → 赛段挑战返回 →
#   第一个赛段 → 下滑 → 删除赛段

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import subprocess
import os

import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(600), pytest.mark.order(5)]  # 流程第5步: 赛段挑战

# ── 日志（桌面/自动化测试log）──
LOG_DIR = r"C:\Users\Administrator\Desktop\自动化测试log"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "stage_challenge.log")
_logcat_proc = None

# ── 连接 ──
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

# ── 元素（全部来自 app元素.txt）──
ID = "com.shiye.cyclingai.ride:id"

MAIN_TRAINING  = f"{ID}/mainIvTraining"                     # 挑战训练
STAGE_CREATE   = (AppiumBy.ANDROID_UIAUTOMATOR,
    'new UiSelector().className("android.widget.FrameLayout").instance(7)')  # 赛段挑战创建
STAGE_SELECT   = f"{ID}/mapChallengeStageIv"                # 赛段选择
STAGE_FIRST    = (AppiumBy.ANDROID_UIAUTOMATOR,
    'new UiSelector().resourceId("com.shiye.cyclingai.ride:id/itemTrainingPlanBeginsBtn").instance(0)')  # 第一条
STAGE_AVG_SPEED = f"{ID}/challengeDetailsCbAvgSpeed"        # 赛段速度要求
STAGE_SAVE     = f"{ID}/challengeDetailsBtnSave"            # 赛段保存
BACK           = f"{ID}/ib_back"                            # 返回(运动记录/赛段挑战共用)
FIRST_STAGE    = f"{ID}/itemTrainingPlanLayout"             # 第一个赛段
STAGE_DELETE   = f"{ID}/challengeDetailsBtnDelete"          # 删除赛段
CONFIRM_DELETE = f"{ID}/tv_d_ok"                            # 确认删除(弹窗, 防御用)


def wait_click(driver, locator, timeout=10):
    """等待元素可点击后点击（找不到则抛异常）"""
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator)).click()

def try_click(driver, locator, timeout=5):
    """尝试点击, 找不到就记录并跳过, 不中断流程"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)).click()
        return True
    except Exception:
        print(f"  [跳过] 页面无此元素: {locator[1] if isinstance(locator, tuple) else locator}")
        return False

def swipe_up(driver, times=1):
    """从下往上滑屏"""
    size = driver.get_window_size()
    x = size['width'] // 2
    sy = int(size['height'] * 0.8)
    ey = int(size['height'] * 0.2)
    for _ in range(times):
        driver.swipe(x, sy, x, ey, 500)
        time.sleep(0.5)

# ── logcat 后台抓取 ──

def start_logcat():
    """后台抓 logcat, 写到桌面/自动化测试log/stage_challenge.log"""
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


def test_stage_flow(driver=None):
    """赛段挑战 创建→删除 完整流程 (pytest共享driver, 直跑自建)"""
    own = driver is None
    if own:
        driver = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))

    try:
        # 强制重启App→主界面, 避免上次停在子页面找不到底部导航
        driver.terminate_app("com.shiye.cyclingai.ride")
        driver.activate_app("com.shiye.cyclingai.ride")
        time.sleep(3)

        start_logcat()
        # ═══ 创建赛段挑战 ═══
        wait_click(driver, (AppiumBy.ID, MAIN_TRAINING))
        print("[1] 点击挑战训练")
        time.sleep(2)

        wait_click(driver, STAGE_CREATE)
        print("[2] 点击赛段挑战创建")
        time.sleep(1)

        wait_click(driver, (AppiumBy.ID, STAGE_SELECT))
        print("[3] 点击赛段选择")
        time.sleep(1)

        wait_click(driver, STAGE_FIRST)
        print("[4] 点击赛段选择第一条")
        time.sleep(1)

        wait_click(driver, (AppiumBy.ID, STAGE_AVG_SPEED))
        print("[5] 点击赛段速度要求")

        swipe_up(driver, times=1)
        print("[6] 下滑一次")

        wait_click(driver, (AppiumBy.ID, STAGE_SAVE))
        print("[7] ✅ 点击赛段保存")

        try_click(driver, (AppiumBy.ID, BACK))
        print("[8] 运动记录返回")

        try_click(driver, (AppiumBy.ID, BACK))
        print("[9] 赛段挑战返回")
        time.sleep(1)

        # ═══ 删除赛段挑战 ═══
        wait_click(driver, (AppiumBy.ID, FIRST_STAGE))
        print("[10] 点击第一个赛段")
        time.sleep(1)

        swipe_up(driver, times=1)
        print("[11] 下滑一次")

        wait_click(driver, (AppiumBy.ID, STAGE_DELETE))
        print("[12] ✅ 点击删除赛段")

        try_click(driver, (AppiumBy.ID, CONFIRM_DELETE), timeout=3)
        print("[13] 确认删除弹窗(若有)")

        print("\n🎉 赛段挑战 创建→删除 全流程完成")

    finally:
        stop_logcat()
        if own:
            driver.quit()


if __name__ == "__main__":
    test_stage_flow()

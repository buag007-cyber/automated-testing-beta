# test_plan_full_flow.py — 骑迹GPS 训练计划 增→改→删 完整流程
# 用法: python test_plan_full_flow.py（需先启动 Appium Server）
#
# 流程（按 app元素.txt 自动化测试流程）：
#   挑战训练 → 返回运动界面 → 历史数据 → 第一条记录 → 返回 →
#   我的信息 → 主界面 → 挑战训练 → 添加计划(热身+主训练) → 保存 →
#   第一条计划 → 随机改参数(不改训练目标) → 保存 →
#   第一条计划 → 删除或更改
# 导航步骤找不到元素会自动跳过（底部导航可能在多页面存在）

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import subprocess
import os

import pytest

pytestmark = pytest.mark.ui  # UI用例: 无真机时 conftest 自动跳过

# ── 日志（桌面/自动化测试log）──
LOG_DIR = r"C:\Users\Administrator\Desktop\自动化测试log"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "training_plan.log")
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

# 主界面导航
MAIN_RIDING    = f"{ID}/mainIvRiding"           # 主界面
MAIN_RECORD    = f"{ID}/mainIvRecord"           # 历史数据
MAIN_SETTINGS  = f"{ID}/mainIvSettings"         # 我的信息
MAIN_TRAINING  = f"{ID}/mainIvTraining"         # 挑战训练
NAV_BACK       = f"{ID}/navigationSelectionBackIv"  # 返回运动界面

# 训练计划
ADD_PLAN       = (AppiumBy.ANDROID_UIAUTOMATOR,
    'new UiSelector().className("android.widget.FrameLayout").instance(6)')
FIRST_PLAN     = (AppiumBy.ANDROID_UIAUTOMATOR,
    'new UiSelector().className("android.view.ViewGroup").instance(1)')
PLAN_SAVE      = f"{ID}/createATrainingPlanBtnSave"  # 保存/删除共用
CONFIRM_DELETE = f"{ID}/tv_d_ok"                      # 确认删除(弹窗)

# 历史记录
FIRST_RECORD   = (AppiumBy.ANDROID_UIAUTOMATOR,
    'new UiSelector().resourceId("com.shiye.cyclingai.ride:id/ridingRecordRl").instance(0)')
RECORD_BACK    = f"{ID}/ib_back"

# 热身
WARM_SETTINGS  = f"{ID}/iv_settings_warm_up"
SEGMENT_TYPE   = (AppiumBy.ANDROID_UIAUTOMATOR,
    'new UiSelector().className("android.widget.ImageView").instance(1)')
WARM_TIME      = f"{ID}/timeTextView"
WARM_TIME_SET  = f"{ID}/trainingWarmUpDurationTv"
WARM_SAVE      = f"{ID}/trainingWarmUpBtnSave"

# 主训练
MAIN_TRAIN_SET = f"{ID}/iv_settings_main_set"
TRAIN_TARGET   = f"{ID}/coreTrainingTargetLl"
TRAIN_TARGET_HR= f"{ID}/coreTrainingTimeTextView"
INTENSITY      = f"{ID}/trainingCoreTrainingTargetIntensityEt"
DURATION       = f"{ID}/trainingCoreTrainingWorkDurationEt"
INTERVAL       = f"{ID}/trainingCoreTrainingIntervalDurationEt"
REPEAT         = f"{ID}/trainingCoreTrainingRepetitionsEt"
MAIN_SAVE      = f"{ID}/trainingCoreTrainingSaveBtn"


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

def wait_send(driver, locator, text, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located(locator))
    el.clear()
    el.send_keys(text)

def keyboard_done(driver):
    try:
        driver.hide_keyboard()
    except:
        pass
    time.sleep(0.3)

def swipe_up(driver, times=1):
    size = driver.get_window_size()
    x = size['width'] // 2
    sy = int(size['height'] * 0.8)
    ey = int(size['height'] * 0.2)
    for _ in range(times):
        driver.swipe(x, sy, x, ey, 500)
        time.sleep(0.5)

# ── logcat 后台抓取 ──

def start_logcat():
    """后台抓 logcat, 写到桌面/自动化测试log/training_plan.log"""
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


def test_full_flow():
    """增→改→删 完整流程"""
    driver = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))

    try:
        # 强制重启App→主界面, 避免上次停在子页面找不到底部导航
        driver.terminate_app("com.shiye.cyclingai.ride")
        driver.activate_app("com.shiye.cyclingai.ride")
        time.sleep(3)

        start_logcat()
        # ═══ 导航遍历（找不到就跳过）═══
        wait_click(driver, (AppiumBy.ID, MAIN_TRAINING))
        print("[1] 点击挑战训练")
        time.sleep(2)

        try_click(driver, (AppiumBy.ID, NAV_BACK))
        print("[2] 返回运动界面")

        try_click(driver, (AppiumBy.ID, MAIN_RECORD))
        print("[3] 点击历史数据")

        try_click(driver, FIRST_RECORD)
        print("[4] 点击第一条运动记录")

        try_click(driver, (AppiumBy.ID, RECORD_BACK))
        print("[5] 运动记录详情返回")

        try_click(driver, (AppiumBy.ID, MAIN_SETTINGS))
        print("[6] 点击我的信息")

        try_click(driver, (AppiumBy.ID, MAIN_RIDING))
        print("[7] 再点击主界面")

        wait_click(driver, (AppiumBy.ID, MAIN_TRAINING))
        print("[8] 点击挑战训练")
        time.sleep(2)

        # 上滑露出"训练计划添加"
        swipe_up(driver, times=3)
        time.sleep(1)

        # ═══ 创建训练计划 ═══
        wait_click(driver, ADD_PLAN)
        print("[9] 点击训练计划添加")

        wait_click(driver, (AppiumBy.ID, WARM_SETTINGS))
        print("[10] 点击热身设置")

        wait_click(driver, SEGMENT_TYPE)
        print("[11] 点击分段类型")

        wait_click(driver, (AppiumBy.ID, WARM_TIME))
        wait_click(driver, (AppiumBy.ID, WARM_TIME_SET))
        wait_send(driver, (AppiumBy.ID, WARM_TIME_SET), "5")
        keyboard_done(driver)
        print("[12] 热身时间 输入5 确认")

        wait_click(driver, (AppiumBy.ID, WARM_SAVE))
        print("[13] 点击热身保存")

        wait_click(driver, (AppiumBy.ID, MAIN_TRAIN_SET))
        print("[14] 点击主训练设置")

        wait_click(driver, (AppiumBy.ID, TRAIN_TARGET))
        wait_click(driver, (AppiumBy.ID, TRAIN_TARGET_HR))
        print("[15] 点击训练目标 → 训练目标心率")

        wait_send(driver, (AppiumBy.ID, INTENSITY), "90")
        keyboard_done(driver)
        print("[16] 心率目标强度 输入90 确认")

        wait_send(driver, (AppiumBy.ID, DURATION), "5")
        keyboard_done(driver)
        print("[17] 训练时长 输入5 确认")

        wait_send(driver, (AppiumBy.ID, INTERVAL), "3")
        keyboard_done(driver)
        print("[18] 间隔时长 输入3 确认")

        wait_send(driver, (AppiumBy.ID, REPEAT), "2")
        keyboard_done(driver)
        print("[19] 重复次数 输入2 确认")

        wait_click(driver, (AppiumBy.ID, MAIN_SAVE))
        print("[20] 点击主训练保存")

        wait_click(driver, (AppiumBy.ID, PLAN_SAVE))
        print("[21] ✅ 点击训练计划保存")

        # ═══ 修改训练计划 ═══
        wait_click(driver, FIRST_PLAN)
        print("[22] 点击第一条训练计划")

        # 随机改一个参数（不改训练目标）
        choices = [
            ("热身时间", lambda: modify_warmup(driver)),
            ("心率强度", lambda: modify_param(driver, INTENSITY, "85")),
            ("训练时长", lambda: modify_param(driver, DURATION, "8")),
            ("间歇时长", lambda: modify_param(driver, INTERVAL, "5")),
            ("重复次数", lambda: modify_param(driver, REPEAT, "3")),
        ]
        name, action = random.choice(choices)
        action()
        print(f"[23] 随机修改: {name}")

        wait_click(driver, (AppiumBy.ID, PLAN_SAVE))
        print("[24] ✅ 保存修改")

        # ═══ 删除训练计划 ═══
        wait_click(driver, FIRST_PLAN)
        print("[25] 再点击第一条训练计划")

        wait_click(driver, (AppiumBy.ID, PLAN_SAVE))
        print("[26] 点击训练计划删除或更改")

        wait_click(driver, (AppiumBy.ID, CONFIRM_DELETE))
        print("[27] ✅ 点击确认删除")

        print("\n🎉 增→改→删 全流程完成")

    finally:
        stop_logcat()
        driver.quit()


def modify_warmup(driver):
    """改热身时间→8（不动训练目标）"""
    wait_click(driver, (AppiumBy.ID, WARM_SETTINGS))
    wait_send(driver, (AppiumBy.ID, WARM_TIME_SET), "8")  # 编辑页是EditText, 直接输入
    keyboard_done(driver)
    wait_click(driver, (AppiumBy.ID, WARM_SAVE))

def modify_param(driver, locator, value):
    """直接改主训练某个参数（不动训练目标）"""
    wait_click(driver, (AppiumBy.ID, MAIN_TRAIN_SET))
    wait_send(driver, (AppiumBy.ID, locator), value)
    keyboard_done(driver)
    wait_click(driver, (AppiumBy.ID, MAIN_SAVE))


if __name__ == "__main__":
    test_full_flow()

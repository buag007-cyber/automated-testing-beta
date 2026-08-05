# test_map_download.py — 骑迹GPS 离线地图下载自动化
# 用法: python test_map_download.py（需先启动 Appium Server）
#
# 流程: 运动界面 → 地图区域 → 离线地图管理 →
#       若有地图先删除 → 点下载 → 等待完成 → 返回
# 完成检测: 地图删除按钮重现 (ID=mapManagementPageCancelIbt + 文字=删除)
# 日志: 全程抓 logcat 到 map_download.log, 可给AI分析

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, subprocess, threading, os

import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(600)]  # UI用例: 无真机跳过, 10分钟超时防卡死

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

ID = "com.shiye.cyclingai.ride:id"

MAIN_MAP        = f"{ID}/mainLlMap"                 # 运动界面
MAIN_RIDING     = f"{ID}/mainIvRiding"              # 主界面(兜底)
MAP_AREA        = f"{ID}/mapRoadNavigationIv"       # 地图区域
MAP_MANAGE      = f"{ID}/navigationSelectionMapManagementBt"  # 离线地图管理
MAP_DELETE      = f"{ID}/mapManagementPageCancelIbt"          # 地图删除
MAP_CONFIRM_DEL = f"{ID}/tv_d_ok"                              # 地图确认删除(弹窗)
MAP_DOWNLOAD    = f"{ID}/mapManagementPageUploadIbt"          # 地图下载
MAP_MANAGE_BACK = f"{ID}/mapManagementPageRollbackIv"         # 离线地图管理返回
MAP_BACK        = f"{ID}/navigationSelectionBackIv"           # 地图返回

# 日志目录: 桌面/自动化测试log
LOG_DIR = r"C:\Users\Administrator\Desktop\自动化测试log"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "map_download.log")
_logcat_proc = None


# ── 基础操作 ──

def wait_click(driver, locator, timeout=10):
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator)).click()

def try_click(driver, locator, timeout=5):
    """尝试点击, 失败返回 False"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)).click()
        return True
    except Exception:
        return False

def is_displayed(driver, locator, timeout=3):
    """检查元素是否存在"""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)) is not None
    except Exception:
        return False

def find_map_btn(driver, text, timeout=3):
    """查找地图管理页按钮: ID 是 CancelIbt, 且文字匹配"""
    loc = (AppiumBy.ANDROID_UIAUTOMATOR,
        f'new UiSelector().resourceId("{ID}/mapManagementPageCancelIbt").textContains("{text}")')
    try:
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(loc))
    except Exception:
        return None

def delete_btn_present(driver, timeout=3):
    """地图删除按钮是否出现 (文字=删除, 排除下载中的取消)"""
    return find_map_btn(driver, "删除", timeout) is not None


# ── logcat 后台抓取 ──

def start_logcat():
    """后台抓 logcat, 按包名过滤, 写到 map_download.log"""
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


# ── 下载完成检测 ──

def wait_download_done(driver, timeout=7200):
    """等待下载完成: 删除按钮重现 (ID=mapManagementPageCancelIbt 且文字=删除)"""
    start = time.time()
    last_log = 0
    while time.time() - start < timeout:
        # 每次轮询都看 CancelIbt 的真实状态
        try:
            btns = driver.find_elements(AppiumBy.ID, f"{ID}/mapManagementPageCancelIbt")
            states = [f"'{b.text}'" for b in btns]
        except Exception:
            states = ["查询异常"]
        if time.time() - last_log > 20:
            print(f"  [诊断] {int((time.time()-start)/60)}分{int(time.time()-start)%60}s  CancelIbt状态: {states}")
            last_log = time.time()
        # 完成信号: 按钮存在且文字=删除 (下载中是"取消", 不匹配)
        if any("删除" in s for s in states):
            return f"删除按钮重现, 耗时 {time.time()-start:.0f}s"
        time.sleep(10)
    raise TimeoutError(f"下载超时 {timeout}s")


# ── 主流程 ──

def test_map_download():
    driver = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))

    try:
        # 下载期间保持亮屏
        subprocess.run(["adb", "shell", "svc", "power", "stayon", "true"])
        start_logcat()
        print("===== 离线地图下载流程 =====")

        # 1. 运动界面
        if not try_click(driver, (AppiumBy.ID, MAIN_MAP)):
            wait_click(driver, (AppiumBy.ID, MAIN_RIDING))  # 兜底: 主界面入口
        print("[1] 运动界面")

        # 2. 地图区域
        wait_click(driver, (AppiumBy.ID, MAP_AREA))
        print("[2] 地图区域")

        # 3. 离线地图管理
        wait_click(driver, (AppiumBy.ID, MAP_MANAGE))
        print("[3] 离线地图管理")
        time.sleep(2)

        # 4. 若有地图 → 先删除 + 确认删除 (按钮文字必须是"删除", 排除"取消")
        del_btn = find_map_btn(driver, "删除", timeout=3)
        if del_btn:
            del_btn.click()
            print("[4] 删除旧地图")
            time.sleep(1)
            wait_click(driver, (AppiumBy.ID, MAP_CONFIRM_DEL))
            print("[4.1] 确认删除")
            time.sleep(3)

        # 5. 点击下载
        wait_click(driver, (AppiumBy.ID, MAP_DOWNLOAD))
        print("[5] 开始下载, 等待完成...")

        # 6. 等待下载+安装完成
        result = wait_download_done(driver)
        print(f"[6] ✅ 下载完成 ({result})")

        # 7. 离线地图管理返回
        wait_click(driver, (AppiumBy.ID, MAP_MANAGE_BACK))
        print("[7] 离线地图管理返回")

        # 8. 地图返回
        wait_click(driver, (AppiumBy.ID, MAP_BACK))
        print("[8] 地图返回")

        # 9. 回到运动界面, 再返回
        try_click(driver, (AppiumBy.ID, MAP_BACK))
        print("[9] 返回运动界面")

        print("\n🎉 离线地图下载流程完成")

    finally:
        # 恢复自动锁屏
        subprocess.run(["adb", "shell", "svc", "power", "stayon", "false"])
        stop_logcat()
        driver.quit()


if __name__ == "__main__":
    test_map_download()

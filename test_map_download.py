# test_map_download.py — 骑迹GPS 离线地图下载自动化
# 用法: python test_map_download.py（需先启动 Appium Server）
#
# 流程: 运动界面 → 地图区域 → 离线地图管理 →
#       若有地图先删除 → 点下载 → 等待完成 → 返回
# 完成检测(两路信号, 谁先到算谁):
#   1) UI轮询: 删除按钮重现 (ID=mapManagementPageCancelIbt + 文字=删除)
#   2) UI辅助: 管理页整体消失 = app上传完成自动返回; 完成/超时都存页面XML快照
# 日志: 全程抓 logcat 到 map_download.log, 供事后分析(不参与完成判断)

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, subprocess, threading, os

import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(3600), pytest.mark.order(2)]  # 流程第2步: 地图下载(可能十几分钟, 超时给1小时)

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

def _app_uid():
    """查 app UID(安装后固定), 用于 logcat 按 UID 过滤"""
    try:
        out = subprocess.run(["adb", "shell", "pm", "list", "packages", "-U", "com.shiye.cyclingai.ride"],
                             capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if " uid:" in line:
                return line.strip().rsplit("uid:", 1)[1]
    except Exception:
        pass
    return None

def start_logcat():
    """后台抓 logcat, 按 UID 过滤 app 全量日志, 写到 map_download.log"""
    global _logcat_proc
    uid = _app_uid()
    if uid:
        # app 全量日志(Mapbox下载/业务打印/崩溃), 不再 *:S 静音
        cmd = ["adb", "logcat", "-v", "time", f"--uid={uid}"]
    else:
        # UID 取不到时兜底: 系统上下文+崩溃
        cmd = ["adb", "logcat", "-v", "time", "-s", "ActivityManager:I", "AndroidRuntime:E", "*:S"]
        print("[日志] 未取到 app UID, 退化为系统上下文过滤")
    try:
        # buffering=1 行缓冲: 每行立即落盘, 让log完成信号能实时读到
        _logcat_proc = subprocess.Popen(cmd, stdout=open(LOG_FILE, "w", encoding="utf-8", errors="ignore", buffering=1))
    except Exception as e:
        print(f"[日志] logcat 启动失败: {e}")

def stop_logcat():
    global _logcat_proc
    if _logcat_proc:
        _logcat_proc.terminate()
        _logcat_proc = None
        print("[日志] logcat 已停止")


# ── 下载完成检测 ──

_ui_snapshots = []   # 本次运行生成的XML快照路径(结束后按结果清理)

def dump_ui(driver, tag):
    """UI辅助: 完成/超时/异常时存一份页面XML快照, 事后确认停在哪个页面"""
    try:
        path = os.path.join(LOG_DIR, f"map_download_{tag}_{time.strftime('%H%M%S')}.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        _ui_snapshots.append(path)
        print(f"[UI] 页面快照: {path}")
    except Exception as e:
        print(f"[UI] 快照失败: {e}")

def wait_download_done(driver, timeout=7200):
    """等待下载+上传完成, 两路信号谁先到算谁:
    1) UI轮询: 删除按钮重现 (CancelIbt文字含'删除')
    2) UI辅助: 管理页整体消失 = app上传完成自动返回 (兼容按钮不重现的情况)
    完成/超时都存页面XML快照, 事后确认实际停在哪个页面"""
    start = time.time()
    last_log = 0
    page_seen = False   # 是否确认过管理页还在(防止一开始误判页面消失)
    while time.time() - start < timeout:
        # 1) UI轮询按钮 + 页面状态
        try:
            btns = driver.find_elements(AppiumBy.ID, f"{ID}/mapManagementPageCancelIbt")
            states = [f"'{b.text}'" for b in btns]
        except Exception:
            states = ["查询异常"]
            btns = []
        back_visible = is_displayed(driver, (AppiumBy.ID, MAP_MANAGE_BACK), timeout=1)
        page_here = bool(btns) or back_visible
        if page_here:
            page_seen = True
        # 进度文本(仅诊断用)
        prog = ""
        try:
            texts = [el.text for el in driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().className("android.widget.TextView")')]
            prog = next((t for t in texts if "%" in t), "") \
                or next((t for t in texts if "MB" in t or "GB" in t), "")
        except Exception:
            pass
        # 2) 诊断打印
        if time.time() - last_log > 20:
            print(f"  [诊断] {int((time.time()-start)//60)}分{int(time.time()-start)%60}s  "
                  f"CancelIbt: {states}  进度: {prog}")
            last_log = time.time()
        # 3) 完成判定: 删除按钮重现 / 管理页自动返回
        if any("删除" in s for s in states):
            dump_ui(driver, "btn_delete")
            return f"删除按钮重现(UI), 耗时 {time.time()-start:.0f}s"
        if page_seen and not page_here:
            dump_ui(driver, "page_gone")
            return f"管理页自动返回(页面消失), 耗时 {time.time()-start:.0f}s"
        time.sleep(10)
    dump_ui(driver, "timeout")
    raise TimeoutError(f"下载超时 {timeout}s (页面停留见XML快照, 详情查map_download.log)")


# ── 主流程 ──

def test_map_download(driver=None):
    """离线地图下载流程 (pytest共享driver, 直跑自建)"""
    own = driver is None
    if own:
        driver = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))
    _ui_snapshots.clear()   # 清掉上次运行的快照记录
    success = False

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

        # 7. 离线地图管理返回 (上传成功可能已自动返回, 找不到就跳过)
        if not try_click(driver, (AppiumBy.ID, MAP_MANAGE_BACK), timeout=3):
            print("[7] 管理页已自动返回, 跳过")
        else:
            print("[7] 离线地图管理返回")

        # 8. 地图返回
        wait_click(driver, (AppiumBy.ID, MAP_BACK))
        print("[8] 地图返回")

        # 9. 回到运动界面, 再返回
        try_click(driver, (AppiumBy.ID, MAP_BACK))
        print("[9] 返回运动界面")

        print("\n🎉 离线地图下载流程完成")
        success = True

    finally:
        # 恢复自动锁屏
        subprocess.run(["adb", "shell", "svc", "power", "stayon", "false"])
        stop_logcat()
        # 临时产物清理: 成功自动删, 失败保留供分析
        if success:
            for p in _ui_snapshots:
                try:
                    os.remove(p)
                except OSError:
                    pass
            try:
                os.remove(LOG_FILE)
            except OSError:
                pass
            print("[清理] 已删除XML快照和map_download.log")
        else:
            if _ui_snapshots:
                print("[保留] 失败快照: " + ", ".join(_ui_snapshots))
            if os.path.exists(LOG_FILE):
                print(f"[保留] 失败日志: {LOG_FILE}")
        if own:
            driver.quit()


if __name__ == "__main__":
    test_map_download()

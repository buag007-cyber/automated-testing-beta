# -*- coding: utf-8 -*-
# 临时排查: 打开离线地图管理页, 打印所有按钮/TextView的 id+文字, 看下载各状态
import time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

APPIUM_URL = "http://127.0.0.1:4723"
CAPS = {
    "platformName": "Android", "automationName": "UiAutomator2",
    "deviceName": "Android Device", "appPackage": "com.shiye.cyclingai.ride",
    "noReset": True, "dontStopAppOnReset": True,
    "newCommandTimeout": 300, "adbExecTimeout": 60000, "autoGrantPermissions": True,
}
ID = "com.shiye.cyclingai.ride:id"

def dump(tag):
    """打印当前页所有 按钮/TextView: id + 文字 + 可点击"""
    print(f"\n===== {tag} =====")
    try:
        els = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((AppiumBy.ID, f"{ID}/mapManagementPageCancelIbt")))
    except Exception:
        pass
    nodes = driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true' or @class='android.widget.TextView']")
    for n in nodes:
        rid = n.get_attribute("resourceId") or ""
        txt = (n.text or "").strip()
        clk = n.get_attribute("clickable")
        cls = n.get_attribute("className") or ""
        # 只打印地图管理相关 + 有文字/可点击的
        if ("mapManagement" in rid or "navigationSelection" in rid or txt or clk == "true"):
            short = rid.replace(ID + "/", "")
            print(f"  id={short or '(无)'}  text='{txt}'  click={clk}  {cls.split('.')[-1]}")

driver = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))
try:
    # 1. 运动界面(兜底主界面)
    try:
        WebDriverWait(driver, 8).until(EC.element_to_be_clickable((AppiumBy.ID, f"{ID}/mainLlMap"))).click()
    except Exception:
        WebDriverWait(driver, 8).until(EC.element_to_be_clickable((AppiumBy.ID, f"{ID}/mainIvRiding"))).click()
        WebDriverWait(driver, 8).until(EC.element_to_be_clickable((AppiumBy.ID, f"{ID}/mainLlMap"))).click()
    print("[1] 运动界面")
    # 2. 地图区域
    WebDriverWait(driver, 8).until(EC.element_to_be_clickable((AppiumBy.ID, f"{ID}/mapRoadNavigationIv"))).click()
    print("[2] 地图区域")
    time.sleep(1)
    # 3. 离线地图管理
    WebDriverWait(driver, 8).until(EC.element_to_be_clickable((AppiumBy.ID, f"{ID}/navigationSelectionMapManagementBt"))).click()
    print("[3] 离线地图管理")
    time.sleep(3)
    dump("进入管理页(静止状态)")

    # 4. 看删除按钮是否在 → 先删掉旧地图, 还原到"待下载"状态
    try:
        del_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().resourceId("{ID}/mapManagementPageCancelIbt").textContains("删除")')))
        print("\n发现删除按钮, 点击删除...")
        del_btn.click()
        time.sleep(1)
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((AppiumBy.ID, f"{ID}/tv_d_ok"))).click()
        print("已确认删除")
        time.sleep(3)
        dump("删除后(应出现下载按钮)")
    except Exception as e:
        print(f"\n无删除按钮(可能本来就没地图): {type(e).__name__}")

    # 5. 找下载按钮并点击, 抓下载中状态
    try:
        dl = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((AppiumBy.ID, f"{ID}/mapManagementPageUploadIbt")))
        print(f"\n点击下载按钮 text='{dl.text}'")
        dl.click()
        time.sleep(6)   # 等下载启动
        dump("下载中(6s后)")
        time.sleep(6)
        dump("下载中(12s后)")
    except Exception as e:
        print(f"\n找不到下载按钮: {type(e).__name__} {e}")
        dump("当前页面全量按钮")

    # 6. 清理: 如果还在下载, 点取消
    try:
        cancel = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().resourceId("{ID}/mapManagementPageCancelIbt").textContains("取消")')))
        cancel.click()
        print("\n已点取消, 停止下载")
        time.sleep(1)
    except Exception:
        print("\n没有取消按钮(下载已完成或未开始)")
    dump("清理后")

finally:
    driver.quit()
    print("\n已断开")

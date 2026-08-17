# run_all.py — 一键跑全流程主控 (双击/CI触发入口)
# 用法: python run_all.py  (或桌面 run.bat 双击)
# 流程: Appium检查 → 设备检查 → 装最新APK → pytest全流程(训练计划→导航→地图→赛段)
# GPS注入: conftest.py 后台线程持续注入, 从流程开始到结束不停
# 依赖: 项目 .venv 里的 pytest(含pytest-html), 真机+Appium Server

import os
import sys
import time
import socket
import shutil
import datetime
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"   # 项目解释器(装了pytest_html)
PKG = "com.shiye.cyclingai.ride"                  # 骑迹GPS包名
APK_GLOB = "CYBERSIGHT*.apk"                      # 公司APK命名规则
REINSTALL_APK = False                             # True=重装最新APK, False=跳过卸载安装
LOG_DIR = Path(r"C:\Users\Administrator\Desktop\自动化测试log")
CSS = ROOT / "report.css"
# 报告按日期归档: 桌面/自动化测试log/2026-08-17/report_1430.html
# 每天一个目录, 文件名带时间, 每次跑都不覆盖
RUN_DATE = datetime.datetime.now().strftime("%Y-%m-%d")
RUN_TIME = datetime.datetime.now().strftime("%H%M%S")
REPORT = LOG_DIR / RUN_DATE / f"report_{RUN_TIME}.html"
# 全部UI用例文件, 按 order 标记顺序执行:
#   1训练计划 → 2地图下载 → 3赛段挑战(创建→删除+GPS) → 4导航+GPS
# GPS注入: 赛段挑战和导航都声明 gps_bg fixture, 各自执行期间后台注入
TEST_FILES = ["test_plan_full_flow.py", "test_map_download.py",
              "test_stage_challenge.py", "test_navigation_flow.py"]


def sh(cmd, **kw):
    """跑命令并打印, 返回CompletedProcess"""
    print("$", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], **kw)


def port_ok(port=4723):
    """Appium端口是否已监听"""
    s = socket.socket()
    s.settimeout(2)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def ensure_appium():
    """Appium没起就自动启动, 最多等30秒"""
    if port_ok():
        print("[Appium] 已运行")
        return
    print("[Appium] 未运行, 自动启动...")
    # Windows下appium是npm的.cmd文件, CreateProcess不认, 必须经cmd.exe启动
    ap = shutil.which("appium") or "appium"
    subprocess.Popen(f'"{ap}"', shell=True,
                     creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(30):
        time.sleep(1)
        if port_ok():
            print("[Appium] 启动成功")
            return
    sys.exit("[Appium] 启动失败(30秒超时)")


def find_apk():
    """Downloads里找最新的CYBERSIGHT apk"""
    cands = sorted(
        Path.home().joinpath("Downloads").glob(APK_GLOB),
        key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        sys.exit(f"[APK] Downloads下没找到 {APK_GLOB}")
    return cands[0]


def install_apk(apk):
    """卸载旧包→装新包 (卸载失败=没装过, 忽略)"""
    # sh(["adb", "uninstall", PKG])
    r = sh(["adb", "install", "-r", str(apk)])
    if r.returncode != 0:
        sys.exit(f"[APK] 安装失败: {apk}")


def run_pytest():
    """一次跑完全部UI用例, GPS后台持续注入, 失败即停, 出HTML报告"""
    print(f"\n===== pytest 全流程 ({len(TEST_FILES)}个文件, GPS后台注入中) =====")
    env = {**os.environ, "RUN_UI": "1"}
    r = subprocess.run([
        str(PY), "-m", "pytest", *TEST_FILES,
        "-m", "ui", "-x",                       # 只跑ui用例, 失败即停
        "--html", str(REPORT),                  # HTML报告
        "--css", str(CSS),                      # 自定义美化样式
        "--self-contained-html",                # 单文件报告(可分享)
    ], env=env, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"[pytest] 有失败, 看报告: {REPORT}")


def main():
    LOG_DIR.mkdir(exist_ok=True)
    REPORT.parent.mkdir(exist_ok=True)  # 日期目录
    ensure_appium()
    # 设备检查
    r = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [ln for ln in r.stdout.strip().splitlines()[1:] if ln.strip()]
    if not lines or "device" not in lines[-1]:
        sys.exit("[设备] 没连真机, 请先adb连接手机")
    # 装APK (默认跳过, 需要时把REINSTALL_APK改成True)
    if REINSTALL_APK:
        apk = find_apk()
        print(f"[APK] 使用最新: {apk.name}")
        install_apk(apk)
    # 跑全流程 (GPS注入由conftest后台线程贯穿全程)
    run_pytest()
    print(f"\n✅ 全流程完成, 报告: {REPORT}")


if __name__ == "__main__":
    main()

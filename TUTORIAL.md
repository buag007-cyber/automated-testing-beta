# PythonProjectKK 测试流程编排教程

> 目标：把 3 个 UI 自动化脚本 + cc-android GPS 注入，串成一个按顺序执行、
> 共享一个 Appium 连接的完整骑行测试流程，失败即停。后续可以随时加脚本、调顺序。

---

## 一、现在的流程结构

```
RUN_UI=1 pytest -m ui        ← 一条命令跑整个流程
  │
  ├─ [1] test_plan_full_flow.py   训练计划 增→改→删   (order=1)
  ├─ [2] test_gps_inject.py       GPS注入, 模拟骑行60s (order=2)
  ├─ [3] test_navigation_flow.py  地图导航            (order=3)
  └─ [4] test_map_download.py     离线地图下载          (order=4)

  所有步骤共享一个 Appium 连接 (conftest.py 的 driver fixture)
  driver 连接在第一步前建立, 最后一步跑完统一断开
```

### 为什么必须共享 driver？

一台手机同时只能有一个 UiAutomator2 会话。如果每个脚本自己
`webdriver.Remote(...)` 连接，第 2 个脚本连的时候就会冲突失败。
所以 conftest.py 里建了 session 级 fixture：

```python
@pytest.fixture(scope="session")
def driver():
    drv = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(CAPS))
    yield drv          # 所有用例注入同一个 driver
    drv.quit()         # 流程结束统一断开
```

### 每个脚本的 driver 参数（两种运行方式都能用）

每个 test 函数都写成 `def test_xxx(driver=None)`：

```python
def test_full_flow(driver=None):
    own = driver is None          # 判断是不是 pytest 注入的
    if own:                       # 直跑时自建连接
        driver = webdriver.Remote(...)
    try:
        ...流程...
    finally:
        if own:                   # 共享时不 quit, 留给 fixture 统一断
            driver.quit()
```

- pytest 跑：conftest 自动注入共享 driver，流程结束统一断开
- `python test_xxx.py` 直跑：driver=None，自己建自己断（老用法不变）

---

## 二、怎么跑

```bash
# 整个流程（真机 + Appium Server 起着）
RUN_UI=1 python -m pytest -m ui -v

# 失败即停（某步挂了后面不跑）
RUN_UI=1 python -m pytest -m ui -v -x

# 只跑某一步
RUN_UI=1 python -m pytest test_gps_inject.py -v

# 跳过某一步（比如只跑 3 和 4）
RUN_UI=1 python -m pytest -m ui -v -k "navigation or map"

# 单步调试（老用法，不经过 pytest）
python test_plan_full_flow.py

# 出 HTML 报告
RUN_UI=1 python -m pytest -m ui --html=report.html
```

PowerShell 里设环境变量：`$env:RUN_UI="1"` 再跑 pytest。

---

## 三、怎么融入新脚本（重点）

新脚本三步走：

### 1. 复制模板建文件 `test_05_你的名字.py`

```python
# test_05_xxx.py — 流程第5步: 描述
import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(600), pytest.mark.order(5)]

def test_xxx(driver=None):
    """描述 (pytest共享driver, 直跑自建)"""
    own = driver is None
    if own:
        driver = webdriver.Remote("http://127.0.0.1:4723",
            options=UiAutomator2Options().load_capabilities(CAPS))
    try:
        # 你的 UI 操作, 用 driver 找元素点击
        ...
    finally:
        if own:
            driver.quit()
```

### 2. 调整其他文件的 order 数字

比如新脚本想插在导航(3)和地图下载(4)中间：
- 新文件: `pytest.mark.order(4)`
- test_map_download.py 改成: `pytest.mark.order(5)`

数字即顺序，改数字就是调顺序。

### 3. 想复用 cc-android 的 GPS 逻辑？

看 test_gps_inject.py 怎么做的：

```python
import importlib.util
from pathlib import Path

_CC = Path(__file__).parent / "cc-android.py"   # 动态加载, 不改原脚本
_spec = importlib.util.spec_from_file_location("cc_android", _CC)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

cfg = cc.Config()
pts = cc.load_route(cfg.gpx_file)      # 加载GPX路线
pl = cc.Player(pts, cfg)               # 播放器
for lat, lon, ele, spd in pl.play():   # 逐个坐标
    driver.set_location(lat, lon, ele, speed=spd)  # 注入
    time.sleep(0.5)
```

---

## 四、CI/CD（代码健康检查）

GitHub Actions 每次 push 自动跑：

```yaml
- name: 语法检查所有py
  run: python -m compileall -q .          # 所有.py无语法错误
- name: pytest 用例收集检查
  run: pytest --collect-only -q           # 用例能正常收集(导入无错)
```

为什么 CI 不真跑流程？因为流程要真机 + Appium + GPX，CI 虚拟机没有。
CI 的作用是防止"提交了语法错误/导入失败"的坏代码。
以后有真机 runner（比如公司电脑挂着跑）再扩展成真跑。

部署步骤：
1. 建 GitHub 仓库（https://github.com/new，不要勾 README）
2. `git remote add origin https://github.com/用户名/PythonProjectKK.git`
3. `git push -u origin master`
4. 仓库页面 Actions 标签看结果

---

## 五、常见问题

**Q: 跑 pytest 报 "test_full_flow() got multiple values for argument 'driver'"**
A: 用了 pytest-order 且 conftest 有 driver fixture，不会出现。
   真出现说明 test 函数里手写了 driver 参数默认值冲突，检查签名。

**Q: 想调注入时长 / 换 GPX 路线**
A: 改 test_gps_inject.py 顶部：
   `INJECT_SECONDS = 60` 或 `cc.Config().gpx_file = r"路径"`

**Q: 某步失败想继续跑后面的**
A: 去掉 `-x` 参数。pytest 默认全部执行完，只是失败的标红。

**Q: 步骤之间 App 页面状态衔接不上**
A: 每个脚本开头都有 try_click 兜底导航（跳到运动界面/主界面），
   如果还乱，在脚本开头加 `driver.terminate_app + activate_app` 强制重启。

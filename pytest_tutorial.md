# pytest 从零开始教程（PythonProjectKK 实战版）

> 这份教程假设你完全没学过 pytest。看完你会：
> 1. 知道 pytest 是怎么工作的
> 2. 会自己写新用例（test_ 函数 + 断言）
> 3. 会改项目里的东西（加脚本、调顺序、改注入时长）
> 4. 遇到报错会自己看懂

---

## 第一部分：pytest 是什么

一句话：**pytest 是 Python 的测试框架，你只需要写"检查对不对"的函数，
它自动帮你找出来、跑起来、告诉你结果。**

传统写法（不用 pytest）：
```python
# 手动调函数、手动判断、手动打印
def check_distance():
    d = dist_m(0, 0, 0.01, 0)
    if d == 1111.95:
        print("通过")
    else:
        print("失败")

check_distance()  # 还得自己记得调它
```

pytest 写法：
```python
def test_distance():          # 函数名 test_ 开头
    d = dist_m(0, 0, 0.01, 0)
    assert d == 1111.95       # assert 一行搞定
```

pytest 的规矩只有两条：
- 文件名以 `test_` 开头（或 `_test` 结尾）→ 会被自动找到
- 文件里函数名以 `test_` 开头 → 会被自动执行

跑 `pytest` 后，它自动扫描当前目录所有 test_ 文件，逐个执行，
输出谁过了、谁挂了、挂在哪一行。不需要 main，不需要手动调用。

---

## 第二部分：从零搭环境

你的项目已经搭好了，对照着理解：

```bash
pip install pytest          # 装框架（你已经装了 pytest-order/html/timeout）
```

项目里的 pytest 相关文件：

```
PythonProjectKK/
├── pytest.ini              # pytest 配置文件（告诉它去哪找用例）
├── conftest.py             # 全局配置 + 共享的 driver
├── test_plan_full_flow.py  # 用例文件1（训练计划）
├── test_gps_inject.py      # 用例文件2（GPS注入）
├── test_navigation_flow.py # 用例文件3（导航）
└── test_map_download.py    # 用例文件4（地图下载）
```

pytest.ini 内容：
```ini
[pytest]
testpaths = .          # 去哪找测试文件：当前目录
markers =
    ui: 依赖真机+Appium的UI用例, 无真机自动跳过
```

`markers` 是注册标记用的——下面第三部分讲标记。

---

## 第三部分：怎么写第一个用例

### 3.1 最小用例

在项目里新建 `test_hello.py`：

```python
def test_add():
    assert 1 + 1 == 2        # assert 后面的表达式为真 → 通过
```

跑 `python -m pytest test_hello.py -v`，输出：

```
test_hello.py::test_add PASSED
```

### 3.2 断言（assert）的三种写法

pytest 里的 `assert` 就是"我赌这里是对的"：

```python
def test_examples():
    # 1. 相等比较
    assert "abc" == "abc"

    # 2. 浮点数要用 approx（计算机小数有误差, 0.1+0.2 != 0.3）
    assert 0.1 + 0.2 == 0.3          # ❌ 可能挂!
    assert 0.1 + 0.2 == pytest.approx(0.3)   # ✅ 允许微小误差
    assert 2.0 == pytest.approx(1.9999, rel=0.01)  # 相对误差1%

    # 3. 期望它抛异常
    with pytest.raises(ZeroDivisionError):
        1 / 0
```

### 3.3 用例失败长什么样

```python
def test_will_fail():
    assert 1 + 1 == 3
```

输出关键几行：
```
>       assert 1 + 1 == 3
E       assert (1 + 1) == 3
test_hello.py:2: AssertionError
```
- `>` 指向出错那一行
- `E` 是错误详情，告诉你实际值
- 最后是文件和行号

### 3.4 写一个你项目场景的用例

假设你要检查"GPX 路线加载后至少有 2 个点"：

```python
import importlib.util
from pathlib import Path
import pytest

# 加载 cc-android.py（文件名带连字符, 不能直接 import, 用 importlib）
_CC = Path(__file__).parent / "cc-android.py"
_spec = importlib.util.spec_from_file_location("cc_android", _CC)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

def test_route_has_points():
    pts = cc.load_route(r"C:\Users\Administrator\Desktop\SHANHAILIANCHENG.gpx")
    assert len(pts) >= 2          # 路线至少有起点终点
```

---

## 第四部分：标记（mark）—— 给用例贴标签

### 4.1 单个用例标记

```python
@pytest.mark.slow          # 贴个标签
def test_big_route():
    ...
```

### 4.2 整个文件标记（pytestmark）

你项目的 UI 脚本就是这么干的——一个标记管整个文件：

```python
import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(600), pytest.mark.order(1)]
#            ↑UI用例标签       ↑10分钟超时防卡死       ↑流程第1步
```

pytestmark 是特殊变量名，pytest 看到它就把这些标记应用到文件里所有用例。
可以写多个：列表形式。

### 4.3 用标记控制跑什么

```bash
python -m pytest -m ui            # 只跑带 ui 标记的
python -m pytest -m "not ui"      # 只跑不带 ui 标记的
python -m pytest -m "ui and order"  # 两个标记都带
```

项目里 conftest.py 的 RUN_UI 机制就是配合 ui 标记：
没设 RUN_UI=1 时，所有 ui 标记用例自动变成 SKIPPED（跳过），
这样不连手机时跑 pytest 不会报错。

### 4.4 顺序标记（pytest-order 插件）

```python
@pytest.mark.order(1)   # 第1步
@pytest.mark.order(5)   # 第5步
```

数字即顺序。改数字 = 调顺序。

---

## 第五部分：fixture —— 共享的东西

### 5.1 为什么需要 fixture

你的 4 个用例都要连 Appium。如果每个用例自己连、自己断：

```python
def test_a():
    driver = webdriver.Remote(...)   # 连一次
    ...操作...
    driver.quit()                    # 断一次

def test_b():
    driver = webdriver.Remote(...)   # 又连一次
    ...
```

问题：一台手机同时只能有一个 UiAutomator2 会话，第二个连会失败。

### 5.2 fixture 解决共享

conftest.py 里定义一次，所有用例自动拿到：

```python
@pytest.fixture(scope="session")
def driver():
    drv = webdriver.Remote(...)   # 流程开始连一次
    yield drv                     # 把 driver 交给用例
    drv.quit()                    # 流程结束统一断
```

用例怎么用？**参数名对上就行**：

```python
def test_gps_inject(driver):      # 参数叫 driver → pytest 自动注入
    driver.set_location(lat, lon, ele, speed=spd)
```

### 5.3 scope：fixture 活多久

| scope | 生命周期 |
|---|---|
| function（默认） | 每个用例都重新执行一次 |
| class | 每个类一次 |
| module | 每个文件一次 |
| session | 整个测试跑完才销毁 |

你的 driver 用 session —— 整个流程 4 步共享一个连接。

### 5.4 yield 是什么

```python
@pytest.fixture
def driver():
    ...准备...        # 用例执行前
    yield drv         # 把东西交给用例, 用例跑完回到这里
    ...清理...        # 用例执行后（即使用例失败也会执行）
```

yield 上面 = 准备，下面 = 清理。比 try/finally 干净。

---

## 第六部分：怎么写新用例（融入流程）

这是你最关心的——新脚本三步走：

### 第 1 步：复制模板

新建 `test_05_你的名字.py`：

```python
# test_05_xxx.py — 流程第5步: 描述
import pytest

pytestmark = [pytest.mark.ui, pytest.mark.timeout(600), pytest.mark.order(5)]

def test_xxx(driver=None):
    """描述 (pytest共享driver, 直跑自建)"""
    own = driver is None          # 判断是不是pytest注入的driver
    if own:                       # 直跑时自己连
        driver = webdriver.Remote("http://127.0.0.1:4723",
            options=UiAutomator2Options().load_capabilities(CAPS))
    try:
        # 你的 UI 操作, 用 driver 找元素点击
        ...
    finally:
        if own:                   # 共享时不quit, 留给fixture统一断
            driver.quit()
```

### 第 2 步：填 body

用 Appium 操作，从你的 app元素.txt 里抄元素 ID：

```python
    try:
        el = driver.find_element(AppiumBy.ID, "com.shiye.cyclingai.ride:id/mainIvRiding")
        el.click()
        assert el.is_displayed()   # 想验证什么就 assert 什么
    finally:
        if own:
            driver.quit()
```

### 第 3 步：调整其他文件的 order

想插在第 2 和第 3 步之间：
- 新文件写 `pytest.mark.order(3)`
- 原来 order(3) 的 test_navigation_flow.py 改成 `pytest.mark.order(4)`
- 原来 order(4) 的 test_map_download.py 改成 `pytest.mark.order(5)`

数字即顺序，改数字就是调顺序。

### 想改已有步骤的行为？

- 改注入时长：test_gps_inject.py 顶部 `INJECT_SECONDS = 60`
- 换 GPX 路线：test_gps_inject.py 里 `cfg.gpx_file = r"新路径"`
- 某步失败想继续：跑的时候去掉 `-x`

---

## 第七部分：常用命令速查

```bash
python -m pytest                     # 跑全部
python -m pytest -v                  # 详细显示每个用例
python -m pytest -q                  # 安静模式, 只显示 . F s
python -m pytest test_gps_inject.py  # 只跑某个文件
python -m pytest -k inject           # 按名字过滤
python -m pytest -m ui               # 按标记过滤
python -m pytest -x                  # 一挂就停(失败即停)
python -m pytest --collect-only      # 只看收集了哪些用例, 不执行
python -m pytest --html=report.html  # 出HTML报告
python -m pytest --maxfail=2         # 最多允许2个失败
```

结果符号：`.` 通过，`F` 失败，`s` 跳过，`E` 报错（用例本身崩了）。

---

## 第八部分：常见坑（都是你项目里会遇到的）

**坑1：在 Python Console 里敲 shell 命令**
Python Console 是解释器，只能跑 Python 代码。
要跑 pytest 用 Terminal（底部标签栏切换），
或者 Console 里：`import pytest; pytest.main(["-m","ui","-v"])`

**坑2：PowerShell 设置环境变量**
```powershell
$env:RUN_UI="1"; python -m pytest -m ui -v    # ✅ 对
RUN_UI=1 python -m pytest -m ui -v            # ❌ 这是linux语法
```

**坑3：用例参数名和 fixture 撞名**
pytest 按参数名注入 fixture。你写了 `def test_x(driver=None)`，
pytest 看到 driver 就注入 conftest 的 fixture —— 这正是我们要的。
但注意：自己定义函数时别用 driver 这个名字干别的事。

**坑4：断言别用 == 比浮点数**
用 `pytest.approx`，教程 3.2 讲过。

**坑5：跑了没反应 / 全 skipped**
没设 RUN_UI=1，或 adb 没连真机。conftest 会跳过所有 ui 用例。

**坑6：两台设备/Appium 会话冲突**
全流程只能有一个 driver（conftest session fixture），
别在脚本里自己 webdriver.Remote 再连一个。

---

## 第九部分：学习路径建议

1. 先跑熟现有流程：RUN_UI=1 python -m pytest -m ui -v
2. 自己加一个最简单的用例（test_hello.py 级别）
3. 试着把某个现有脚本的 order 改一下，看顺序变化
4. 写一个你自己的流程步骤（第六部分模板）
5. 需要时再学参数化（@pytest.mark.parametrize）、fixture 传参等进阶

进阶参考：https://docs.pytest.org/ （英文官方文档）

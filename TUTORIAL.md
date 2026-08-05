# PythonProjectKK 接入 pytest + CI/CD 教程

> 目标：让这个 GPS 注入 + Appium UI 测试项目有一套标准的自动化测试和持续集成流程。
> 读完这篇，你会知道每个文件是干嘛的、怎么跑、怎么扩展、怎么让 GitHub 自动帮你跑测试。

---

## 一、项目现状（加入前 vs 加入后）

| 文件 | 加入前 | 加入后 |
|---|---|---|
| test_map_download.py / test_navigation_flow.py / test_plan_full_flow.py | 只能 `python xxx.py` 手动跑 | 既是 pytest 用例，也能 `python xxx.py` 直跑 |
| cc-android.py | 纯脚本，改坏了没人知道 | 核心函数被 test_unit_gps.py 单测保护 |
| 没有 | 无依赖清单 | requirements.txt 统一管依赖 |
| 没有 | 无测试配置 | pytest.ini + conftest.py |
| 没有 | 无 CI | .github/workflows/ci.yml 每次 push 自动跑测试 |

核心思想一句话：**能单元测试的逻辑（GPS 计算/解析）进 CI 自动跑，依赖真机的 UI 用例留在本地手动跑。**

---

## 二、pytest 篇

### 1. 装 pytest（只装一次）

```bash
pip install -r requirements.txt   # 或单独: pip install pytest
```

### 2. pytest 的规则：文件 + 函数都要 test_ 开头

```
test_xxx.py 文件  →  里面 def test_yyy() 函数  →  pytest 自动收集
```

你的 3 个 UI 文件早就符合了（test_map_download 等），所以 pytest 直接能认。

### 3. 用标记区分"UI用例"和"纯逻辑用例"

每个 UI 脚本顶部加了一行：

```python
import pytest

pytestmark = pytest.mark.ui  # 整文件标记为UI用例
```

`pytestmark` 是 pytest 的"文件级标记"，一个标记就给整个文件的所有用例生效。

### 4. conftest.py：没人管 UI 用例就跑

conftest.py 是 pytest 的全局钩子文件（自动加载，不用 import）：

```python
def pytest_collection_modifyitems(config, items):
    run_ui = os.environ.get("RUN_UI") == "1" and _has_device()
    if run_ui:
        return
    skip = pytest.mark.skip(reason="未设置RUN_UI=1或无真机, 跳过UI用例")
    for item in items:
        if "ui" in item.keywords:
            item.add_marker(skip)
```

逻辑：没设环境变量 `RUN_UI=1` 或 adb 没连真机 → 给所有带 ui 标记的用例打 skip。
所以本地/CI 跑 pytest 不会因为没手机而报错。

### 5. test_unit_gps.py：纯逻辑单测（重点）

测的是 cc-android.py 里不碰手机的三块：

```python
# 动态加载 cc-android.py (文件名带连字符"-"不能直接 import, 用 importlib)
import importlib.util
from pathlib import Path

_CC = Path(__file__).parent / "cc-android.py"
_spec = importlib.util.spec_from_file_location("cc_android", _CC)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)
```

| 测试函数 | 测什么 | 关键点 |
|---|---|---|
| test_dist_m_one_degree_lat | 距离公式 | 纬度差0.01度≈1111.95米，用 `pytest.approx` 浮点比较 |
| test_dist_m_symmetric | 距离公式 | 对称性：A→B 和 B→A 距离相等 |
| test_load_route_points | GPX解析 | `tmp_path` fixture 自动建临时GPX文件，用完即删 |
| test_player_two_points | 插值播放器 | 2点路线→约22个子步、终点坐标、速度±5%、爬升累计 |
| test_player_descend_no_climb | 插值播放器 | 下坡不累计爬升 |

浮点比较不要用 `==`，用 `pytest.approx`：

```python
assert d == pytest.approx(1111.95, rel=0.001)   # rel=允许相对误差0.1%
```

临时文件用内置 fixture `tmp_path`（pytest 自动清理，不用自己删）：

```python
def test_load_route_points(tmp_path):
    p = tmp_path / "route.gpx"          # 临时目录下的文件
    p.write_text('<gpx>...</gpx>')      # 写入测试数据
    pts = cc.load_route(str(p))
```

### 6. 常用跑法（都在项目根目录）

```bash
pytest                    # 全跑: 单测过 + UI跳过
pytest -v                 # 详细模式, 显示每个用例
pytest test_unit_gps.py   # 只跑单测文件
pytest -m "not ui"        # 显式排除UI用例 (CI里就是这条)
pytest -k dist            # 按名字过滤: 只跑名字带dist的
pytest --html=report.html # 装pytest-html后生成HTML报告
pytest -q                 # 安静模式, 只显示 . 和 F
```

### 7. 以后新代码怎么加测试（你的场景）

cc-android.py 里新增了函数？直接在 test_unit_gps.py 加一个 test_ 函数：

```python
def test_new_function():
    result = cc.新函数(参数)
    assert result == 期望值
```

记住原则：**纯计算、不碰手机/网络/文件的函数才值得单测**。
Appium 注入那部分（Injector）依赖真机，交给 UI 用例测。

---

## 三、CI/CD 篇

### 1. CI/CD 是什么

- **CI（持续集成）**：每次你 push 代码到仓库，服务器自动拉代码、装依赖、跑测试，有问题马上红。
- **CD（持续部署）**：测试通过后自动发布（本项目暂时用不到，先做 CI）。

作用：代码质量闸门。改坏了自己没发现？CI 会拦住。

### 2. GitHub Actions 三个概念

```
Workflow (工作流)  = .github/workflows/ci.yml 一个文件
  └── Job (任务)   = 一台干净的 Ubuntu 虚拟机
        └── Step (步骤) = 依次执行: 拉代码→装Python→装依赖→跑测试
```

### 3. ci.yml 逐行解析

```yaml
name: CI                    # 工作流名字, Actions页面显示用

on:
  push:                     # 触发条件: 推代码时
    branches: [master, main]
  pull_request:             # 提PR时也触发

jobs:
  test:                     # 任务名
    runs-on: ubuntu-latest  # 在Ubuntu虚拟机上跑
    steps:
      - uses: actions/checkout@v4          # 把你的代码拉进虚拟机
      - uses: actions/setup-python@v5      # 装Python
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt  # 装依赖
      - run: pytest -m "not ui" -v            # 跑测试, 排除UI
```

注意最后一行：CI 机器上没有你的 Android 真机，所以 `-m "not ui"` 只跑单测。
UI 用例在 conftest.py 里也会被自动跳过（双保险）。

### 4. 从零到跑通 CI（照做一遍）

**第一步：初始化 git（你的仓库还没 commit）**

```bash
cd C:\Users\Administrator\PycharmProjects\PythonProjectKK
git add .gitignore requirements.txt pytest.ini conftest.py cc-android.py cc-ios.py \
        test_map_download.py test_navigation_flow.py test_plan_full_flow.py test_unit_gps.py \
        .github
git commit -m "接入pytest: 单测+UI用例标记+CI工作流"
```

> 注意：`.idea/` 已被 .gitignore 忽略，不会进仓库。如果之前 add 过，先 `git rm -r --cached .idea`。

**第二步：在 GitHub 建仓库**

1. 浏览器打开 https://github.com/new
2. Repository name 填 `PythonProjectKK`（或随便）
3. 不要勾选 "Add a README"（避免和本地冲突）
4. 创建后按页面提示添加远程地址并推送：

```bash
git remote add origin https://github.com/你的用户名/PythonProjectKK.git
git branch -M main
git push -u origin main
```

**第三步：看 CI 结果**

1. 打开仓库页面 → 顶部 Tab 点 **Actions**
2. 能看到 "CI" 工作流正在跑，黄色=进行中，绿色=通过，红色=失败
3. 点进去看每个 step 的日志，失败时日志会显示具体哪个用例挂了

以后每次 push，GitHub 都会自动重新跑一遍。仓库页面会出现绿色 ✔ 或红色 ✘ 小图标。

### 5. 国内用不了 GitHub？Gitee 备选

Gitee 也支持 Actions（叫 Gitee Go），配置文件名不同：

```yaml
# .gitee/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest -m "not ui" -v
```

Gitee 建仓库后，推送方式跟 GitHub 一样，只是地址换成 `https://gitee.com/你的用户名/PythonProjectKK.git`。

---

## 四、常见问题

**Q: 跑 pytest 报 `ModuleNotFoundError: No module named 'appium'`**
A: 没装依赖。`pip install -r requirements.txt`。
（test_unit_gps.py 加载 cc-android.py 时顶层 import 了 appium）

**Q: 我想连真机跑 UI 用例**
A: 先启动 Appium Server，手机连 adb，然后：

```bash
RUN_UI=1 pytest -m ui -v
```

Windows PowerShell 里写 `$env:RUN_UI="1"` 再跑 pytest。

**Q: UI 用例跑起来报 instrumentation 崩溃**
A: 这是 Appium/uiautomator2 环境问题（手机端 server APK 没装好），
和 pytest 无关——你用 `python test_xxx.py` 直跑也会报同样的错。
先解决 Appium 环境，再跑。

**Q: pytest 有缓存目录 .pytest_cache 和 __pycache__ 会进 git 吗**
A: 不会，.gitignore 已忽略。

**Q: cc-ios.py 怎么加单测**
A: 它和 cc-android.py 结构一致（同样的函数名）。照 test_unit_gps.py 的写法，
在加载处加一个 `cc_ios` 模块加载，补同样的断言即可。

---

## 五、一图流

```
本地开发                         GitHub (CI)
───────                         ──────────
写代码                          push 代码
  ↓                                ↓
python test_unit_gps.py        Actions 自动跑:
  ↓                          pip install -r requirements.txt
连真机时:                     pytest -m "not ui" -v
RUN_UI=1 pytest -m ui            ↓
  ↓                          全绿=可合并 / 红=看日志修
日常回归: pytest
```

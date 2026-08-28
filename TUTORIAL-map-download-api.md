# 地图下载 API 连通性测试教程（test_map_download_api.py · 零基础版）

> 这份教程假设你**完全没学过 pytest**（只看懂 Python 基础就行）。
> 每个重要知识点讲完，都跟一个 **✏️ 小练习**（带答案、分步骤引导），
> 先自己做，再点开答案对照。
> 看完你会：
> 1. 知道 pytest 怎么工作、怎么跑、怎么看结果
> 2. 懂这个脚本在验证什么、接口协议长什么样
> 3. 看得懂每一行代码（pytest 的部分逐个解释）
> 4. 知道原版 82 行里哪些是冗余、精简版 58 行怎么改的
> 5. 会自己写类似的"接口连通性验证"脚本

---

## 零、pytest 到底是个啥（没学过也能看懂）

**一句话：pytest 是 Python 的测试框架，你只管写"检查对不对"的函数，它自动帮你找到、跑起来、告诉你结果。**

它的规矩只有两条：
- 文件名以 `test_` 开头（如 `test_map_download_api.py`）→ pytest 会自动找到它
- 文件里函数名以 `test_` 开头（如 `test_map_download_channel`）→ pytest 会自动执行它

### 不学 pytest，你原来会怎么写？

```python
# 传统写法：手动调函数、手动判断、手动打印
def check_map_api():
    r = requests.get(API_URL, params=...)
    if r.status_code == 200:
        print("接口OK")
    else:
        print("接口挂了")

check_map_api()          # 还得自己记得调它
# 换了参数又要复制一份再改……代码越写越乱
```

### 用 pytest 怎么写？

```python
def test_map_download_channel(country, lat, lon, distance):
    r = requests.get(API_URL, params={"lat": lat, "lon": lon, "distance": distance}, timeout=30)
    assert r.status_code == 200, "接口非200"    # assert 一行搞定
    assert r.json().get("code") == 200
```

pytest 的好处：
- **不用自己调函数**——它扫描所有 `test_` 函数自动跑
- **不用自己打印结果**——`assert` 不成立就报 FAILED，成立就 PASSED
- **一组数据跑一次**——参数化，不用复制函数（下面第三节讲）

**✏️ 小练习 A（pytest 的规矩）**

**步骤 1**：下面 4 个函数，你觉得 pytest 会执行哪几个？先自己圈出来：
```python
def check_map_api(): ...      # ①
def test_map_api(): ...       # ②
def map_api_test(): ...       # ③
def test_launch_app(): ...    # ④
```

**步骤 2**：新建一个临时文件 `exercise_a.py`，把这 4 个函数照抄进去（函数体写 `pass` 就行），然后运行：
```bash
.venv\Scripts\python -m pytest exercise_a.py --collect-only -q
```
`--collect-only` 只列出"pytest 准备执行哪些用例"，不真跑。看输出，和你猜的一致吗？

<details><summary>👀 参考答案</summary>

pytest 会执行 **② 和 ④**（函数名以 `test_` 开头）。① 是 `check_` 开头不会跑；③ `map_api_test` 以 `test` 结尾，**那是文件名的规则**（`xxx_test.py`），函数名不适用。

`--collect-only` 输出里只会出现 `test_map_api` 和 `test_launch_app` 两个函数。练完删掉 `exercise_a.py`。
</details>

### 怎么装、怎么跑？

依赖就 3 个（项目的 `requirements.txt` 里已有，装了 .venv 就不用管）：

```bash
pip install pytest pytest-timeout requests
```

运行（在项目目录下）：

```bash
cd C:\Users\Administrator\PycharmProjects\PythonProjectKK
.venv\Scripts\python -m pytest test_map_download_api.py -v
```

- `.venv\Scripts\python` 是项目的虚拟环境解释器（装好的依赖都在里面）
- `-m pytest` = 用 python 跑 pytest
- `-v` = verbose，把每个用例的名字和结果都列出来

**✏️ 小练习 B（自己跑一次）**

**步骤 1**：先自己把"运行原版测试"的命令写出来（要求：进入项目目录、用虚拟环境、显示详细信息）：
```
（写在这里）
```

**步骤 2**：照着你写的命令跑一遍（会真实请求接口 + 下载三国地图，约 20~30 秒）。看到结尾是 `3 passed` 就成功了。

<details><summary>👀 参考答案</summary>

```bash
cd C:\Users\Administrator\PycharmProjects\PythonProjectKK
.venv\Scripts\python -m pytest test_map_download_api.py -v
```

跑完结尾应是 `3 passed in ~20s`。如果看到 `failed`，往上翻找 `AssertionError` 附近是哪条断言——先别慌，第三节会教你怎么读。
</details>

### 结果怎么看？

跑完你会看到类似：

```
test_map_download_api.py::test_map_download_channel[中国-兰州] PASSED [ 33%]
test_map_download_api.py::test_map_download_channel[日本-札幌] PASSED [ 66%]
test_map_download_api.py::test_map_download_channel[韩国-大田] PASSED [100%]

============================= 3 passed in 20.21s ==============================
```

- 每个用例一行：`文件名::函数名[哪组数据] 结果`
- 结尾一行是总结：`3 passed` / `1 failed` / `1 skipped`
- 某条 `assert` 没过 → 那个用例变 FAILED，pytest 会把**断言那行的值**打出来帮你排查（这就是为什么断言消息里不用重复写值，第四节讲）

**✏️ 小练习 C（读结果）**

对照上面那段真实输出，回答：
1. 这个文件里一共收集了几个用例？
2. `[中国-兰州]` 是什么？它来自代码里哪个地方？
3. 如果有一行变成 `FAILED`，总结行大概会怎么写？

<details><summary>👀 参考答案</summary>

1. **3 个**（中国-兰州、日本-札幌、韩国-大田）。
2. 是"哪组数据"的标识，来自 `COUNTRIES` 里每行的 `id="中国-兰州"`（第三节会细讲）。
3. 总结行会变成类似 `2 passed, 1 failed in 20.21s`，失败的用例上方会有 `AssertionError` 和值对比。
</details>

## 一、这个脚本在干嘛

一句话：**验证"请求地图下载接口 → 拿到 CDN 链接 → 能下载 → 文件格式对"这条链路通不通。**

```
本脚本(纯HTTP)                    App(真机)
    │                                 │
    ├─ 请求下载接口 ──lat/lon/distance─▶ 后端
    │  ◀── 返回 CDN url ────────────────┤
    ├─ 下载地图文件 ◀──────────────────▶ CDN
    ├─ 校验: 非空 + 文件头 HUD4 + 大小范围
    └─ 删掉临时文件
```

几个设计决策（都是为什么）：
- **中日韩三国**：App 支持三国地图（骑迹 GPS），三组坐标参数化跑同一套代码
- **坐标用 WGS-84**：接口要求 WGS-84 标准系，不是高德 GCJ-02。如果地图显示有 ~500m 偏移，就是坐标系不匹配
- **下载完就删**：只验证连通性，不留文件占磁盘
- **不需要真机**：纯 HTTP 请求，电脑直接跑（这也是它和 test_map_download.py 的本质区别——那个是 Appium 真机 UI 流程）

## 二、接口协议（先看懂要测什么）

```
GET http://cybersight.zhxxh.cn/v2/map/roadnet/download.bin?lat=36.0611&lon=103.8343&distance=30000
```

响应是 JSON：
```json
{
  "code": 200,
  "status": true,
  "data": {
    "url": "https://cdn-roadnet.cshud.com/ar/map?token=..."
  }
}
```

`data.url` 就是 CDN 上的地图文件地址，拿到它再下载。

**校验思路（关键学习点：验"特征"不验"死值"）**：
| 校验项 | 为什么这么验 |
|--------|-------------|
| 文件大小在 0.1MB~100MB | 三国数据量不同是特性，写死具体大小反而错 |
| 文件头 == `b"HUD4"` | 确认是真地图文件，不是下载到 HTML 错误页 |
| Content-Length 只警告不断言 | 地图是动态生成的，声明值和实际值常不一致（已知现象） |

**✏️ 小练习 D（亲手请求一次接口）**

**步骤 1**：打开命令行，运行：
```bash
curl "http://cybersight.zhxxh.cn/v2/map/roadnet/download.bin?lat=36.0611&lon=103.8343&distance=30000"
```
（curl 是命令行发 HTTP 请求的工具，Windows 10+ 自带）

**步骤 2**：对照教程里给出的 JSON 结构，找出返回里这几个字段，写下来：
- `code` 的值：____
- `status` 的值：____
- `data.url` 是不是 `https://` 开头：____

**步骤 3**：再试一次，把 `distance` 改成 `1000000`（一千万米=夸张半径），看返回的 url 有没有变化？想想为什么。

<details><summary>👀 参考答案</summary>

- `code` 是 `200`，`status` 是 `true`，`data.url` 是 `https://cdn-roadnet.cshud.com/ar/map?token=...`。
- 把 `distance` 改大后 url（尤其 token）通常会变——因为地图是按"中心点+半径"动态生成的，参数不同生成的地图不同。这也解释了代码里"验特征不验死值"的思路。

练完后你再看测试代码第一段断言（`code == 200`、`status is True`、`url.startswith("https://")`），是不是完全对上了？
</details>

## 三、逐块拆解（pytest 部分逐个讲）

### 1. 参数化：为什么写 COUNTRIES 而不是 3 个函数

**不参数化**的话，你得写 3 个几乎一模一样的函数：

```python
def test_兰州():
    resp = requests.get(API_URL, params={"lat": 36.0611, "lon": 103.8343, "distance": 30000}, ...)
    ... 下载、校验 ...

def test_札幌():
    resp = requests.get(API_URL, params={"lat": 43.0618, "lon": 141.3545, "distance": 30000}, ...)
    ... 同一坨代码又抄一遍 ...
```

改一行逻辑要改 3 处，代码冗余。**参数化**就是"同一套代码，换数据跑 N 次"：

```python
COUNTRIES = [
    pytest.param("中国兰州", 36.0611, 103.8343, 30000, id="中国-兰州"),
    pytest.param("日本札幌", 43.0618, 141.3545, 30000, id="日本-札幌"),
    pytest.param("韩国大田", 36.3504, 127.3845, 30000, id="韩国-大田"),
]

@pytest.mark.parametrize("country,lat,lon,distance", COUNTRIES)
def test_map_download_channel(country, lat, lon, distance):
    ...
```

逐字拆这一行：

```python
@pytest.mark.parametrize("country,lat,lon,distance", COUNTRIES)
```

- `@` 开头 = **装饰器**，包在函数外面给函数"加功能"。读作：下面这个函数，按 COUNTRIES 里的数据跑多次
- 第一个参数 `"country,lat,lon,distance"` = 逗号分隔的**参数名列表**，要和函数签名一一对应
- 第二个参数 `COUNTRIES` = **数据列表**，里面每一组（一行 `pytest.param`）就是一次运行
- 运行时，第 1 组数据会作为 `country="中国兰州", lat=36.0611, lon=103.8343, distance=30000` 传进函数

`pytest.param(..., id="中国-兰州")` 里的 `id` 是**给测试报告看的名字**。不加 id，测试名会变成 `中国兰州-36.0611-103.8343-30000` 一长串（pytest 默认把参数值拼进去）；加了 id，报告里就是清爽的 `[中国-兰州]`。

**✏️ 小练习 E（参数化）**

**步骤 1**：判断——`@pytest.mark.parametrize("a,b", [(1,2), (3,4), (5,6)])` 下面的测试函数会跑几次？

**步骤 2**：给 `COUNTRIES` 加一行泰国曼谷（纬度 13.7563，经度 100.5018，半径 30000），id 用 `"泰国-曼谷"`。照着前几行的格式写。

**步骤 3**：只跑泰国这组验证一下（不用等 3 国全跑）：
```bash
.venv\Scripts\python -m pytest test_map_download_api_lean.py -k 泰国 -v
```
`-k 泰国` 的意思是"只跑名字里含'泰国'的用例"。看输出确认只跑了 1 个。

<details><summary>👀 参考答案</summary>

**步骤 1**：**3 次**（3 组数据，每组跑一次。6 是"参数个数×组数"的误解）。

**步骤 2**：在 `COUNTRIES` 列表里加一行：
```python
    pytest.param("泰国-曼谷", 13.7563, 100.5018, 30000, id="泰国-曼谷"),
```

**步骤 3**：`-k 泰国` 后输出应该只有 1 条用例，名字类似 `test_map_download_channel[泰国-曼谷]`。练完记得把泰国这行删掉（或留着，无所谓）。
</details>

### 2. assert：怎么算"通过"？

`assert` 是 Python 自带关键字：**后面这个条件为真 → 继续跑；为假 → 直接报错，这条用例 FAILED。**

```python
assert resp.status_code == 200, "接口非200"
#      └──── 条件 ────┘   └── 失败时显示的消息 ──┘
```

失败时 pytest 会打印类似：

```
E   AssertionError: 接口非200
E   assert 500 == 200
E    +  where 500 = <Response [500]>.status_code
```

看到了吗？**pytest 自己会显示表达式里每个值**（500 是哪来的），所以断言消息里不需要再拼一遍值（第四节第 4 条就是精简这个）。

**✏️ 小练习 F（assert）**

**步骤 1**：填空——断言"接口返回状态码是 200"：
```python
assert resp.status_code == ___, "接口非200"
```

**步骤 2**：故意改错制造一次失败。把精简版里第一处断言改成 `assert resp.status_code == 500`（故意写成 500），然后只跑一国的 `-k 中国`：
```bash
.venv\Scripts\python -m pytest test_map_download_api_lean.py -k 中国 -v
```

**步骤 3**：观察输出里的 `AssertionError` 和 `assert 200 == 500` 这一行，对照教程的例子，确认自己看得懂。**看完立刻把断言改回 `== 200`**。

<details><summary>👀 参考答案</summary>

**步骤 1**：填 `200`。

**步骤 2-3**：故意改错后，输出里会出现：
```
E   AssertionError: [中国-兰州] 接口异常: {...}
E   assert (200 == 500)
```
`(200 == 500)` 就是 pytest 的"断言内省"——左边是实际值 200，右边是你写的期望 500。**故意弄挂一次看报错，是学 pytest 最快的方式**。改回来后跑一遍确认 `3 passed`。
</details>

### 3. 常量区：pytestmark 和 timeout 是什么

```python
TIMEOUT_API = 30       # 接口请求超时(秒)
TIMEOUT_DL = 120       # 下载超时(秒)
pytestmark = [pytest.mark.timeout(300)]  # 每国 5 分钟上限
```

- `TIMEOUT_API/TIMEOUT_DL` 是 `requests.get(timeout=...)` 用的，控制**单次请求/下载**的等待上限
- `pytestmark` 是一个**特殊变量名**：pytest 规定，写在文件顶部的 `pytestmark` 会被当成"这个文件里所有用例都适用的标记"
- `pytest.mark.timeout(300)` 是 `pytest-timeout` 插件提供的**标记**：整个用例（含下载）超过 300 秒就强制杀掉，防网络卡死挂一晚上
- 所以是**两层超时**：请求 30s、下载 120s、整条用例兜底 300s

**✏️ 小练习 G（timeout）**

**步骤 1**：判断——文件顶部的 `pytestmark = [pytest.mark.timeout(300)]` 作用范围是？（A 只对第一个用例 / B 整个文件所有用例 / C 所有测试文件）

**步骤 2**：验证一下它真的有用：把精简版里 timeout 从 `300` 临时改成 `1`（1 秒），跑 `-k 中国`，看会发生什么。

**步骤 3**：看完效果，改回 `300`。想想：如果没这行，网络卡住时测试会怎样？

<details><summary>👀 参考答案</summary>

**步骤 1**：**B**。`pytestmark` 写在哪个文件就对哪个文件的全部用例生效（不是全局）。

**步骤 2**：改成 1 秒后，用例会在下载地图时被强制中断，报 `TimeoutError`（pytest-timeout 把用例杀掉）——接口请求和下载明明正常，也会超时失败。这就是"用例级兜底"在起作用。

**步骤 3**：没有它，网络卡住时测试会一直挂到单请求超时甚至更久，整个流程可能等几十分钟。所以 `timeout` 是"保命"标记。
</details>

### 4. _download：流式下载（requests 知识点，与 pytest 无关）

```python
def _download(url):
    with requests.get(url, stream=True, timeout=TIMEOUT_DL) as r:
        r.raise_for_status()
        dest = tempfile.mktemp(suffix=".bin")
        size = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
        return dest, size
```

- `stream=True` + `iter_content()` 逐块(64KB)写盘 → **大文件不占内存**。不用 stream 的话 requests 会一次性把整个文件读进内存，几百 MB 地图直接撑爆
- `raise_for_status()`：HTTP 非 200 直接抛异常，不用自己写 if 判断
- 返回 `(文件路径, 实际字节数)` 给调用方做校验

**✏️ 小练习 H（流式下载）**

**步骤 1**：判断——下载 500MB 的地图，`stream=True` 时内存大约占多少？（A 约 500MB / B 只有几十 KB 的缓冲 / C 跟文件大小无关，永远是 0）

**步骤 2**：`iter_content(chunk_size=65536)` 里的 `65536` 是什么单位？（提示：字节 → 等于多少 KB？）

**步骤 3**：思考——把 `chunk_size` 改成 `1` 会怎样？改成 `10*1024*1024`（10MB）呢？哪个更快、哪个更省内存？

<details><summary>👀 参考答案</summary>

**步骤 1**：**B**。流式下载每次只处理一个 chunk（默认 64KB 缓冲），文件多大都不占内存。

**步骤 2**：**字节**。`65536` 字节 = 64KB。

**步骤 3**：chunk 越小越省内存但磁盘写入次数多（慢）；越大越快但单块占内存。64KB~1MB 是常用平衡点。这也是"精简版"保留这段代码不改的原因——它就是标准写法。
</details>

### 5. 测试函数三步走 + try/finally

```python
@pytest.mark.parametrize("country,lat,lon,distance", COUNTRIES)
def test_map_download_channel(country, lat, lon, distance):
    # 1. 接口 → CDN 链接
    t0 = time.time()
    resp = requests.get(API_URL, params={"lat": lat, "lon": lon, "distance": distance}, timeout=TIMEOUT_API)
    body = resp.json()
    assert resp.status_code == 200 and body.get("code") == 200 and body.get("status") is True, ...
    url = body.get("data", {}).get("url", "")
    assert url.startswith("https://"), ...

    # 2. 下载 → 校验 → 清理
    dest, size = _download(url)
    try:
        with open(dest, "rb") as f:
            signature = f.read(4)
        assert signature == b"HUD4", ...
        assert SIZE_MIN <= size <= SIZE_MAX, ...
        print(...)
    finally:
        os.remove(dest)
```

- `params={...}` 是 requests 传查询参数的标准方式（自动 URL 编码）
- `body.get("data", {}).get("url", "")` 双层 get，避免 `data` 为 None 时 KeyError 崩掉
- `try/finally`：**finally 里的代码无论成败一定执行**——临时文件必须删，写在这里最保险（没 try 的话断言失败会直接跳出，文件就留在磁盘上了）

**✏️ 小练习 I（try/finally）**

**步骤 1**：找出下面代码的问题（这段是"错误示范"）：
```python
def test_map_download_channel(country, lat, lon, distance):
    dest, size = _download(url)
    with open(dest, "rb") as f:
        signature = f.read(4)
    assert signature == b"HUD4", f"[{country}] 文件头异常"
    os.remove(dest)   # 删除临时文件
```
想想：如果 `assert` 失败，`os.remove(dest)` 会执行吗？临时文件会怎样？

**步骤 2**：把这段改对（用 try/finally 包住校验和删除），改完对照精简版第 2 步的写法确认。

**步骤 3**：验证——把校验故意改错（`assert signature == b"XXXX"`），跑 `-k 中国`，然后检查系统临时目录（`%TEMP%`）里有没有残留的 `.bin` 文件。应该没有——因为 finally 保证了删除。

<details><summary>👀 参考答案</summary>

**步骤 1**：`assert` 失败时函数直接抛异常跳出，`os.remove(dest)` **不会执行** → 临时文件残留在磁盘上。跑多了会攒一堆垃圾文件。

**步骤 2**：正确写法就是把"校验"放 `try` 里、`os.remove(dest)` 放 `finally` 里（就是精简版的样子）。

**步骤 3**：`%TEMP%` 里没有 `.bin` 残留 = try/finally 生效。**练完把故意改错的断言改回来。**
</details>

## 四、精简分析（原版 82 行 → 精简版 58 行）

| # | 原版写法 | 为什么冗余 | 精简后 |
|---|---------|-----------|--------|
| 1 | 头部注释 6 行 | 核心就"链路 + 校验思路"两点，其余是过程记录 | 2 行 |
| 2 | 每次下载都 `os.makedirs(DOWNLOAD_DIR, exist_ok=True)` | 系统 Downloads 必然存在，且重复调用 3 次 | 删除 |
| 3 | 下载到系统 Downloads 目录 | "用完即删"却去动用户下载目录，语义不符 | `tempfile.mktemp` 临时文件 |
| 4 | 断言消息拼值，如 `f"非200: {resp.status_code}"` | 小练习 F 讲过：pytest 失败时**自己会显示表达式值** | 消息只留 `[{country}] 定位词` |
| 5 | 3 处 print + 1 处警告 | 验证脚本输出 1 行总结就够 | 合并 1 处 print |
| 6 | `clen` 警告逻辑（约 8 行） | 注释自己都写"实测与声明常不一致"=已知现象，警告无行动价值 | 删除 |
| 7 | 魔法数 `0.1*1024*1024` / `100*1024*1024` | 断言里重复出现，改范围要改两处 | 提成 `SIZE_MIN/SIZE_MAX` 常量 |
| 8 | 注释"下载到项目downloads目录" | **与实际代码不符**（实际是系统下载目录），误导 | 修正 |

**为什么这些保留不精简**：
- `pytest.param + id`：报告可读性，去掉测试名变丑
- `b"HUD4"` 文件头校验：核心断言，防下载到 HTML 错误页
- `try/finally`：清理保障，结构不能省
- `stream=True + iter_content`：大文件不占内存的正确姿势

**✏️ 小练习 J（找冗余）**

**步骤 1**：下面这段"故意写得很啰嗦"的代码，找出至少 3 处可精简的点：
```python
# 下载地图文件到系统下载目录, 下载完就删除, 不占磁盘空间
import os, requests
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)          # ①

r = requests.get(url, stream=True, timeout=120)
r.raise_for_status()
clen = int(r.headers.get("Content-Length", 0))    # ②
size = 0
dest = os.path.join(DOWNLOAD_DIR, "map.bin")
with open(dest, "wb") as f:
    for chunk in r.iter_content(chunk_size=65536):
        if chunk:
            f.write(chunk)
            size += len(chunk)
if clen and clen != size:                          # ③
    print(f"警告: Content-Length={clen} 实际={size}, 动态地图差异正常")
assert size > 0, "下载为空"
print("接口OK, 下载完成")                          # ④
```

**步骤 2**：对照第四节表格里的 8 条精简点，看你找的和表格对不对得上。

<details><summary>👀 参考答案</summary>

至少这 4 处（对应表格 #2/#3/#6/#5）：
- **①** `os.makedirs(...)`：下载到系统 Downloads 却"用完即删"，语义不符且 Downloads 必然存在 → 换成 `tempfile.mktemp()` 或直接删
- **②③** `clen` 获取 + 不一致警告：已知现象、无行动价值 → 整段删
- **④** print：验证脚本一行总结即可，过程 print 都是噪音

这正好是原版精简的核心思路：**删掉"重复动作、已知现象的警告、多余打印"，保留断言和清理**。
</details>

## 五、精简版完整代码（test_map_download_api_lean.py）

```python
# test_map_download_api_lean.py — 地图下载接口通道测试（精简版）
# 链路: 请求接口 → 拿CDN链接 → 下载 → 校验文件头 → 删除。纯网络, 不需真机。
import os
import tempfile
import time

import pytest
import requests

API_URL = "http://cybersight.zhxxh.cn/v2/map/roadnet/download.bin"
TIMEOUT_API, TIMEOUT_DL = 30, 120                      # 接口/下载超时(秒)
SIZE_MIN, SIZE_MAX = 0.1 * 1024**2, 100 * 1024**2      # 合理大小范围(字节)

# 坐标是 WGS-84（接口要求）, 不是高德 GCJ-02; 二三线城市数据量小下载快
COUNTRIES = [
    pytest.param("中国-兰州", 36.0611, 103.8343, 30000, id="中国-兰州"),
    pytest.param("日本-札幌", 43.0618, 141.3545, 30000, id="日本-札幌"),
    pytest.param("韩国-大田", 36.3504, 127.3845, 30000, id="韩国-大田"),
]
pytestmark = [pytest.mark.timeout(300)]  # 每国 5 分钟上限


def _download(url):
    """流式下载到临时文件, 返回 (文件路径, 实际字节数)"""
    with requests.get(url, stream=True, timeout=TIMEOUT_DL) as r:
        r.raise_for_status()  # 非200直接抛
        dest = tempfile.mktemp(suffix=".bin")
        size = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
        return dest, size


@pytest.mark.parametrize("country,lat,lon,distance", COUNTRIES)
def test_map_download_channel(country, lat, lon, distance):
    # 1. 接口 → CDN 链接
    t0 = time.time()
    resp = requests.get(API_URL, params={"lat": lat, "lon": lon, "distance": distance},
                        timeout=TIMEOUT_API)
    body = resp.json()
    assert resp.status_code == 200 and body.get("code") == 200 \
        and body.get("status") is True, f"[{country}] 接口异常: {body}"
    url = body.get("data", {}).get("url", "")
    assert url.startswith("https://"), f"[{country}] CDN链接异常"

    # 2. 下载 → 校验 → 清理
    dest, size = _download(url)
    try:
        with open(dest, "rb") as f:
            signature = f.read(4)
        assert signature == b"HUD4", f"[{country}] 文件头异常: {signature!r}"
        assert SIZE_MIN <= size <= SIZE_MAX, f"[{country}] 大小异常: {size}"
        print(f"[{country}] 接口+下载 {time.time()-t0:.1f}s, {size/1024/1024:.2f}MB, 校验OK")
    finally:
        os.remove(dest)
```

**✏️ 小练习 K（通读精简版）**

**步骤 1**：对照第五节代码，把"三步走"（接口→下载→校验清理）在代码里用注释标出来，标完和第三节第 5 小节的分步注释对比。

**步骤 2**：找出代码里所有 `assert` 行，数一数一共几条，说说每条在验什么（对照第二节的"校验思路"表）。

**步骤 3**：运行精简版确认 3 passed：
```bash
.venv\Scripts\python -m pytest test_map_download_api_lean.py -v
```

<details><summary>👀 参考答案</summary>

- 共 **4 条 assert**：① 接口 `code==200 and status is True`（请求是否成功）② `url` 以 `https://` 开头（CDN 链接格式）③ 文件头 `b"HUD4"`（是地图不是错误页）④ 大小在 `SIZE_MIN~SIZE_MAX`（数据量合理）。
- 全部是"特征校验"：不写死具体值，只验"格式对不对、范围合不合理"。和第二节的校验思路表一一对应。
</details>

## 六、怎么运行 + 结果怎么读 + 调试技巧

### 运行

```bash
cd C:\Users\Administrator\PycharmProjects\PythonProjectKK
.venv\Scripts\python -m pytest test_map_download_api.py -v        # 原版
.venv\Scripts\python -m pytest test_map_download_api_lean.py -v   # 精简版
```

- 不需要真机、不需要 Appium、不需要 RUN_UI
- 单独跑，不进 run_all 的 UI 流程（没有 order 标记，不会被编排）

### 结果怎么看

```
3 passed in 20.21s          ✅ 全过
2 passed, 1 failed          ❌ 有一条断言没满足，往上翻找 "AssertionError"
1 passed, 1 failed, 1 skipped   skipped = 被跳过了（比如 -k 过滤掉的）
```

### 调试三板斧

| 命令 | 作用 |
|------|------|
| `-v` | 显示每个用例的名字和结果 |
| `-k 兰州` | 只跑名字里带"兰州"的用例（参数化时很好用，不用等 3 国全跑） |
| `-x` | 一失败就停，不用等后面的用例 |
| `--tb=short` | 报错信息精简显示，不被一大屏堆栈淹没 |

**✏️ 小练习 L（调试命令）**

**步骤 1**：写出以下场景的命令（每题一条）：
1. 只跑日本那组数据，并显示详细信息
2. 3 国全跑，但"第一条失败就立刻停"
3. 跑精简版但报错信息要精简（不显示完整堆栈）

**步骤 2**：挑其中一条实际跑一遍，确认命令生效。

<details><summary>👀 参考答案</summary>

1. `.venv\Scripts\python -m pytest test_map_download_api_lean.py -k 日本 -v`
2. `.venv\Scripts\python -m pytest test_map_download_api_lean.py -x`
3. `.venv\Scripts\python -m pytest test_map_download_api_lean.py --tb=short`

三条可以组合：`.venv\Scripts\python -m pytest test_map_download_api_lean.py -k 日本 -v -x --tb=short`。
</details>

## 七、你能学到的核心知识点

1. **pytest 两条规矩**：文件名 `test_` 开头 + 函数名 `test_` 开头 = 自动被发现执行
2. **`assert 条件, "消息"`**：条件为假就 FAILED，pytest 自动显示表达式的值
3. **参数化** `@pytest.mark.parametrize` + `pytest.param(..., id=...)`：一套代码 N 组数据
4. **`pytestmark` 模块级标记** + `pytest.mark.timeout`：整个文件共用超时兜底
5. **`requests.get(params={...})`**：传查询参数的标准姿势，自动 URL 编码
6. **流式下载** `stream=True` + `iter_content(chunk_size=65536)`：大文件逐块写盘，不占内存
7. **`raise_for_status()`**：非 200 直接抛异常，省掉手写判断
8. **断言思路：验特征不验死值**：校验"范围/格式标识"，不写死具体大小
9. **`try/finally` 资源清理**：无论成败都删临时文件
10. **调试命令**：`-v` / `-k 名字` / `-x` / `--tb=short`

## 八、综合动手练习（把所有知识串起来）

做完上面的小练习后，用一整块时间挑战这几个：

1. **加一个国家**：泰国曼谷 `13.7563, 100.5018`，在 `COUNTRIES` 加一行，`-k 泰国` 跑通后再全量跑
2. **加一条断言**：url 域名必须包含 `cdn-roadnet`（提示：`"cdn-roadnet" in url`）。故意写错一次看 FAILED，再改对
3. **换校验特征**：把"文件头"校验改成同时校验文件尾 4 个字节，理解"特征校验"思路
4. **从零写一个**：抄一个"验证某 API 连通性"的最小脚本（10 行左右：1 个函数 + 1 条 assert），跑通后依次加上：参数化 → timeout → try/finally——每一步都跑一遍，写出来你就真会了

---

> 一句话总结：**接口连通性验证 = 请求 → 拿链接 → 下载 → 验特征 → 清理**。
> pytest 部分只需要记住：`test_` 开头会被自动跑、`assert` 判断对错、`@pytest.mark.parametrize` 换数据。
> 精简的度 = 去掉重复动作、已知现象的警告、多余打印，保留核心断言和清理保障。

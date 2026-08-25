# test_map_download_api.py — 地图下载接口通道测试 (中日韩)
# 常规通道测试: 验证"请求接口→拿到CDN链接→下载→完整性"链路通就行
# 不写死文件大小(三国数据量不同是特性), 校验文件头标识确认格式正确
# 下载到系统下载目录, 完成后立即删除, 不占磁盘空间
# 用法: .venv\Scripts\python -m pytest test_map_download_api.py -v  (纯网络, 不需真机)
# 注意: 独立接口测试, 不进 run_all 的 UI 流程(无 order 标记)

import os
import time
import requests
import pytest

# ── 三国参数: 城市 / WGS-84纬度 / 经度 / 半径 ──
# 坐标是WGS-84标准系(接口要求), 不是高德GCJ-02
# 二三线城市数据量小下载快; 若地图显示有~500m偏移说明坐标系不匹配
COUNTRIES = [
    pytest.param("中国兰州", 36.0611, 103.8343, 30000, id="中国-兰州"),
    pytest.param("日本札幌", 43.0618, 141.3545, 30000, id="日本-札幌"),
    pytest.param("韩国大田", 36.3504, 127.3845, 30000, id="韩国-大田"),
]

API_URL = "http://cybersight.zhxxh.cn/v2/map/roadnet/download.bin"
TIMEOUT_API = 30       # 接口请求超时(秒)
TIMEOUT_DL = 120       # 下载超时(秒)
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")  # 系统下载目录, 下载完即删

pytestmark = [pytest.mark.timeout(300)]  # 每国 5 分钟上限


def _download(url, dest, timeout=TIMEOUT_DL):
    """下载文件到dest, 返回(实际字节数, 响应头Content-Length)"""
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()                       # 非200直接抛
        clen = int(r.headers.get("Content-Length", 0))
        size = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
        return size, clen


@pytest.mark.parametrize("country,lat,lon,distance", COUNTRIES)
def test_map_download_channel(country, lat, lon, distance):
    """三国地图下载通道: 接口→CDN→下载→校验→删除"""
    # 1. 请求下载接口, 拿CDN链接
    t0 = time.time()
    resp = requests.get(API_URL, params={"lat": lat, "lon": lon, "distance": distance},
                        timeout=TIMEOUT_API)
    t_api = time.time() - t0
    assert resp.status_code == 200, f"[{country}] 接口非200: {resp.status_code}"
    data = resp.json()
    assert data.get("code") == 200, f"[{country}] code异常: {data}"
    assert data.get("status") is True, f"[{country}] status异常: {data}"
    url = data.get("data", {}).get("url", "")
    assert url.startswith("https://"), f"[{country}] CDN链接异常: {url}"
    print(f"[{country}] 接口OK {t_api:.1f}s → {url[:60]}...")

    # 2. 下载地图文件到项目downloads目录
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    dest = os.path.join(DOWNLOAD_DIR, f"map_{country}.bin")
    try:
        t0 = time.time()
        size, clen = _download(url, dest)
        t_dl = time.time() - t0
        # 3. 完整性校验: 非空 + 文件头标识 + 合理大小范围
        # Content-Length 只警告不断言: 地图动态生成, 实测与声明常不一致
        assert size > 0, f"[{country}] 下载为空"
        assert 0.1 * 1024 * 1024 <= size <= 100 * 1024 * 1024, \
            f"[{country}] 大小异常: {size}字节"
        if clen and clen != size:
            print(f"[{country}] 警告: Content-Length={clen} 实际={size}, 动态地图差异正常")
        with open(dest, "rb") as f:
            signature = f.read(4)
        assert signature == b"HUD4", f"[{country}] 文件头标识异常: {signature!r}"
        print(f"[{country}] 下载OK {size/1024/1024:.2f}MB {t_dl:.1f}s 文件头标识OK")
    finally:
        # 4. 下载完删除, 不占磁盘
        if os.path.exists(dest):
            os.remove(dest)
            print(f"[{country}] 已清理临时文件")

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
pytestmark = [pytest.mark.timeout(600)]  # 每国 5 分钟上限


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


if __name__ == "__main__":
    # PyCharm ▶ / 命令行直接跑时执行pytest, -s显示下载进度, 退出码透传
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))

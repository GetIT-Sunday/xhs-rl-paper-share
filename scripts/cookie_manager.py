#!/usr/bin/env python3
"""
XHS Cookie 管理器 —— QR 码登录 + 本地缓存

使用方式：
  # 获取有效 Cookie（自动从缓存读取，失效则重新扫码）
  from cookie_manager import get_valid_cookie
  cookie_str = get_valid_cookie()

  # 强制重新扫码
  from cookie_manager import login_by_qrcode
  cookie_str = login_by_qrcode()
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from xhs import XhsClient
    from xhshow import Xhshow
    _HAS_XHS = True
except ImportError:
    _HAS_XHS = False

# Cookie 缓存路径（放在用户 home 下，沙箱销毁后也能持久）
# Cookie 缓存路径优先用 workspace（跨会话持久），fallback 到 home
_WORKSPACE_CACHE = Path("/home/gem/workspace/.xhs_cookie_cache.json")
_HOME_CACHE = Path.home() / ".xhs_cookie_cache.json"

def _get_cache_path() -> Path:
    """返回可写的缓存路径：优先 workspace，其次 home"""
    if _WORKSPACE_CACHE.parent.exists():
        return _WORKSPACE_CACHE
    return _HOME_CACHE

COOKIE_CACHE_PATH = _get_cache_path()


def _make_client(cookie_str: str = "") -> "XhsClient":
    """创建带签名的 XhsClient"""
    if not _HAS_XHS:
        print("❌ 请先安装依赖：pip install xhs xhshow", file=sys.stderr)
        sys.exit(1)
    cookie = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            cookie[k.strip()] = v.strip()
    signer = Xhshow()

    def sign_func(url, data, a1=None, web_session=None):
        return signer.sign_headers_post(
            uri=url,
            cookies=cookie,
            payload=data if data else {},
            x_rap=True,
        )

    return XhsClient(cookie=cookie_str, sign=sign_func)


def _validate_cookie(cookie_str: str) -> bool:
    """验证 Cookie 是否有效（调一个轻量接口）"""
    try:
        client = _make_client(cookie_str)
        # 调用一个轻量只读接口验证登录态
        result = client.get_emojis()
        return True
    except Exception:
        return False


def _load_cache() -> dict:
    """读取本地 Cookie 缓存"""
    if not COOKIE_CACHE_PATH.exists():
        return {}
    try:
        with open(COOKIE_CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cookie_str: str, login_time: float):
    """保存 Cookie 到本地文件"""
    data = {
        "cookie": cookie_str,
        "login_time": login_time,
        "note": "XHS Web Cookie 缓存，约 30 天有效，失效后自动重新扫码",
    }
    COOKIE_CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    # 限制只有当前用户可读
    COOKIE_CACHE_PATH.chmod(0o600)
    print(f"✅ Cookie 已缓存到 {COOKIE_CACHE_PATH}")


def _qrcode_to_terminal(url: str):
    """在终端打印 QR 码"""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        return
    except ImportError:
        pass

    try:
        import segno
        qr = segno.make(url)
        qr.terminal(compact=True)
        return
    except ImportError:
        pass

    # 两个库都没有，用 qr 命令行工具
    result = os.system(f"command -v qr > /dev/null 2>&1 && qr '{url}'")
    if result == 0:
        return

    # 最后兜底：只打印 URL 让用户手动生成
    print(f"\n📱 请用手机浏览器打开以下链接，或将链接转为二维码后扫描：")
    print(f"   {url}\n")
    print("💡 提示：也可以在浏览器地址栏输入 https://www.xiaohongshu.com 扫码登录后，")
    print("         把 a1、web_session、webId Cookie 值告诉我直接使用。")


def login_by_qrcode() -> str:
    """通过扫码登录，返回 Cookie 字符串"""
    if not _HAS_XHS:
        print("❌ 请先安装依赖：pip install xhs xhshow", file=sys.stderr)
        sys.exit(1)

    # 创建一个无 cookie 的临时客户端用于登录流程
    # 注：签名库要求 cookies 中必须包含 a1（设备指纹），登录前尚无真实 a1，
    # 这里生成一个符合格式的临时值仅用于请求签名，不影响后续真实登录态获取
    import uuid
    _tmp_a1 = uuid.uuid4().hex + uuid.uuid4().hex[:14]
    signer = Xhshow()
    dummy_client = XhsClient(cookie=f"a1={_tmp_a1}", sign=lambda url, data, **kw: signer.sign_headers_post(
        uri=url, cookies={"a1": _tmp_a1}, payload=data if data else {}, x_rap=True
    ))

    print("\n🔑 需要登录小红书，正在生成二维码...")
    try:
        qr_resp = dummy_client.get_qrcode()
    except Exception as e:
        print(f"❌ 获取二维码失败: {e}", file=sys.stderr)
        sys.exit(1)

    qr_id = qr_resp.get("qr_id")
    code = qr_resp.get("code")
    qr_url = qr_resp.get("url", "")

    print("\n" + "=" * 50)
    print("请用小红书 App 扫描以下二维码登录：")
    print("=" * 50)
    _qrcode_to_terminal(qr_url)
    print("=" * 50)
    print("等待扫码中...")

    # 轮询登录状态（最多等 120 秒）
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(2)
        try:
            status_resp = dummy_client.check_qrcode(qr_id=qr_id, code=code)
        except Exception:
            continue

        login_status = status_resp.get("code_status", 0)
        # code_status: 0=待扫码, 1=已扫码待确认, 2=已确认
        if login_status == 1:
            print("📱 已扫码，请在手机上确认登录...")
        elif login_status == 2:
            # 登录成功，提取 Cookie
            # 注：当前 xhs 库返回的 login_info 字段为 session/secure_session/user_id，
            # 而非旧版预期的 web_session/web_id，这里做兼容映射；
            # a1 复用登录前生成的设备指纹（登录成功后服务端会绑定该 a1）
            login_info = status_resp.get("login_info", {})
            web_session = login_info.get("web_session", "") or login_info.get("secure_session", "")
            web_id = login_info.get("web_id", "") or login_info.get("user_id", "")

            if not web_session:
                print("❌ 登录成功但未获取到 web_session", file=sys.stderr)
                sys.exit(1)

            cookie_str = f"a1={_tmp_a1};web_session={web_session};webId={web_id}"
            print(f"\n✅ 登录成功！")
            login_time = time.time()
            _save_cache(cookie_str, login_time)
            return cookie_str

    print("❌ 扫码超时（120秒），请重试", file=sys.stderr)
    sys.exit(1)


def get_valid_cookie(force_refresh: bool = False) -> str:
    """
    获取有效的 XHS Cookie。

    策略：
    1. 读本地缓存
    2. 验证是否有效
    3. 有效 → 直接返回
    4. 失效 → 扫码重新登录

    Args:
        force_refresh: 强制重新扫码（忽略缓存）
    """
    if not force_refresh:
        cache = _load_cache()
        cookie_str = cache.get("cookie", "")

        if cookie_str:
            login_time = cache.get("login_time", 0)
            age_days = (time.time() - login_time) / 86400
            print(f"📂 读取缓存 Cookie（已缓存 {age_days:.1f} 天）...")

            # 超过 25 天主动提示续期（但不强制，先验证）
            if age_days > 25:
                print(f"⚠️  Cookie 已缓存 {age_days:.0f} 天，即将过期，正在验证...")

            if _validate_cookie(cookie_str):
                print("✅ Cookie 有效，直接使用")
                return cookie_str
            else:
                print("⚠️  缓存 Cookie 已失效，需要重新登录")

    return login_by_qrcode()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="XHS Cookie 管理器")
    parser.add_argument("--refresh", action="store_true", help="强制重新扫码登录")
    parser.add_argument("--validate", action="store_true", help="只验证当前 Cookie 是否有效")
    args = parser.parse_args()

    if args.validate:
        cache = _load_cache()
        cookie_str = cache.get("cookie", "")
        if not cookie_str:
            print("❌ 本地无 Cookie 缓存")
            sys.exit(1)
        if _validate_cookie(cookie_str):
            login_time = cache.get("login_time", 0)
            age_days = (time.time() - login_time) / 86400
            print(f"✅ Cookie 有效（已缓存 {age_days:.1f} 天）")
        else:
            print("❌ Cookie 已失效")
        sys.exit(0)

    cookie = get_valid_cookie(force_refresh=args.refresh)
    print(f"\nCookie: {cookie[:40]}...")

#!/usr/bin/env python3
"""Short-lived, loopback-only setup wizard. No credentials enter HTTP responses."""
from __future__ import annotations

import argparse
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from account_state import (current_cookie, fingerprint, home_path,
                           private_json, read_json, save_confirmation)
from cookie_manager import QRLogin, LoginError, verify_account, _get_cache_path

MODULES = {'xhs': 'xhs', 'xhshow': 'xhshow', 'PyMuPDF': 'fitz', 'Pillow': 'PIL',
           'requests': 'requests', 'arxiv': 'arxiv', 'qrcode': 'qrcode'}


class Wizard:
    def __init__(self, home, cache, ttl=900):
        self.home, self.cache = Path(home), Path(cache)
        self.token = secrets.token_urlsafe(32)
        self.session_id = secrets.token_hex(8)
        self.expires_at = time.time() + ttl
        self.status_file = self.home / 'configure-status.json'
        self.dependencies = {p: importlib.util.find_spec(m) is not None for p, m in MODULES.items()}
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.busy = False
        self.phase = 'idle'
        self.message = '生成二维码，或检查本机已有登录。'
        self.account = None
        self.cookie = current_cookie(self.cache)
        self.qr_image = None
        self.qr_expires_at = None
        self.complete = False
        self.write_status()

    def snapshot(self):
        with self.lock:
            return {'session_id': self.session_id, 'expires_at': self.expires_at,
                    'home': str(self.home), 'dependencies': self.dependencies,
                    'environment_ready': all(self.dependencies.values()),
                    'cookie_configured': bool(self.cookie), 'phase': self.phase,
                    'message': self.message, 'busy': self.busy, 'account': self.account,
                    'qr_ready': self.qr_image is not None, 'qr_expires_at': self.qr_expires_at,
                    'login_verified': self.account is not None,
                    'account_verified': self.account is not None,
                    'configuration_complete': self.complete,
                    'metrics_mapping_configured': bool(os.environ.get('XHS_METRICS_CONFIG')),
                    'live_metrics_verified': False}

    def write_status(self):
        private_json(self.status_file, self.snapshot())

    def update(self, **values):
        with self.lock:
            for name, value in values.items():
                setattr(self, name, value)
            self.write_status()

    def invalidate(self):
        config = read_json(self.home / 'config.json')
        if config:
            config['confirmed_account_id'] = None
            if isinstance(config.get('account'), dict):
                config['account']['verified_at'] = 0
            private_json(self.home / 'config.json', config)

    def start(self, action):
        with self.lock:
            if self.stop.is_set() or time.time() >= self.expires_at:
                raise LoginError('配置页面已过期，请让 Agent 重新打开。')
            if self.busy:
                raise LoginError('正在处理，请等待当前操作完成。')
            if action not in ('login', 'verify', 'confirm'):
                raise LoginError('未知操作。')
            if action == 'confirm' and (not self.account or not all(self.dependencies.values())):
                raise LoginError('请先完成环境检查和真实账号核对。')
            self.update(busy=True, complete=False, phase='working', message='正在连接小红书…')
            threading.Thread(target=self.work, args=(action,), daemon=True).start()

    def work(self, action):
        try:
            if action == 'login':
                # An inherited explicit cookie would win in future Agent commands.
                if os.environ.get('XHS_COOKIE'):
                    raise LoginError('检测到外部登录配置。请让 Agent 移除 XHS_COOKIE 配置后，再切换扫码账号。')
                self.invalidate()
                self.update(account=None, qr_image=None)
                qr = QRLogin()
                self.update(qr_image=qr.image(), qr_expires_at=qr.deadline,
                            phase='waiting', message='请用小红书 App 扫码，并在手机上确认登录。')
                while not self.stop.wait(2):
                    state, cookie = qr.poll()
                    if cookie:
                        private_json(self.cache, {'cookie': cookie, 'login_time': time.time()})
                        self.cookie = cookie
                        self.update(qr_image=None, phase='verifying', message='登录完成，正在读取真实账号…')
                        break
                    self.update(phase=state, message=('已扫码，请在手机上确认。' if state == 'scanned' else '等待手机扫码…'))
                else:
                    return
            if fingerprint(current_cookie(self.cache)) != fingerprint(self.cookie):
                raise LoginError('本机登录凭证已发生变化，请重新打开配置页。')
            before = self.account
            account = verify_account(self.cookie)
            if self.stop.is_set():
                return
            if action == 'confirm':
                if not before or account['account_id'] != before['account_id']:
                    self.invalidate()
                    self.update(account=account, phase='verified', message='登录账号发生变化，请重新核对后确认。')
                    return
                if fingerprint(current_cookie(self.cache)) != fingerprint(self.cookie):
                    raise LoginError('本机登录凭证已发生变化，请重新打开配置页。')
                save_confirmation(self.home, self.cookie, account)
                self.update(account=account, complete=True, phase='complete', qr_image=None,
                            message='配置已保存。回到 Agent 对话即可继续创作；本页不会发布内容。')
            else:
                self.update(account=account, phase='verified', qr_image=None,
                            message='已从平台读取真实账号，请核对昵称和账号 ID。')
        except Exception as exc:
            self.invalidate()
            self.update(account=None, complete=False, phase='error', qr_image=None,
                        message=str(exc) if isinstance(exc, LoginError) else '操作未完成，接口适配或依赖可能不可用，请让 Agent 检查。')
        finally:
            self.update(busy=False)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, wizard):
        self.wizard = wizard
        super().__init__(('127.0.0.1', 0), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Neither request tokens nor third-party responses belong in logs.

    def reply(self, code, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob: https:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self, api=False):
        wizard = self.server.wizard
        if time.time() >= wizard.expires_at or wizard.stop.is_set():
            self.reply(410, {'error': '配置页已过期，请重新打开。'})
            return False
        if self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            self.reply(403, {'error': '无效主机。'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin:
            self.reply(403, {'error': '不允许跨站请求。'})
            return False
        if api and not secrets.compare_digest(self.headers.get('X-Paper2XHS-Token', ''), wizard.token):
            self.reply(403, {'error': '配置链接无效，请让 Agent 重新打开。'})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(api=path.startswith('/api/')):
            return
        assets = {'/': ('configure.html', 'text/html; charset=utf-8'),
                  '/configure.css': ('configure.css', 'text/css; charset=utf-8'),
                  '/configure.js': ('configure.js', 'text/javascript; charset=utf-8')}
        if path in assets:
            filename, mime = assets[path]
            self.reply(200, Path(__file__).with_name(filename).read_bytes(), mime)
        elif path == '/api/status':
            self.reply(200, self.server.wizard.snapshot())
        elif path == '/api/qr':
            with self.server.wizard.lock:
                image = self.server.wizard.qr_image
            self.reply(200, image, 'image/png') if image else self.reply(404, {'error': '暂无二维码。'})
        else:
            self.reply(404, {'error': '页面不存在。'})

    def do_POST(self):
        if not self.allowed(api=True):
            return
        if self.headers.get('Content-Length', '0') != '0':
            self.reply(400, {'error': '此接口不接受表单数据。'})
            return
        path = urlsplit(self.path).path
        if path not in ('/api/login', '/api/verify', '/api/confirm'):
            self.reply(404, {'error': '操作不存在。'})
            return
        try:
            self.server.wizard.start(path.rsplit('/', 1)[-1])
            self.reply(202, self.server.wizard.snapshot())
        except LoginError as exc:
            self.reply(409, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ttl', type=int, default=900, help='Lifetime in seconds (30–3600)')
    args = parser.parse_args()
    if not 30 <= args.ttl <= 3600:
        parser.error('--ttl must be between 30 and 3600')
    home = home_path()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    # One wizard owns the account's confirmation state at a time.
    lock_fd = os.open(home / 'configure.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        parser.exit(2, '配置页已在运行，请继续使用已打开的页面或停止旧进程后重新打开。\n')
    wizard = Wizard(home, _get_cache_path(), args.ttl)
    with Server(wizard) as server:
        server.timeout = 0.5
        print(json.dumps({'url': server.origin + '/#token=' + wizard.token,
                          'status_file': str(wizard.status_file), 'session_id': wizard.session_id,
                          'expires_at': wizard.expires_at}, ensure_ascii=False), flush=True)
        if wizard.cookie:
            wizard.start('verify')
        try:
            while time.time() < wizard.expires_at:
                server.handle_request()
        except KeyboardInterrupt:
            pass
        finally:
            wizard.stop.set()
            wizard.update(phase='closed', busy=False, qr_image=None,
                          message='配置页已关闭。已保存的配置仍保留在本机。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Portable Skill entrypoint. Keep installed code separate from private state."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

SKILL = Path(__file__).resolve().parents[1]
COMMANDS = {
    'fetch': 'fetch_papers.py', 'generate': 'generate_content.py',
    'cover': 'capture_cover.py', 'evidence': 'evidence_check.py',
    'collect': 'collect_metrics.py', 'feedback': 'feedback.py',
    'login': 'cookie_manager.py', 'publish': 'publish_to_xhs.py',
    'schedule': 'scheduled_publish.py',
}
RUNTIME_SCRIPTS = sorted(set(COMMANDS.values()) | {
    'paper_pipeline.py', 'publication_store.py', 'compose_cover.py', 'xhs_mcp_client.py',
})
MODULES = {'xhs': 'xhs', 'xhshow': 'xhshow', 'PyMuPDF': 'fitz', 'Pillow': 'PIL',
           'requests': 'requests', 'arxiv': 'arxiv', 'qrcode': 'qrcode'}


def paths():
    home = Path(os.environ.get('PAPER2XHS_HOME', '~/.local/share/paper2xhs')).expanduser().resolve()
    data = Path(os.environ.get('PAPER2XHS_DATA_DIR', str(home / 'data'))).expanduser().resolve()
    return {'home': home, 'app': home / 'app', 'data': data,
            'python': home / '.venv' / 'bin' / 'python',
            'cookie_cache': Path(os.environ.get('XHS_COOKIE_CACHE', str(home / 'cookie.json'))).expanduser().resolve()}


def sync_runtime(p):
    # Never copy references/*.json: the source repo may contain real account data.
    if p['home'] == SKILL or SKILL in p['home'].parents or p['home'] in SKILL.parents:
        raise ValueError('PAPER2XHS_HOME must be separate from the installed Skill directory')
    for key in ('home', 'data'):
        if p[key] == SKILL or SKILL in p[key].parents:
            raise ValueError('Private state must be outside the Skill directory')
        p[key].mkdir(parents=True, exist_ok=True, mode=0o700)
    for relative in ('scripts', 'references', 'examples', 'assets/covers'):
        (p['app'] / relative).mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_SCRIPTS:
        source = SKILL / 'scripts' / name
        target = p['app'] / 'scripts' / name
        if not target.exists() or source.read_bytes() != target.read_bytes():
            shutil.copyfile(source, target)
    source = SKILL / 'examples' / 'creator_metrics.config.example.json'
    target = p['app'] / 'examples' / source.name
    shutil.copyfile(source, target)


def environment(p):
    env = dict(os.environ)
    env['PAPER2XHS_DATA_DIR'] = str(p['data'])
    env['XHS_COOKIE_CACHE'] = str(p['cookie_cache'])
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    # Reuse locally provided/login-cached credentials without printing them.
    if not env.get('XHS_COOKIE') and p['cookie_cache'].exists():
        cookie = json.loads(p['cookie_cache'].read_text()).get('cookie')
        if cookie:
            env['XHS_COOKIE'] = cookie
    return env


def doctor(p):
    executable = p['python'] if p['python'].exists() else Path(sys.executable)
    code = ('import importlib.util,json; '
            'print(json.dumps({p:importlib.util.find_spec(m) is not None '
            'for p,m in ' + repr(MODULES) + '.items()}))')
    probe = subprocess.run([str(executable), '-c', code], capture_output=True, text=True)
    dependencies = json.loads(probe.stdout) if probe.returncode == 0 else {}
    return {**{k: str(v) for k, v in p.items()}, 'skill': str(SKILL),
            'supported_platform': os.name == 'posix', 'python_supported': sys.version_info >= (3, 10),
            'venv_ready': p['python'].exists(), 'dependencies': dependencies,
            'cookie_configured': bool(os.environ.get('XHS_COOKIE') or p['cookie_cache'].exists()),
            'account_configured': bool(os.environ.get('XHS_ACCOUNT_ID')),
            'metrics_mapping_configured': bool(os.environ.get('XHS_METRICS_CONFIG')),
            'live_metrics_verified': False,
            'note': 'Local configuration checks only; no platform login or API was verified.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    sub.add_parser('doctor', help='Report local readiness without credentials or network calls')
    setup = sub.add_parser('setup', help='Prepare private runtime and install dependencies')
    setup.add_argument('--skip-deps', action='store_true', help='Skip venv and pip; stdlib workflows only')
    sub.add_parser('prepare', help='Select and prepare from cached candidates; never publish')
    run = sub.add_parser('run', help='Run one function in the private workspace')
    run.add_argument('command', choices=sorted(COMMANDS))
    run.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    p = paths()
    try:
        if args.mode == 'doctor':
            print(json.dumps(doctor(p), ensure_ascii=False, indent=2))
            return 0
        if os.name != 'posix' or sys.version_info < (3, 10):
            raise ValueError('Use Python 3.10+ on macOS/Linux or Windows WSL')
        sync_runtime(p)
        if args.mode == 'setup':
            if not args.skip_deps:
                if not p['python'].exists():
                    venv.EnvBuilder(with_pip=True).create(p['home'] / '.venv')
                subprocess.run([str(p['python']), '-m', 'pip', 'install', '-r', str(SKILL / 'requirements.txt')], check=True)
            print(json.dumps(doctor(p), ensure_ascii=False, indent=2))
            return 0
        python = str(p['python']) if p['python'].exists() else sys.executable
        env = environment(p)
        if args.mode == 'prepare':
            code = ('from scheduled_publish import prepare_next_content; '
                    'p=prepare_next_content(); print(str(p) if p else "No cached candidates; run fetch first"); '
                    'raise SystemExit(0 if p else 2)')
            return subprocess.call([python, '-c', code], cwd=p['app'] / 'scripts', env=env)
        extra = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
        return subprocess.call([python, str(p['app'] / 'scripts' / COMMANDS[args.command]), *extra],
                               cwd=p['app'], env=env)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        # Avoid reflecting local credential contents or failing command arguments.
        print('Paper2XHS setup/run failed: ' + (str(exc) if type(exc) is ValueError else type(exc).__name__), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

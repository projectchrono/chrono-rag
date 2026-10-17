"""Conda bootstrap shared by both setup scripts; only uses the standard library."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def setup(conda: str, name: str, channel: str) -> None:
    if not name or name.startswith('-') or name in {'.', '..', 'base', 'root'} or any(c in name for c in '/\\:'):
        raise ValueError('CHRONO_RAG_ENV must be a dedicated conda environment name, not a path or base.')

    def run(*args: str, capture: bool = False):
        return subprocess.run([conda, *args], check=True, text=True,
                              capture_output=capture, cwd=ROOT)

    envs = json.loads(run('env', 'list', '--json', capture=True).stdout)['envs']
    matches = [p for p in envs if os.path.normcase(Path(p).name) == os.path.normcase(name)]
    if len(matches) > 1:
        raise ValueError(f'Multiple environments named {name!r}; choose a unique CHRONO_RAG_ENV.')
    if matches:
        print(f"==> [1/3] Reusing conda environment {matches[0]}", flush=True)
        target = ['-p', matches[0]]
    else:
        # Even an unregistered/broken directory must never be overwritten by create -y.
        info = json.loads(run('info', '--json', capture=True).stdout)
        for parent in info['envs_dirs']:
            if (Path(parent) / name).exists():
                raise ValueError(f'Environment directory already exists: {Path(parent) / name}. '
                                 'Repair it or choose another CHRONO_RAG_ENV.')
        print(f"==> [1/3] Creating conda environment {name!r} (Python 3.12)", flush=True)
        run('create', '-n', name, 'python=3.12', '-y')
        target = ['-n', name]

    print('==> [2/3] Installing chrono-rag', flush=True)
    run('run', '--no-capture-output', *target, 'python', '-m', 'pip', 'install',
        '-e', f'{ROOT}[llm,web,mcp,dev]')
    print(f'==> [3/3] Checking/downloading the {channel} index', flush=True)
    run('run', '--no-capture-output', *target, 'chrono-rag', 'get-index',
        '--channel', channel, '--if-missing')
    print(f'\nchrono-rag is ready (channel {channel}).\n\n'
          f'  conda activate {name}\n'
          '  chrono-rag search "how do I attach a lidar in pychrono"\n\n'
          'Run chrono-rag doctor for diagnostics. Restart existing MCP/web processes '
          'after changing the index.', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conda', required=True)
    parser.add_argument('--channel', default=os.getenv('CHRONO_RAG_CHANNEL', 'main'))
    parser.add_argument('--env', default=os.getenv('CHRONO_RAG_ENV', 'chrono-rag'))
    args = parser.parse_args()
    try:
        setup(args.conda, args.env, args.channel)
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError) as exc:
        print(f'Setup failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

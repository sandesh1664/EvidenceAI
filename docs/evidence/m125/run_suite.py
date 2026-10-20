"""Run independent regression groups against the explicit disposable database."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[3]
commands=[['python3',str(root/'docs/evidence/m125/run_regressions.py'),group] for group in ['backend','frontend','audits']]
processes=[subprocess.Popen(c,cwd=root) for c in commands]
raise SystemExit(max(p.wait() for p in processes))

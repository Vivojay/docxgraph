import os
import shutil
import signal
import subprocess
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_seed():
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    subprocess.run([sys.executable, "-m", "backend.app.seed"], cwd=ROOT, env=env, check=True)


def main():
    run_seed()
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    backend = subprocess.Popen([sys.executable, "-m", "backend.app.main"], cwd=ROOT, env=env)
    frontend = None
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm:
        frontend = subprocess.Popen([npm, "run", "dev"], cwd=os.path.join(ROOT, "frontend"), env=env)
    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None:
                raise SystemExit(backend.returncode)
            if frontend and frontend.poll() is not None:
                raise SystemExit(frontend.returncode)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in [frontend, backend]:
            if proc and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)


if __name__ == "__main__":
    main()

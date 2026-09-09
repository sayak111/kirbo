import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIENT_DIR = ROOT / "client"

if __name__ == "__main__":
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    subprocess.run([sys.executable, "-m", "client.gui"], cwd=ROOT, env=env)

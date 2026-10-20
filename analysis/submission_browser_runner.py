"""Launch an isolated synthetic cabinet for the submission browser smoke."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from scripts.runtime import Runtime


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sme-ui-audit-") as folder:
        with Runtime(Path(folder)):
            pass
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env.update(
            MODEL_PROVIDER="mock",
            SME_AUDIT_BASE_URL=f"http://127.0.0.1:{port}",
            SME_AUDIT_WORKSPACE=folder,
        )
        with Path(".runtime/submission-audit-20261019-browser-server.log").open("w") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "scripts.serve", "--directory", folder, "--port", str(port)],
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("isolated cabinet exited; see runtime log")
                    try:
                        with urlopen(
                            env["SME_AUDIT_BASE_URL"] + "/v1/health", timeout=1
                        ) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                completed = subprocess.run(
                    ["node", "analysis/submission_browser_smoke.cjs"],
                    env=env,
                    timeout=100,
                    check=False,
                )
                if completed.returncode:
                    raise RuntimeError("browser smoke failed")
            finally:
                # CTRL_BREAK isn't available with pipes. Terminate only our process tree.
                subprocess.run(
                    ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
                server.wait(timeout=10)


if __name__ == "__main__":
    main()

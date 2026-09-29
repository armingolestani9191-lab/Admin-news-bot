# ==========================
# AutoNewsBot Launcher
# Version 1.4
# ==========================

import os
import subprocess
import sys
import time


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def start_process(title, script):
    print(f"🚀 Starting {title}...")
    return subprocess.Popen(
        [sys.executable, "-u", os.path.join(BASE_DIR, script)],
        cwd=BASE_DIR,
    )


if __name__ == "__main__":
    print("🚀 Starting AutoNewsBot System v1.4...")
    processes = {
        "User Bot": start_process("User Bot", "bot.py"),
        "News Engine": start_process("News Engine", "main.py"),
    }
    print("✅ All systems started!")
    while True:
        for title, process in list(processes.items()):
            code = process.poll()
            if code is None:
                continue
            print(f"❌ {title} stopped with code {code}. Restarting...")
            script = "bot.py" if title == "User Bot" else "main.py"
            processes[title] = start_process(title, script)
        time.sleep(3)

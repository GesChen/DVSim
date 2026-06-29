# redirect output to logfile
import sys
from pathlib import Path
from datetime import datetime

class Logger:
    def __init__(self, filename):
        self.file = open(filename, "a", encoding="utf-8", buffering=1)
        
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.file.write(f"\n{'=' * 80}\n")
        self.file.write(f"Session started: {ts}\n")
        self.file.write(f"{'=' * 80}\n")

    def write(self, text):
        if not text:
            return

        for line in text.splitlines(True):  # keep newline
            if line.strip():
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                self.file.write(f"[{ts}] {line}")
            else:
                self.file.write(line)

    def flush(self):
        self.file.flush()

log = Logger(str(Path(__file__).with_name("postprocess.log")))
sys.stdout = log
sys.stderr = log
# ---

josnpath = sys.argv[1]

import postprocessoutput
postprocessoutput.processbin(josnpath)
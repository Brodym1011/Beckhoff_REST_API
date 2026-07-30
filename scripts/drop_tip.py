import subprocess
import sys

# Replace this command with the real drop-tip terminal call
result = subprocess.run(["echo", "drop_tip: OK"], capture_output=True, text=True)
print(result.stdout.strip())
sys.exit(result.returncode)

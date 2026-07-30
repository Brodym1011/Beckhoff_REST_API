import subprocess
import sys

# Replace this command with the real open-door terminal call
result = subprocess.run(["echo", "open_door: OK"], capture_output=True, text=True)
print(result.stdout.strip())
sys.exit(result.returncode)

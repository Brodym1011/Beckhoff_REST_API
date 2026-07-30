import subprocess
import sys

# Replace this command with the real close-door terminal call
result = subprocess.run(["echo", "close_door: OK"], capture_output=True, text=True)
print(result.stdout.strip())
sys.exit(result.returncode)

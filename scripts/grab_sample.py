import subprocess
import sys

# Replace this command with the real grab-sample terminal call
result = subprocess.run(["echo", "grab_sample: OK"], capture_output=True, text=True)
print(result.stdout.strip())
sys.exit(result.returncode)

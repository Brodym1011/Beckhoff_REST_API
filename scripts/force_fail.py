import sys

# Always exits non-zero to trigger a 400 response
print("force_fail: intentional failure", file=sys.stderr)
sys.exit(1)

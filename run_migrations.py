"""Run database migrations."""
import subprocess
import sys
import os

# Change to the FastAPI directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Run alembic upgrade head
result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], 
                       capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)

sys.exit(result.returncode)

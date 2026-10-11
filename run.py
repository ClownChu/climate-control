import subprocess
import sys
import time
import os

while True:
    try:
        # Call control.py with parameters from command line
        script_path = os.path.join(os.path.dirname(__file__), 'control.py')
        subprocess.call([sys.executable, script_path] + sys.argv[1:])

        # Wait for execution to complete
        time.sleep(1)

    except subprocess.CalledProcessError:
        # Restart if control.py crashes
        continue

    except KeyboardInterrupt:
        # Exit gracefully if interrupted by user
        break

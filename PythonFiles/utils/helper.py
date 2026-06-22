# Helper functions for smooth operation

from pathlib import Path
import os
import time
import threading
import logging

import psutil

logger = logging.getLogger('HGCALTestGUI.PythonFiles.utils.helper')

def get_install_path():

    return Path(__file__).parent.parent.parent

def get_logging_path():
    # Portable across Windows (USERPROFILE) and Linux/macOS (HOME).
    home = os.getenv("USERPROFILE") or os.getenv("HOME") or os.path.expanduser("~")
    return home + "/GUILogs/testgui.log"


def install_parent_death_watchdog(parent_pid=None, poll_interval=1.0):
    """Force this process to exit if its parent dies.

    Portable across Linux and Windows: starts a daemon thread that polls
    whether the parent process is still alive and calls os._exit() if it
    disappears. This prevents orphaned child processes from lingering (and
    busy-looping) after the launcher is gone -- e.g. when the terminal window
    is closed and the parent is killed without a clean shutdown.

    The parent's creation time is captured up front so PID reuse cannot fool
    the watchdog into thinking a recycled PID is still our parent.
    """
    if parent_pid is None:
        parent_pid = os.getppid()

    try:
        parent = psutil.Process(parent_pid)
        start_time = parent.create_time()
    except psutil.Error:
        # Can't observe the parent; nothing to watch.
        return

    def _watch():
        while True:
            try:
                gone = (not parent.is_running()
                        or parent.status() == psutil.STATUS_ZOMBIE
                        or parent.create_time() != start_time)
            except psutil.Error:
                gone = True
            if gone:
                os._exit(1)
            time.sleep(poll_interval)

    watchdog = threading.Thread(target=_watch, name='parent-death-watchdog', daemon=True)
    watchdog.start()

"""Stop the Pi-driven cycle_loop cleanly.

Writes STOP_FLAG (picked up at the next iteration boundary) and sends
SIGTERM to the cycle_loop PID so it finishes the current iteration,
powers off, and exits. Safe to call even if no cycle is running.
"""

import json
import logging
import os
import signal
import time

import cycle_loop

logger = logging.getLogger('HGCALTestGUI.mb_tests.killCycle')

PID_FILE = '/tmp/hgcal_thermal.pid'

# Seconds to wait for cycle_loop to exit after SIGTERM.
JOIN_TIMEOUT_S = 15.0


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):
        result = {'status': 'no_cycle_running'}

        # Create the stop flag so the loop exits at the next iteration boundary
        # even if SIGTERM is lost.
        try:
            with open(cycle_loop.STOP_FLAG, 'w') as f:
                f.write('stop')
        except OSError as e:
            logger.warning('could not write STOP_FLAG: %s', e)

        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            pid = None

        if pid is not None:
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info('killCycle: SIGTERM sent to pid=%d', pid)
                # Poll until it exits or timeout.
                deadline = time.time() + JOIN_TIMEOUT_S
                while time.time() < deadline and _pid_alive(pid):
                    time.sleep(0.25)
                result = {
                    'status': 'killed' if not _pid_alive(pid) else 'still_alive',
                    'pid': pid,
                }
            except ProcessLookupError:
                result = {'status': 'process_not_found', 'pid': pid}

            try:
                os.remove(PID_FILE)
            except OSError:
                pass

        conn_test.send('Done.')
        conn_test.send(json.dumps(result))

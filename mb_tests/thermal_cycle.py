"""Start the Pi-driven thermal-cycle loop.

Spawns cycle_loop.run as a non-daemon background process so the LocalHandler
subprocess can return immediately and free the trigger pipe for follow-up
requests (status_poll, killCycle, power_off). The loop owns power and
pacing; the ZCU only runs single-pass conn tests via its 'runOnce' endpoint.

To avoid orphaned loops outliving a GUI crash, we capture the GUI's PID
(grandparent of this task_test subprocess) and pass it to cycle_loop so it
can self-terminate when the GUI is gone.
"""

import json
import logging
import multiprocessing as mp
import os

import cycle_loop


def _find_gui_pid():
    """Grandparent PID: task_test -> LocalHandler -> GUI main.
    Returns None if /proc isn't available or the walk fails (cycle_loop
    then just skips the liveness check)."""
    try:
        with open('/proc/{}/status'.format(os.getppid())) as f:
            for line in f:
                if line.startswith('PPid:'):
                    pid = int(line.split()[1])
                    return pid if pid > 1 else None
    except (FileNotFoundError, ValueError, PermissionError):
        pass
    return None

logger = logging.getLogger('HGCALTestGUI.mb_tests.thermal_cycle')

STATES = {
    "pass": "Pass",
    "fail": "Fail",
    "retest": "Needs Retesting",
    "excluded": "Excluded from Test",
    "waiting": "Waiting",
}
naming_scheme = [
    "SFP0", "SFP1", "SFP2", "SFP3",
    "A1", "A2", "A3", "A4",
    "B1", "B2", "B3", "B4",
    "C1", "C2", "C3", "C4",
    "D1", "D2", "D3", "D4",
]

# Production runtime; set low for debug.
# RUNTIME_M = 200
RUNTIME_M = 0.5  # DEBUG: 30 seconds

PID_FILE = '/tmp/hgcal_thermal.pid'


class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):
        self.conn = conn_test
        remote_ip = gui_cfg["TestHandler"]["remoteip"]
        selected = [naming_scheme[i] for i, s in enumerate(sites or []) if s]

        site_map = {}
        for i, s in enumerate(sites or []):
            site_map[naming_scheme[i]] = {"passing_state": "waiting" if s else "excluded"}

        if selected:
            # Clear any stale stop flag from a prior run.
            if os.path.exists(cycle_loop.STOP_FLAG):
                try:
                    os.remove(cycle_loop.STOP_FLAG)
                except OSError:
                    pass
            # Start a fresh results file so status_poll only sees this run.
            open(cycle_loop.RESULTS_PATH, 'w').close()

            gui_pid = _find_gui_pid()
            logger.info('capturing GUI pid=%s for crash-teardown check', gui_pid)
            p = mp.Process(
                target=cycle_loop.run,
                args=(remote_ip, selected, RUNTIME_M, tester),
                kwargs={'gui_pid': gui_pid},
                daemon=False,
            )
            p.start()
            with open(PID_FILE, 'w') as f:
                f.write(str(p.pid))
            logger.info('cycle_loop started as pid=%d for sites=%s', p.pid, selected)
        else:
            logger.info('thermal_cycle: no sites selected, nothing to start')

        self.conn.send('Done.')
        self.conn.send(json.dumps(site_map))

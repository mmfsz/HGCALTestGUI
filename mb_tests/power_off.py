"""GUI-invokable power-off. Turns off power for all sites marked ready.

Called after the ZCU has stopped testing (killCycle / natural end-of-cycle)
so we don't race with an in-flight lpGBT I2C transaction — cutting power
mid-I2C can latch the bus and force a hardware power cycle.
"""

import json
import logging
import time

from power_manager import PowerManager

logger = logging.getLogger('HGCALTestGUI.mb_tests.power_off')

naming_scheme = [
    "SFP0", "SFP1", "SFP2", "SFP3",
    "A1", "A2", "A3", "A4",
    "B1", "B2", "B3", "B4",
    "C1", "C2", "C3", "C4",
    "D1", "D2", "D3", "D4",
]

# Brief pause after killCycle before cutting power, giving the ZCU time
# to finish any in-flight I2C transaction. Not a guarantee of safety if
# the user killed mid-cycle — proper fix is clean max_cycles exit.
POST_KILL_SETTLE_S = 3.0


class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):
        self.conn = conn_test

        targets = [naming_scheme[i] for i, s in enumerate(sites or []) if s]

        time.sleep(POST_KILL_SETTLE_S)

        pm = PowerManager()
        if targets:
            pm.power_off(targets)
        else:
            pm.power_off_all()

        self.conn.send('Done.')
        self.conn.send(json.dumps({"status": "power_off_complete", "sites": targets}))

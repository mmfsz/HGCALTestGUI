"""Per-site power control for the thermal-cycle stand.

Wraps `pwr_simple_2.mm_power_man` with the 20-site GUI naming scheme.
Each site maps to (board_id, module_id) where board_id is a key in
`pwr_simple_2.mm_power_man.addrs`.

SITE_MAP is hardware-dependent — edit to match the physical wiring of
the power tray boards. Boards that fail to open (e.g. Remote I/O error
because the hardware isn't present) are logged and skipped; calls for
sites on those boards become no-ops so the test flow can proceed.
"""

import logging
import time

from pwr_simple_2 import mm_power_man

logger = logging.getLogger(__name__)

# GUI site name -> (board_id, module_id). Board IDs index into
# pwr_simple_2.mm_power_man.addrs. Modules are 1..4 per board.
#
# Current wiring on this stand:
#   - Only boards 2,3,4 are physically installed (3 boards × 4 modules = 12 sites).
#   - SFP0-SFP3 routed to board 2; HPC0 sites (A,B) on boards 3 and 4.
#   - HPC1 sites (C,D) are not wired yet — leave unmapped.
# Verify against your wiring before running; unmapped sites are silently
# skipped, erroring boards are logged and skipped.
SITE_MAP = {
    'SFP0': (2, 1), 'SFP1': (2, 2), 'SFP2': (2, 3), 'SFP3': (2, 4),
    'B1':   (3, 1), 'B2':   (3, 2), 'B3':   (3, 3), 'B4':   (3, 4),
    'A1':   (4, 1), 'A2':   (4, 2), 'A3':   (4, 3), 'A4':   (4, 4),
}

# Seconds to wait after power-on before the ZCU starts I2C.
SETTLE_DELAY_S = 1.5


class PowerManager:
    def __init__(self, device='/dev/i2c-1'):
        self.device = device
        self._managers = {}

    def _manager(self, board):
        if board not in self._managers:
            try:
                self._managers[board] = mm_power_man(self.device, board)
                logger.info("Opened power board %d", board)
            except Exception as e:
                self._managers[board] = None
                logger.warning("Power board %d unreachable (%s); sites on it will be skipped", board, e)
        return self._managers[board]

    def _resolve(self, site):
        bm = SITE_MAP.get(site)
        if bm is None:
            logger.warning("Site %s has no power mapping; skipping", site)
            return None, None, None
        board, module = bm
        mgr = self._manager(board)
        return mgr, board, module

    def _set(self, sites, enabled):
        done = []
        for site in sites:
            mgr, board, module = self._resolve(site)
            if mgr is None:
                continue
            try:
                mgr.set_enabled(imodule=module, enabled=enabled)
                done.append(site)
                state = "ON" if enabled else "OFF"
                logger.info("Power %s: %s (board %d, module %d)", state, site, board, module)
                print("Power %s: %s (board %d, module %d)" % (state, site, board, module))
            except Exception as e:
                logger.error("Failed to set power for %s: %s", site, e)
        return done

    def power_on(self, sites, settle=True):
        done = self._set(sites, True)
        if done and settle:
            time.sleep(SETTLE_DELAY_S)
        return done

    def power_off(self, sites):
        return self._set(sites, False)

    def power_off_all(self):
        return self.power_off(list(SITE_MAP.keys()))

    def read(self, site):
        mgr, board, module = self._resolve(site)
        if mgr is None:
            return None
        try:
            flags = mgr.status_flags()
            return {
                'v_in': mgr.input_voltage(),
                'i_9v': mgr.current(module, analog=True),
                'enabled': flags['M%d.ENABLED' % module],
                'pgood_9v': flags['M%d.9V_OK' % module],
            }
        except Exception as e:
            logger.error("Failed to read power for %s: %s", site, e)
            return None

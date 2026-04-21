"""Pi-side thermal-cycle loop.

Runs as a daemon spawned by thermal_cycle.py. Per outer iteration:
  1. power on selected sites
  2. ZMQ runBatch to ZCU — spawns a short-lived subprocess that runs
     CYCLES_PER_RESTART test iterations and exits (reclaims uHAL memory).
  3. power off selected sites
  4. sleep briefly
Repeats until runtime_m expires, SIGTERM received, or STOP_FLAG appears.
Always powers off on exit (try/finally).

CYCLES_PER_RESTART is the knob the operator has to trade off:
  - 1 = maximum power toggling, each test gets its own subprocess (slower)
  - N = test runs N cycles per power-on with one subprocess, fewer power
    toggles but less uHAL memory growth per outer iteration
The equivalent of the old MAX_CYCLES_PER_RESTART in cycleManager.
"""

import json
import logging
import os
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path

import zmq

from power_manager import PowerManager

logger = logging.getLogger('HGCALTestGUI.mb_tests.cycle_loop')

STOP_FLAG = '/tmp/hgcal_thermal_stop'
RESULTS_PATH = str(Path.home() / 'thermal_cycle_results.json')

# Test iterations per subprocess restart (and per power-on → power-off pair).
# Default 1 gives per-iteration power toggle as requested by the operator.
# Raise to amortize Python+uHAL startup (~5-10s) over more test cycles.
CYCLES_PER_RESTART = 1

# Sleep between outer iterations after power-off.
INTER_CYCLE_SLEEP_S = 1.0
# ZMQ timeout for runBatch — must exceed subprocess startup + N test passes.
# 60s baseline + 30s per cycle. Adjust if your test pass is longer.
RUNBATCH_BASE_TIMEOUT_MS = 60000
RUNBATCH_PER_CYCLE_MS = 30000


def _runBatch_zcu(remote_ip, iengines, tester, n_cycles):
    """Send 'runBatch;site1,site2,...;tester;n_cycles' to ZCU.
    Returns parsed JSON result (with 'cycles' list) or None on failure."""
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.connect('tcp://{}:5555'.format(remote_ip))
    try:
        msg = 'runBatch;{};{};{}'.format(','.join(iengines), tester or '', n_cycles)
        sock.send_string(msg)
        timeout_ms = RUNBATCH_BASE_TIMEOUT_MS + RUNBATCH_PER_CYCLE_MS * n_cycles
        if sock.poll(timeout_ms) & zmq.POLLIN:
            reply = sock.recv_string()
            try:
                return json.loads(reply)
            except Exception as e:
                logger.error('runBatch bad JSON: %s', e)
                return None
        logger.error('runBatch timed out after %d ms', timeout_ms)
        return None
    finally:
        sock.setsockopt(zmq.LINGER, 0)
        sock.close()
        ctx.term()


def run(remote_ip, selected_sites, runtime_m, tester,
        results_path=None, cycles_per_restart=None):
    results_path = results_path or RESULTS_PATH
    n_cycles = cycles_per_restart if cycles_per_restart is not None else CYCLES_PER_RESTART
    Path(results_path).parent.mkdir(exist_ok=True, parents=True)

    pm = PowerManager()
    stopped = {'flag': False}

    def on_signal(signum, _frame):
        stopped['flag'] = True
        logger.info('cycle_loop received signal %d; will exit after current batch', signum)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    end = datetime.now() + timedelta(minutes=runtime_m)
    batch_count = 0
    total_cycles = 0

    try:
        while datetime.now() < end:
            if stopped['flag'] or os.path.exists(STOP_FLAG):
                break
            batch_count += 1
            t0 = datetime.now()

            pm.power_on(selected_sites)   # power_on settles 1.5s internally
            batch_res = _runBatch_zcu(remote_ip, selected_sites, tester, n_cycles)
            pm.power_off(selected_sites)

            cycles = []
            if batch_res is not None and 'cycles' in batch_res:
                cycles = batch_res['cycles']
                total_cycles += len(cycles)

            # Write one record per test cycle so status_poll/analyze_cycle see
            # the same per-cycle shape as before.
            with open(results_path, 'a') as f:
                for idx, cycle in enumerate(cycles):
                    entry = {
                        'batch': batch_count,
                        'cycle_in_batch': idx + 1,
                        'ts': t0.isoformat(),
                        'results': cycle,
                    }
                    f.write(json.dumps(entry) + '\n')
                if not cycles:
                    err = (batch_res or {}).get('error', 'no_cycles_returned')
                    f.write(json.dumps({
                        'batch': batch_count,
                        'ts': t0.isoformat(),
                        'results': {'error': err},
                    }) + '\n')

            logger.info('batch %d done in %.1fs (%d cycles inside, %d total)',
                        batch_count, (datetime.now() - t0).total_seconds(),
                        len(cycles), total_cycles)

            # Sleep in short slices so SIGTERM is responsive
            slept = 0.0
            while slept < INTER_CYCLE_SLEEP_S and not stopped['flag'] and not os.path.exists(STOP_FLAG):
                time.sleep(0.1)
                slept += 0.1
    finally:
        try:
            pm.power_off(selected_sites)
        except Exception as e:
            logger.error('final power_off failed: %s', e)
        if os.path.exists(STOP_FLAG):
            try:
                os.remove(STOP_FLAG)
            except OSError:
                pass
        logger.info('cycle_loop exiting after %d batches (%d total cycles)',
                    batch_count, total_cycles)

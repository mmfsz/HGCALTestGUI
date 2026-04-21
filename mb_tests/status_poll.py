"""Summarize the local cycle_loop results file.

The cycle loop runs on the Pi now (not the ZCU), so status is read from
the Pi-local JSON file cycle_loop writes to. Returns per-site pass/fail
counts in the shape ThermalTestInProgressScene.display_status expects.
"""

import json
import logging

import cycle_loop

logger = logging.getLogger('HGCALTestGUI.mb_tests.status_poll')


class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):
        summary = {}
        try:
            with open(cycle_loop.RESULTS_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    results = entry.get('results', {})
                    if not isinstance(results, dict) or 'error' in results:
                        continue
                    for site, data in results.items():
                        s = summary.setdefault(site, {'total': 0, 'passed': 0, 'failed': 0})
                        s['total'] += 1
                        if data.get('connection', {}).get('passed', False):
                            s['passed'] += 1
                        else:
                            s['failed'] += 1
        except FileNotFoundError:
            summary = {'error': 'no results file yet'}
        except Exception as e:
            logger.exception('status_poll failed')
            summary = {'error': str(e)}

        conn_test.send('Done.')
        conn_test.send(json.dumps(summary))

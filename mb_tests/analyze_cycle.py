"""Summarize per-site fail/total counts from the local cycle_loop results.

Returns the shape ThermalTestFinalResultsScene.apply_analysis expects:
{site: {'full_id': ..., 'successful': 0/1, 'test_data': {'fails': N, 'total': N}}}

full_id is not populated here (cycle_loop doesn't carry it); the DB-upload
path in the final-results scene skips uploads with no full_id, which is
acceptable until we plumb full_id through.
"""

import json
import logging

import cycle_loop

logger = logging.getLogger('HGCALTestGUI.mb_tests.analyze_cycle')


class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):
        per_site = {}
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
                        s = per_site.setdefault(site, {'total': 0, 'fails': 0})
                        s['total'] += 1
                        if not data.get('connection', {}).get('passed', False):
                            s['fails'] += 1
        except FileNotFoundError:
            conn_test.send('Done.')
            conn_test.send(json.dumps({'error': 'no results file yet'}))
            return
        except Exception as e:
            logger.exception('analyze_cycle failed')
            conn_test.send('Done.')
            conn_test.send(json.dumps({'error': str(e)}))
            return

        out = {}
        for site, counts in per_site.items():
            total = counts['total']
            fails = counts['fails']
            # Same criterion the scene uses: pass if fails==0, or <1/95 fail rate over >60 cycles
            if total == 0:
                successful = 0
            elif fails == 0 or (fails / total < 1/95 and total > 60):
                successful = 1
            else:
                successful = 0
            out[site] = {
                'full_id': None,
                'successful': successful,
                'test_data': {'fails': fails, 'total': total},
            }

        conn_test.send('Done.')
        conn_test.send(json.dumps(out))

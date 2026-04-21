"""Summarize per-site fail/total counts from the local cycle_loop results.

Returns the shape ThermalTestFinalResultsScene.apply_analysis expects:
{site: {'full_id': ..., 'successful': 0/1, 'test_data': {'fails': N, 'total': N}}}

full_id is pulled from the Pi-local cache setup_check wrote after the
fullIDs handshake with the ZCU. Sites without a cached full_id get None
(DB upload in the final-results scene is skipped for those).
"""

import json
import logging
from pathlib import Path

import cycle_loop

logger = logging.getLogger('HGCALTestGUI.mb_tests.analyze_cycle')

# Must match setup_check.FULLIDS_CACHE
FULLIDS_CACHE = str(Path.home() / 'thermal_cycle_fullids.json')


def _load_fullids():
    try:
        with open(FULLIDS_CACHE) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, ValueError):
        pass
    except Exception as e:
        logger.warning('could not load full_ids cache: %s', e)
    return {}


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

        fullids = _load_fullids()
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
            entry = fullids.get(site) or {}
            full_id = entry.get('full_id') if isinstance(entry, dict) else None
            out[site] = {
                'full_id': full_id,
                'successful': successful,
                'test_data': {'fails': fails, 'total': total},
            }

        conn_test.send('Done.')
        conn_test.send(json.dumps(out))

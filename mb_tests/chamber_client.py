"""ZMQ REQ client for the chamber-host EnvBroker.

Used by cycle_loop.py at the start and end of each power-up cycle to grab
the latest (chamber_temp, sensor_temp, humidity, dew_point) reading from
the Alma host that is driving the thermal chamber.

Best-effort: never raises. On timeout / refused connection / bad reply the
function returns {'error': ...} so the test loop continues uninterrupted.
A single warning is logged per outage; the next successful read clears the
suppression so a recovery is also logged once.
"""

import json
import logging

import zmq

logger = logging.getLogger('HGCALTestGUI.mb_tests.chamber_client')

DEFAULT_PORT = 5560
DEFAULT_TIMEOUT_MS = 2000

_warned = False


def get_reading(host, port=DEFAULT_PORT, timeout_ms=DEFAULT_TIMEOUT_MS):
    """Query the chamber-host broker and return the cached reading dict.

    Returns:
      {ts, chamber_temp, sensor_temp, humidity, dew_point, age_s} on success,
      {'error': '<reason>'} on any failure."""
    global _warned
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
    sock.setsockopt(zmq.SNDTIMEO, timeout_ms)
    sock.connect('tcp://{}:{}'.format(host, port))
    try:
        sock.send_string('getEnv')
        reply = sock.recv_string()
        try:
            payload = json.loads(reply)
        except ValueError:
            return {'error': 'bad_json: {}'.format(reply[:80])}
        if 'error' not in payload and _warned:
            logger.info('chamber broker recovered at %s:%d', host, port)
            _warned = False
        return payload
    except zmq.error.Again:
        if not _warned:
            logger.warning('chamber broker unreachable at %s:%d (timeout %dms); '
                           'env will be null this and subsequent cycles until recovery',
                           host, port, timeout_ms)
            _warned = True
        return {'error': 'timeout: {}:{}'.format(host, port)}
    except Exception as e:
        if not _warned:
            logger.warning('chamber broker query failed at %s:%d: %s', host, port, e)
            _warned = True
        return {'error': str(e)}
    finally:
        sock.close()

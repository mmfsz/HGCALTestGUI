import zmq, logging
import json

logger = logging.getLogger('HGCALTestGUI.mb_tests.analyze_cycle')

class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):

        self.remote_ip = gui_cfg["TestHandler"]["remoteip"]
        self.message = ""
        self.conn = conn_test

        # Send analyzeCycle request to ZCU
        self.comm_zcu("analyzeCycle;;{}".format(tester or ""))

        # Forward the ZCU's reply as the test result
        self.conn.send('Done.')
        self.conn.send(self.message if self.message else json.dumps({"error": "No response from ZCU"}))

    def comm_zcu(self, sending_msg):
        context = zmq.Context()

        socket = context.socket(zmq.REQ)
        logger.info("analyze_cycle: Connecting to tcp://%s:5555", self.remote_ip)
        socket.connect("tcp://{ip_address}:5555".format(ip_address=self.remote_ip))

        logger.info("analyze_cycle: Sending request: %s", sending_msg)
        socket.send_string(sending_msg)

        REQUEST_TIMEOUT = 30000  # 30s — analysis may take a moment
        try:
            if (socket.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                self.message = socket.recv_string()
                logger.info("analyze_cycle: Got response (%d chars)", len(self.message))
            else:
                logger.error("analyze_cycle: Poll timed out after %dms", REQUEST_TIMEOUT)
        except Exception as e:
            logger.error("analyze_cycle: Failed to communicate with ZCU: %s", e)

        try:
            socket.close()
            context.term()
        except:
            pass

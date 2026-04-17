import zmq, logging
import json

logger = logging.getLogger('HGCALTestGUI.mb_tests.status_poll')

class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):

        self.remote_ip = gui_cfg["TestHandler"]["remoteip"]
        self.message = ""
        self.conn = conn_test

        # Send statusCycle request to ZCU
        self.comm_zcu("statusCycle;;")

        # Forward the ZCU's reply as the test result
        self.conn.send('Done.')
        self.conn.send(self.message if self.message else json.dumps({"error": "No response from ZCU"}))

    def comm_zcu(self, sending_msg):
        context = zmq.Context()

        socket = context.socket(zmq.REQ)
        logger.info("status_poll: Connecting to tcp://%s:5555", self.remote_ip)
        socket.connect("tcp://{ip_address}:5555".format(ip_address = self.remote_ip))

        logger.info("status_poll: Sending request: %s", sending_msg)
        socket.send_string(sending_msg)

        REQUEST_TIMEOUT = 10000
        try:
            if (socket.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                self.message = socket.recv_string()
                logger.info("status_poll: Got response (%d chars): %.100s", len(self.message), self.message)
            else:
                logger.error("status_poll: Poll timed out after %dms - ZCU REPServer may be stuck", REQUEST_TIMEOUT)
        except Exception as e:
            logger.error("status_poll: Failed to communicate with ZCU: %s", e)

        try:
            socket.close()
            context.term()
        except:
            pass

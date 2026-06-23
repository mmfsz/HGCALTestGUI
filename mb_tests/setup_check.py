import zmq, logging
import multiprocessing as mp
import os
import json
import time
import requests
from pathlib import Path

from power_manager import PowerManager

# Pi-local cache of per-site {full_id, thermal_ready}. Written here at the
# end of setup_check so analyze_cycle can fill the full_id field on results
# uploaded to the MB database.
FULLIDS_CACHE = str(Path.home() / 'thermal_cycle_fullids.json')

STATES = {
    "ready": ("✔", "green"),
    "failure": ("✖", "red"),
    "warning": ("⚠", "orange"),
    "excluded": ("__", "black"),
    "waiting": ("...", "lightgray"),
    "failed3": ("✖⚠", "maroon"),
    "passed": ("✔⚠", "steelblue"),
    "no_db": ("DB✖", "darkviolet")
}
naming_scheme = [
                "SFP0", "1", "2", "3",
                "8", "9", "A3", "A4",
                "4", "5", "6", "7",
                "C1", "C2", "C3", "C4",
                "D1", "D2", "D3", "D4"
                ]

class Test():

    def __init__(self, conn_test, gui_cfg, sites=None, tester=None):

        self.remote_ip = gui_cfg["TestHandler"]["remoteip"]
        self.message = ""

        self.conn = conn_test
        self.queue = mp.Queue()

        output = []
        site_map = {}

        process_zmq = mp.Process(target = self.SUB_ZMQ, args=(conn_test, gui_cfg))
        process_zmq.start()

        # Build comma-separated list of selected iengine site names
        selected_iengines = [naming_scheme[i] for i, s in enumerate(sites) if s]

        if selected_iengines:
            # Power on selected sites before asking the ZCU to read chip IDs.
            # PowerManager logs+skips any board that's not wired, so unreachable
            # sites won't block the flow — they'll just fail the fullIDs read.
            pm = PowerManager()
            pm.power_on(selected_iengines)

            # Send one request to ZCU with all selected iengines
            # Protocol: "fullIDs;SFP0,SFP1,A1,...;tester"
            iengines_str = ",".join(selected_iengines)
            self.comm_zcu("fullIDs;{};{}".format(iengines_str, tester))

            # GET THE JSON FROM THE ZCU
            # ZCU returns {"states": [20-element list], "fullIDs": {site: {full_id, thermal_ready}}}
            # (old format: bare 20-element list — handle for backward compat)
            data = json.loads(self.queue.get())
            if isinstance(data, dict) and 'states' in data:
                states = data['states']
                full_ids_map = data.get('fullIDs', {})
                # The ZCU's get_fullIDs writes the raw DB HTTP response into
                # full_id, which can be an error string like "Could not find
                # full_id associated with LPGBT ID 0x...". Normalize those to
                # None so downstream upload logic skips them cleanly.
                for _site, _entry in full_ids_map.items():
                    if isinstance(_entry, dict):
                        fid = _entry.get('full_id')
                        if isinstance(fid, str) and 'could not find' in fid.lower():
                            _entry['full_id'] = None
                # Merge with any existing cache so rechecks update per-site entries
                # without wiping data from sites that weren't in this request.
                try:
                    with open(FULLIDS_CACHE) as f:
                        existing = json.load(f)
                except (FileNotFoundError, ValueError):
                    existing = {}
                existing.update(full_ids_map)
                with open(FULLIDS_CACHE, 'w') as f:
                    json.dump(existing, f, indent=2)
            else:
                states = data  # legacy shape
                full_ids_map = {}

            # Build output in the format the GUI expects: [["ready", 0], ["failure", 0], ...]
            for i, s in enumerate(sites):
                if s:
                    st = states[i]
                    # DB-miss: ZCU read the board ('ready') but its lpGBT has no
                    # registered full_id (normalized to None above), so its thermal-
                    # cycle result can't be uploaded. Flag distinctly so the operator
                    # does not waste a cycle run on an unuploadable board.
                    _e = full_ids_map.get(naming_scheme[i])
                    if st == 'ready' and (not _e or _e.get('full_id') is None):
                        st = 'no_db'
                    output.append([st, 0])
                else:
                    output.append(["excluded", -1])
        else:
            for i, s in enumerate(sites):
                output.append(["excluded", -1])

        # send done followed by JSON to trigger the end of the test on the GUI
        self.conn.send('Done.')
        self.conn.send(json.dumps(output))

        # TODO SAVE site_map AS A JSON FILE

        process_zmq.terminate()

    def comm_zcu(self, sending_msg):
        context = zmq.Context()

        socket = context.socket(zmq.REQ)
        socket.connect("tcp://{ip_address}:5555".format(ip_address = self.remote_ip))

        print(sending_msg)
        #socket.send_json(sending_msg)
        socket.send_string(sending_msg)
        
        print("Request sent. Waiting for confirmation receipt...")
        # Get the reply
    
        # Recording the number of tries to open the socket and receive a string
        tries = 0


        REQUEST_TIMEOUT = 2000
        REQUEST_RETRIES = 3
        retries_left = REQUEST_RETRIES
        while (len(self.message)< 1) and tries < 1000:
            
            try:

                if(socket.poll(REQUEST_TIMEOUT) &  zmq.POLLIN) != 0:
                    self.message = socket.recv_string()
                    retries_left = REQUEST_RETRIES
                    print("Request received.")
                    break

                retries_left -= 1
                print("No response from server")
                socket.setsockopt(zmq.LINGER, 0)
                socket.close()
                
                # Out of retries
                if retries_left == 0:
                    print("Server seems to be offline, abandoning...")
                    break
                
                print("ThermalREQClient: Attempts remaining...Reconnecting to the server...")

                socket = context.socket(zmq.REQ)
                
                socket.connect("tcp://{ip_address}:5555".format(ip_address = self.remote_ip))
        
                print("ThermalREQClient: Resending...")

                socket.send_string(sending_msg)
                

            except:
                print("No Message received from the request.")
                tries = tries + 1 
            #messagebox.showerror("No Message Received", "REQClient: No message received from the request.")


        # Closes the client so the code in the GUI can continue once the request is sent.
        try:
            print("Trying to close the socket")
            socket.close()
        except:
            print("Unable to close the socket")

    # Responsible for listening for ZMQ messages from zcu
    def SUB_ZMQ(self, conn, gui_cfg):
        
        
        grabbed_ip = gui_cfg["TestHandler"]["remoteip"]
        # Creates the zmq.Context object
        cxt = zmq.Context()
        # Creates the socket as the SUBSCRIBE type
        listen_socket = cxt.socket(zmq.SUB)

        # TODO ZMQ is this always the correct port number?
        listen_socket.connect("tcp://{ip_address}:5556".format(ip_address = grabbed_ip))

        # Sets the topics that the server will listen for
        listen_socket.setsockopt(zmq.SUBSCRIBE, b'print')
        listen_socket.setsockopt(zmq.SUBSCRIBE, b'JSON')

        try:
            while 1 > 0:
                # Splits up every message that is received into topic and message
                # the space around the semi-colon is necessary otherwise the topic and messaage
                # will have extra spaces.
                try:
                    self.topic, self.message = listen_socket.recv_string().split(" ; ")

                except Exception as e:
                    print("SUBClient: There was an error trying to get the message from the socket")
                    print(e)
                                     

                poller = zmq.Poller()
                poller.register(listen_socket, zmq.POLLIN)

                # Tests what topic was received and then does the appropriate code accordingly
                if self.topic == "print":
                    pass

                elif self.topic == "JSON":
                    
                    # Places the message in the queue. the queue.get() is in 
                    # TestInProgressScene's begin_update() method
                    self.queue.put(self.message)

                else:
                    print("Invalid topic sent. Must be 'print' or 'JSON'.")

        except Exception as e:
            print(e)
            print("SUB_ZMQ has crashed. Please restart the software.")

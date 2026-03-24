import zmq, logging
import multiprocessing as mp
import os
import json
import time
import requests

STATES = {
    "ready": ("✔", "green"),
    "failure": ("✖", "red"),
    "warning": ("⚠", "orange"),
    "excluded": ("__", "black"),
    "waiting": ("...", "lightgray"),
    "failed3": ("✖⚠", "maroon"),
    "passed": ("✔⚠", "steelblue")
}
naming_scheme = [
                "SFP0", "SFP1", "SFP2", "SFP3",
                "A1", "A2", "A3", "A4",
                "B1", "B2", "B3", "B4",
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

        for i,s in enumerate(sites):
            # IF THE SITE WAS SELECTED, RUN THE SETUP TEST
            if s:
                # TURN ON POWER FOR THIS SITE

                # TELL THE ZCU TO RUN SETUP AND GIVE IT THE SITE
                #self.comm_zcu({"test": "setup", "site": s})
                self.comm_zcu("lpGBTID;320WMMBD0010002;Maria")

                # GET THE JSON FROM THE SETUP
                data = json.loads(self.queue.get())['data']
                # JSON SHOULD BE IN THE FORM OF {"lpgbt_id": id, "result": true/false}

                # GET SERIAL NUMBER FROM LPGBT
                r=requests.post("{}/get_sn_from_lpgbt_id.py".format(gui_cfg["DBInfo"]["baseURL"]), data={"lpgbt_id": data["test_data"]["DAQ"]["id"]})
                sn = r.text

                # SAVE SN FOR SITE
                #site_map[naming_scheme[i]] = sn
                #print(sn)

                # UPDATE OUTPUT
                # SECOND NUMBER WAS FOR NUMBER OF PREVIOUS THERMAL CYCLE FAILURES
                # COULD MAKE A FUNCTION TO GET THIS AFTER GETTING THE SERIAL NUMBER
                #if data["result"] == "true":
                    #output.append(["ready", 0])
                #else:
                    #output.append(["failure", 0])

                if " " not in sn:
                    output.append(["ready", 0])
                else:
                    output.append(["failure", 0])

                # TURN OFF POWER FOR THIS SITE


                #output.append(["ready", 0])

            else:
                output.append(["excluded", -1])

        # send done followed by JSON to trigger the end of the test on the GUI
        self.conn.send('Done.')
        self.conn.send(json.dumps(output))

        # TODO SAVE site_map AS A JSON FILE

        # will need to uncomment to kill zcu listener
        #process_zmq.terminate()

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
                
                # TODO ZMQ What is "grabbed_ip" supposed to be?
                socket.connect("tcp://{ip_address}:5555".format(ip_address = grabbed_ip))
        
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

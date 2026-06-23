#################################################################################

# Importing Necessary Modules
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
import tkinter.font as font
import logging
from PythonFiles.utils.ConsoleRedirector import ConsoleRedirector
logging.getLogger('PIL').setLevel(logging.WARNING)
# import PythonFiles
import os
import sys
import time
import json
# Importing Necessary Files
from PythonFiles.utils.ThermalREQClient import ThermalREQClient

#################################################################################

logger = logging.getLogger('HGCALTestGUI.PythonFiles.Scenes.ThermalTestInProgressScene')
#FORMAT = '%(asctime)s|%(levelname)s|%(message)s|'
#logging.basicConfig(filename="/home/{}/GUILogs/gui.log".format(os.getlogin()), filemode = 'a', format=FORMAT, level=logging.DEBUG)


# Creating class for the window
class ThermalTestInProgressScene(ttk.Frame):

    #################################################

    def __init__(self, parent, master_frame, data_holder, queue, conn_trigger, conn_result):
        super().__init__(master_frame, width=1300-213, height = 800)

        self.console_text = None
        self.original_stdout = sys.stdout  # Store the default stdout

        self.queue = queue
        self.conn_trigger = conn_trigger
        self.conn_result = conn_result
        self.data_holder = data_holder
        self.parent = parent
        self._poll_id = None
        self._poll_start_time = None

        self.update_frame(parent)

        # Restore to default (in constructor)
        # sys.stdout = self.original_stdout

    #################################################

    def create_style(self, _parent):

        self.s = ttk.Style()

        self.s.tk.call('lappend', 'auto_path', '{}/awthemes-10.4.0'.format(_parent.main_path))
        self.s.tk.call('package', 'require', 'awdark')

        self.s.theme_use('awdark')

    def update_frame(self, parent):
        logger.debug("ParentTestClass: A ThermalTestInProgressScene frame has been updated.")
        # Creates a font to be more easily referenced later in the code
        font_scene = ('Arial', 15)
        
        self.create_style(parent)
        # Create a centralized window for information
        frm_window = ttk.Frame(self, width=870, height = 480)
        frm_window.grid(column=0, row=0, sticky='nsew')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        frm_window.columnconfigure(0, weight=1)
        frm_window.rowconfigure(0, weight=1)

        # Create a label for the tester's name
        lbl_title = ttk.Label(
            frm_window, 
            text = "Thermal Test in Progress", 
            font = ('Arial', '28')
            )
        lbl_title.pack(side = 'top', pady = 5)
        

        # # Create the rectangle canvas
        # canvas = tk.Canvas(frm_window, width=700, height=200)
        # canvas.pack()
        # canvas.create_rectangle(0, 0, 700, 200, fill="lightgray", outline="black")

        # Create console display inside the window
        self.create_console_window(frm_window)
        logger.info("Successfully created console for output on GUI.")
        

        # Create a label for bottom text
        lbl_wait_text = ttk.Label(
            frm_window, 
            text = "Please wait, tests in progress...", 
            font = ('Arial', '14')
            )
        lbl_wait_text.pack(side = 'top', pady = 15)


        #------------------------------

        # Create the countdown timer frame
        self.frm_timer = ttk.Frame(frm_window, padding=10)
        self.frm_timer.pack(side='top', pady=20)

        # Create the label for approximate time remaining
        lbl_approx_time = ttk.Label(self.frm_timer, text="Approximate time remaining:", font=("Arial", 15))
        lbl_approx_time.grid(row=0, column=0, padx=5, pady=5, sticky="w")


        # Create a label to display the countdown timer
        self.timer_label = ttk.Label(self.frm_timer, text="02:00:00", font=("Arial", 24), foreground="red")
        self.timer_label.grid(row=1, column=0, columnspan=3, pady=10)

        # Clear and start the countdown from 2 hours (7200 seconds)
        self.cancel_timer()
        self.remaining_time = 7200
        self.update_timer()






        # Create a logout button
        btn_stop_early = ttk.Button(
            frm_window, 
            text = "Stop Test Early", 
            #relief = tk.RAISED, 
            command = lambda: self.btn_stop_early_action(parent))
        btn_stop_early.pack(anchor = 'center', pady = 5)


        # Create a button to go to test results
        self.btn_next = ttk.Button(
            frm_window, 
            text = "Thermal Test Results", 
            state="disabled",
            #relief = tk.RAISED, 
            command = lambda: self.btn_next_action(parent))
        self.btn_next.pack(anchor = 'center', pady = 5)


        # Create frame for logout button
        frm_logout = ttk.Frame(self)
        frm_logout.grid(column = 2, row = 2, padx = 10, pady = 10, sticky = 'se')
        frm_logout.columnconfigure(0, weight=1)

      
        #if (self.test_idx == 0):     
      
        # Creating the help button
        btn_help = ttk.Button(
            frm_logout,
            #relief = tk.RAISED,
            text = "Help",
            command = lambda: self.help_action(parent)
        )
        btn_help.pack(anchor = 'center', pady = 5)
        

        self.grid_propagate(0)
        
    

    #################################################
    def create_console_window(self, frm_window):
        # Create a frame to hold the console output and scrollbar
        console_frame = tk.Frame(frm_window)
        
        # Create a Text widget for displaying console output
        self.console_text = tk.Text(console_frame, width=85, height=30, wrap="word", state="disabled", bg="black", fg="white")
        self.console_text.pack(side="left", fill="both", expand=True)

        # Create a Scrollbar and attach it to the Text widget
        scrollbar = tk.Scrollbar(console_frame, command=self.console_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.console_text.config(yscrollcommand=scrollbar.set)

        console_frame.pack()

        # Redirect sys.stdout to the Text widget
        # sys.stdout = ConsoleRedirector(self.console_text)


    # Timer functionality
    def update_timer(self):
        # Updates the countdown timer every second.
        if self.remaining_time > 0:
            self.remaining_time -= 1
            hours, remainder = divmod(self.remaining_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.timer_label.config(text=f"{hours:02}:{minutes:02}:{seconds:02}")

            # Schedule the next update
            self._timer_id = self.after(1000, self.update_timer)
        else:
            self.timer_label.config(text="00:00:00", foreground="red")
            self.btn_next.config(state="normal") #Results Button can only be pressed when timer is done

    def set_timer(self, hours, minutes):
        # Manually sets the countdown timer based on function parameters.
        # Convert input to total seconds
        self.remaining_time = (hours * 3600) + (minutes * 60)

        # Update timer display immediately
        self.update_timer()


    def cancel_timer(self):
        # Cancel any scheduled timer updates
        if hasattr(self, "_timer_id"):
            self.after_cancel(self._timer_id)
        
        # Reset the remaining time
        self.remaining_time = 0

        # Update the timer display immediately
        self.timer_label.config(text="00:00:00", foreground="red")

    
    
    def console_print(self, text):
        if self.console_text:
            self.console_text.config(state="normal")
            self.console_text.insert(tk.END, text + "\n")
            self.console_text.see(tk.END)
            self.console_text.config(state="disabled")

    def start_polling(self):
        self._poll_start_time = time.time()
        self.console_print("Thermal cycling started. Polling ZCU for status every 5 minutes...\n")
        # First poll after 10 seconds, then every 5 minutes
        self._poll_id = self.after(300000, self.poll_status)

    def stop_polling(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def poll_status(self):
        logger.info("Polling ZCU for cycle status...")
        gui_cfg = self.data_holder.getGUIcfg()

        checkbox_states = self.data_holder.data_dict.get("checkbox_states", [])
        ready_channels = [s != 'excluded' for s in checkbox_states]

        sending_REQ = ThermalREQClient(
            gui_cfg,
            'status_poll',
            ready_channels,
            self.data_holder.data_dict['user_ID'],
            self.conn_trigger
        )
        # Start checking for the response non-blockingly
        self.after(100, self.wait_for_status)

    def wait_for_status(self):
        if not self.queue.empty():
            signal = self.queue.get()
            if "Results received successfully." in signal:
                message = self.conn_result.recv()
                logger.info("Status received: %s", message)
                self.display_status(message)
                # Schedule next poll in 5 minutes
                self._poll_id = self.after(300000, self.poll_status)
                return
        # Not ready yet, check again in 100ms
        self.after(100, self.wait_for_status)

    def display_status(self, json_string):
        try:
            data = json.loads(json_string)
        except Exception:
            self.console_print("Failed to parse status from ZCU.")
            return

        if "error" in data:
            self.console_print(f"Status error: {data['error']}")
            return

        elapsed = int(time.time() - self._poll_start_time)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        total_cycles = max((c.get("total", 0) for c in data.values()), default=0)
        self.console_print(f"--- Status update (elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}, {total_cycles} cycles) ---")
        for site, counts in data.items():
            passed = counts.get("passed", 0)
            failed = counts.get("failed", 0)
            self.console_print(f"  {site}: {passed} passed, {failed} failed")
        self.console_print("")

    def help_action(self, _parent):
        _parent.help_popup(self)
 

    def btn_stop_early_action(self, _parent):
        self.gui_cfg = self.data_holder.getGUIcfg()
        confirm = messagebox.askyesno(
                title="Confirm Early Stop",
                message="Are you sure you want to stop the test now?\nThermal testing is still in progress!"
            )

        checkbox_states = self.data_holder.data_dict.get("checkbox_states",[])
        ready_channels = []
        for i in range(len(checkbox_states)):
            if checkbox_states[i] != 'excluded':
                ready_channels.append(True)
            else:
                ready_channels.append(False)

        if confirm:
            logger.info("User stopped thermal testing early!")
            self.stop_polling()
            self.cancel_timer()

            logger.info("Sending request to stop thermal testing early...")
            sending_REQ = ThermalREQClient(
                self.gui_cfg,
                'killCycle',
                ready_channels,
                self.data_holder.data_dict['user_ID'],
                self.conn_trigger
                )

            # No explicit power_off: killCycle signals cycle_loop, whose
            # try/finally powers off before exiting. A redundant power_off
            # here would queue another reply on conn_result and race the
            # final scene's analyze_cycle request.

            _parent.set_frame_thermal_final_results()

        pass 


    # Send to the next scene (thermal_final_results)
    def btn_next_action(self, _parent):
        self.gui_cfg = self.data_holder.getGUIcfg()

        response = messagebox.askokcancel(
                title="Confirm Test Finish",
                message="Make sure the green light on top of the Cycler is on before proceeding to results."
            )
        
        checkbox_states = self.data_holder.data_dict.get("checkbox_states",[])
        ready_channels = []
        for i in range(len(checkbox_states)):
            if checkbox_states[i] != 'excluded':
                ready_channels.append(True)
            else:
                ready_channels.append(False)

        if response:
            self.stop_polling()
            self.cancel_timer()
            # sys.stdout = self.original_stdout

            # No explicit power_off: cycle_loop's try/finally already cuts
            # power when it exits at RUNTIME_M. Queuing another power_off
            # here would race the final scene's analyze_cycle on conn_result.
            # The final scene triggers analyze_cycle on entry.

            _parent.set_frame_thermal_final_results()
        

    #################################################      
        
    def get_submit_action(self):
        return self.btn_confirm_action

    def get_parent(self):
        return self.parent


    #################################################



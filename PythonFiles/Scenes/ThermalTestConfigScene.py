#################################################################################

# Importing Necessary Modules
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
import tkinter.font as font
import logging
logging.getLogger('PIL').setLevel(logging.WARNING)
# import PythonFiles
import os

# Importing Necessary Server Files
from PythonFiles.utils.ThermalREQClient import ThermalREQClient

#################################################################################

logger = logging.getLogger('HGCALTestGUI.PythonFiles.Scenes.ThermalTestConfigScene')
#FORMAT = '%(asctime)s|%(levelname)s|%(message)s|'
#logging.basicConfig(filename="/home/{}/GUILogs/gui.log".format(os.getlogin()), filemode = 'a', format=FORMAT, level=logging.DEBUG)

# Creating class for the window
class ThermalTestConfigScene(ttk.Frame):

    #################################################

    def __init__(self, parent, master_frame, data_holder, queue, conn_trigger):
        super().__init__(master_frame, width=1300-213, height = 800)
        self.queue = queue
        self.conn_trigger = conn_trigger
        self.data_holder = data_holder
        self.parent = parent

        # Create a list of boolean values for the checkboxes
        # TODO (FSU) set this up for your ports
        self.checkbox_values = [
                                False, False, False, False,
                                False, False, False, False,
                                False, False, False, False,
                                False, False, False, False,
                                False, False, False, False,
                                ]
        self.bool_checkbox_values = [
                                False, False, False, False,
                                False, False, False, False,
                                False, False, False, False,
                                False, False, False, False,
                                False, False, False, False,
                                ]
        self.naming_scheme = [
                                "SFP0", "1", "2", "3",
                                "8", "9", "A3", "A4",
                                "4", "5", "6", "7",
                                "C1", "C2", "C3", "C4",
                                "D1", "D2", "D3", "D4"
                            ]

        # FSU / cold stand, firmware zcu102-jon-10LD-SFP3 (2026-06-11):
        # Only 9 links are live (LD_1..LD_9). The 20-slot data model above is kept
        # INTACT on purpose — the ZCU's fullIDs returns a fixed 20-element states[]
        # array and setup_check.py / power_manager.py / thermalcycler_mb.iengine_map
        # all index by this position, so shrinking the list would misalign them.
        # Instead we only RENDER the live sites below, so the dangerous/unwired
        # boxes can never be selected. live_indices -> iengine -> LD:
        #   SFP1->1->LD_1  SFP2->2->LD_2  SFP3->3->LD_3
        #   B1->4->LD_4    B2->5->LD_5    B3->6->LD_6   B4->7->LD_7
        #   A1->8->LD_8    A2->9->LD_9
        # SFP0 is index 0 -> iengine 0 -> LD_0, the architectural hang: NEVER expose
        # it (a stray click or Select-All would hang the PS and need a power cycle).
        self.live_indices = [1, 2, 3, 4, 5, 8, 9, 10, 11]

        self.current_engine_selection = None
        
        self.update_frame(parent)

    #################################################

    def create_style(self, _parent):

        self.s = ttk.Style()

        self.s.tk.call('lappend', 'auto_path', '{}/awthemes-10.4.0'.format(_parent.main_path))
        self.s.tk.call('package', 'require', 'awdark')

        self.s.theme_use('awdark')

    def update_frame(self, parent):
        logger.debug("ParentTestClass: A ThermalTestConfigScene frame has been updated.")
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
            text = "Test Configuration", 
            font = ('Arial', '28')
            )
        lbl_title.pack(side = 'top', pady = 10)
        


        # Create a frame to contain the label, dropdown, and confirm button in a single row
        frm_engine_selection = ttk.Frame(frm_window)
        frm_engine_selection.pack(anchor='center', pady=10)

        # Create a label for confirming test
        lbl_active = ttk.Label(
            frm_window, 
            text = "Select active sites:", 
            font = ('Arial', '24')
            )
        lbl_active.pack(side = 'top', pady = 15)




        # Create a frame to hold the checkboxes
        checkbox_frame = ttk.Frame(frm_window)
        checkbox_frame.pack(pady=10)

        # Keep a BooleanVar for all 20 positions so the data model / downstream
        # index alignment is preserved, but only RENDER the live sites
        # (self.live_indices) so SFP0 (LD_0 hang) and the unwired sites can never
        # be checked. Non-rendered positions stay False forever.
        # 2026-06-17: keep a BooleanVar for ALL 20 positions so the downstream
        # 20-element model (bool_checkbox_values -> setup_check/thermal_cycle/
        # power_off naming_scheme -> ZCU states[]) stays index-aligned; only the
        # live sites are rendered. naming_scheme now holds chamber-slot numbers
        # '1'..'9' (slot N == iengine N), so render in slot order for the operator.
        for i in range(20):
            chk_var = tk.BooleanVar()
            chk_var.set(False)
            self.checkbox_values[i] = chk_var

        render_order = sorted(self.live_indices, key=lambda i: int(self.naming_scheme[i]))
        for live_pos, i in enumerate(render_order):
            col = live_pos // 5
            row = live_pos % 5
            checkbox = ttk.Checkbutton(
                checkbox_frame,
                text=f"Slot {self.naming_scheme[i]}",
                variable=self.checkbox_values[i],
                command=lambda idx=i: self.checkbox_selected(idx)  # Pass index to function
            )
            checkbox.grid(row=row, column=col, padx=10, pady=5, sticky="w")


        # Create a frame for the select/deselect buttons
        frm_select = ttk.Frame(frm_window)
        # Create "Select All" button
        btn_select_all = ttk.Button(
            frm_select,
            text="Select All",
            command=lambda: self.btn_select_all_action(parent)
        )
        btn_select_all.pack(side='left', padx=10)

        # Create "Deselect All" button
        btn_deselect_all = ttk.Button(
            frm_select,
            text="Deselect All",
            command=lambda: self.btn_deselect_all_action(parent)
        )
        btn_deselect_all.pack(side='left', padx=5)

        frm_select.pack(anchor='center', pady=10)



        # Create a label for bottom text
        lbl_begin_text = ttk.Label(
            frm_window, 
            text = "Once all engines are properly connected, click the button below to begin the setup check:", 
            font = ('Arial', '20')
            )
        lbl_begin_text.pack(side = 'top', pady = 25)


        # Create a logout button
        btn_setup_check = ttk.Button(
            frm_window, 
            text = "Run Setup Check", 
            #relief = tk.RAISED, 
            command = lambda: self.btn_setup_check_action(parent))
        btn_setup_check.pack(anchor = 'center', pady = 5)


        # Create frame for logout button
        frm_logout = ttk.Frame(self)
        frm_logout.grid(column = 2, row = 2, padx=10, pady=10, sticky = 'se')
        frm_logout.columnconfigure(0, weight=1)

        # Create a logout button
        btn_logout = ttk.Button(
            frm_logout, 
            text = "Logout", 
            #relief = tk.RAISED, 
            command = lambda: self.btn_logout_action(parent))
        btn_logout.pack(anchor = 'center', pady = 5)


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

    
    
    def help_action(self, _parent):
        _parent.help_popup(self)
 
    def checkbox_selected(self, idx):
        self.gui_cfg = self.data_holder.getGUIcfg()
        
        self.bool_checkbox_values = []

        for chk_var in self.checkbox_values:
            value = chk_var.get() 
            # print(f"Value: {value} (Type: {type(value)})")  # Debugging output
            self.bool_checkbox_values.append(value)  # Ensure proper boolean conversion

        # print("simple_checkbox_values:", simple_checkbox_values)
        self.data_holder.data_dict["checkbox_selection"] = self.bool_checkbox_values



    def btn_setup_check_action(self, _parent):
        
        Checkboxes = all(not value for value in self.bool_checkbox_values)

        if Checkboxes == True:
            response = messagebox.showwarning(
                title="Missing selection!",
                message="You need to select at least one channel!"
            )
        else:

            logger.info("Sending request to do setup check...")
            sending_REQ = ThermalREQClient(
                self.gui_cfg, 
                "setup_check",
                self.bool_checkbox_values, 
                self.data_holder.data_dict['user_ID'], 
                self.conn_trigger
                )
        
            _parent.set_frame_thermal_setup_results()


    def btn_select_all_action(self, _parent):
        
        self.select_all_checkbox()
        self.checkbox_selected(0)

        pass

    def btn_deselect_all_action(self, _parent):

        self.deselect_all_checkbox()
        self.checkbox_selected(0)       
        
        pass

    # def btn_confirm_engine_action(self, _parent):
        

    #     pass


    def run_all_action(self, _parent):
       
        _parent.run_all_tests() 
        
    # Since BooleanVar is linked to the checkboxes, updating it will instantly reflect on the GUI.
    # Only touch the live (rendered) sites — never set SFP0/LD_0 or the unwired sites.
    def select_all_checkbox(self):
        # Set the live checkbox values to True
        for i in self.live_indices:
            self.checkbox_values[i].set(True)  # Update BooleanVar

    # Since BooleanVar is linked to the checkboxes, updating it will instantly reflect on the GUI.
    def deselect_all_checkbox(self):
        for i in self.live_indices:
            self.checkbox_values[i].set(False)  # Update BooleanVar



    #################################################
      
    def get_submit_action(self):
        return self.btn_confirm_action

    def get_parent(self):
        return self.parent
    
    #################################################

    # functionality for the logout button
    def btn_logout_action(self, _parent):
        result = messagebox.askyesno("Confirm Logout", "Are you sure you want to logout?")
        if result:
            _parent.set_frame_login_frame()

    #################################################





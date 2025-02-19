""" 
.. module:: vismapframe

:synopsis: *Module to handle visualization with maps.*

The module contains the class ``VisMapFrame`` to build the frame in which the user enters the plotting parameters. 
A time-interval of interest is to be specified, and the X, Y data corresponding to this time-interval shall be plotted. 
A single x-variable (belonging to a satellite) is selected (see the class ``Plot2DVisVars`` for list of possible variables).
Multiple y-variables may be selected to be plotted on the same figure. 

The module currently only allows plotting of satellite orbit-propagation parameters (and hence association of only the satellite 
(no need of sensor) with the variable is sufficient).

"""
from tkinter import ttk 
import tkinter as tk
from eosim import config
from eosim.gui.mapprojections import Mercator, EquidistantConic, LambertConformal, Robinson, LambertAzimuthalEqualArea, Gnomonic
import instrupy, orbitpy
import pandas as pd
import numpy as np
import tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
# Implement the default Matplotlib key bindings.
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

import cartopy.crs as ccrs
import logging

logger = logging.getLogger(__name__)

class PlotMapVars(instrupy.util.EnumEntity):
    """ This class holds and handles the variables which can be plotted (either on x or y axis). 
        The class-variables are all the variables make up all the possible variables which can be plotted. 
        The class also includes two functions which aid in the retrieval of the variable-data from the OrbitPy datafiles.
    
    """
    TIME = "Time"
    ALT = "Altitude [km]"
    INC = "Inclination [deg]"
    TA = "True Anomaly [km]"
    RAAN = "RAAN [deg]"
    AOP = "AOP [deg]"
    ECC = "ECC"
    SPD = "ECI Speed [km/s]"

    @classmethod
    def get_orbitpy_file_column_header(cls, var):
        """ Function returns the OrbitPy column header (label) corresponding to the input variable. 
            If not present, ``False`` is returned indicating a "derived" variable.
        """
        if(var==cls.INC):
            return "inc [deg]"
        elif(var==cls.RAAN):
            return "raan [deg]"
        elif(var==cls.AOP):
            return "aop [deg]"
        elif(var==cls.TA):
            return "ta [deg]"
        elif(var==cls.ECC):
            return "ecc"
        else:
            return False # could be a derived variable
    
    @classmethod
    def get_data_from_orbitpy_file(cls, sat_df, sat_id, var, step_size, epoch_JDUT1):
        """ Extract the variable data from the input orbit-propagation data. 

            :param sat_df: Dataframe corresponding to the orbit-propagation data.
            :paramtype sat_df: :class:`pandas.DataFrame`

            :param sat_id: Satellite identifier.
            :paramtype sat_id: str or int

            :param var: Variable of interest to be plotted (on either the X or Y axis).
            :paramtype var: class-variable of the ``Plot2DVisVars`` class.

            :param step_size: step-size
            :paramtype step_size: float

            :param epoch_JDUT1: Epoch in Julian Date UT1 at which the input data is referenced.
            :paramtype epoch_JDUT1: float

            :return: Tuple containing the variable plot-name (label) and the corresponding data to be plotted. 
            :rtype: tuple

        """
        _header = PlotMapVars.get_orbitpy_file_column_header(var)     
        if(_header is not False):                     
            if _header == sat_df.index.name:
                data = sat_df.index
            else:
                data = sat_df[_header]
        else:
            # a derived variable
            if(var == cls.TIME):
                data = np.array(sat_df.index) * step_size # index = "time index"
                _header = 'time [s]'
            elif(var == cls.ALT):
                sat_dist = []
                sat_dist = np.array(sat_df["x [km]"])*np.array(sat_df["x [km]"]) + np.array(sat_df["y [km]"])*np.array(sat_df["y [km]"]) + np.array(sat_df["z [km]"])*np.array(sat_df["z [km]"])
                sat_dist = np.sqrt(sat_dist)
                data = np.array(sat_dist) - instrupy.util.Constants.radiusOfEarthInKM
                _header = 'alt [km]'
            elif(var==cls.SPD):
                data = np.array(sat_df["vx [km/s]"])*np.array(sat_df["vx [km/s]"]) + np.array(sat_df["vy [km/s]"])*np.array(sat_df["vy [km/s]"]) + np.array(sat_df["vz [km/s]"])*np.array(sat_df["vz [km/s]"])
                data = np.sqrt(data)
                _header = 'speed [km/s]'

        return (str(sat_id)+'.'+_header, data)

class MapVisPlotAttibutes():
    """ Container class to hold and handle the plot attributes which are specified by the user.
    """
    def __init__(self, proj=None, sat_id=None, var=None, time_start=None, time_end=None):
        self.sat_id = sat_id if sat_id is not None else list() # satellite-identifier, a list since multiple plots are possible on a single map
        self.var = var if var is not None else list() # variable, a list since multiple plots are possible on a single map
        self.proj = proj if proj is not None else None
        self.time_start = time_start if time_start is not None else None
        self.time_end = time_end if time_end is not None else None
    
    def update_variables(self, sat_id, var):
        self.sat_id.append(sat_id)
        self.var.append(var)
    
    def update_projection(self, proj):
        self.proj = proj

    def reset_variables(self):
        self.sat_id =  list()
        self.var = list()

    def update_time_interval(self, time_start, time_end):
        self.time_start = time_start
        self.time_end = time_end

    def get_projection(self):
        return self.proj
    
    def get_variables(self):
        return [self.sat_id, self.var]

    def get_time_interval(self):
        return [self.time_start, self.time_end]

class VisMapFrame(ttk.Frame):    
    """ Primary class to create the frame and the widgets."""
    def __init__(self, win, tab):

        self.vis_map_attr = MapVisPlotAttibutes() # instance variable storing the plot attributes

        # map plots frame
        vis_map_frame = ttk.Frame(tab)
        vis_map_frame.pack(expand = True, fill ="both", padx=10, pady=10)
        vis_map_frame.rowconfigure(0,weight=1)
        vis_map_frame.rowconfigure(1,weight=1)
        vis_map_frame.columnconfigure(0,weight=1)
        vis_map_frame.columnconfigure(1,weight=1)  
        vis_map_frame.columnconfigure(2,weight=1)             

        vis_map_time_frame = ttk.LabelFrame(vis_map_frame, text='Set Time Interval', labelanchor='n')
        vis_map_time_frame.grid(row=0, column=0, sticky='nswe', padx=(10,0))
        vis_map_time_frame.rowconfigure(0,weight=1)
        vis_map_time_frame.rowconfigure(1,weight=1)
        vis_map_time_frame.rowconfigure(2,weight=1)
        vis_map_time_frame.columnconfigure(0,weight=1)
        vis_map_time_frame.columnconfigure(1,weight=1)

        vis_map_proj_frame = ttk.LabelFrame(vis_map_frame, text='Set Map Projection', labelanchor='n')
        vis_map_proj_frame.grid(row=0, column=1, sticky='nswe')
        vis_map_proj_frame.columnconfigure(0,weight=1)
        vis_map_proj_frame.rowconfigure(0,weight=1)
        vis_map_proj_frame.rowconfigure(1,weight=1)

        vis_map_proj_type_frame = ttk.Frame(vis_map_proj_frame)
        vis_map_proj_type_frame.grid(row=0, column=0)       
        proj_specs_container = ttk.Frame(vis_map_proj_frame)
        proj_specs_container.grid(row=1, column=0, sticky='nswe')
        proj_specs_container.columnconfigure(0,weight=1)
        proj_specs_container.rowconfigure(0,weight=1)

        proj_specs_container_frames = {}
        for F in (Mercator, EquidistantConic, LambertConformal,Robinson,LambertAzimuthalEqualArea,Gnomonic):
            page_name = F.__name__
            self._prj_typ_frame = F(parent=proj_specs_container, controller=self)
            proj_specs_container_frames[page_name] = self._prj_typ_frame
            self._prj_typ_frame.grid(row=0, column=0, sticky="nsew")
        self._prj_typ_frame = proj_specs_container_frames['Mercator'] # default projection type
        self._prj_typ_frame.tkraise()

        vis_map_var_frame = ttk.LabelFrame(vis_map_frame, text='Set Variable(s)', labelanchor='n')
        vis_map_var_frame.grid(row=0, column=2, sticky='nswe')
        vis_map_var_frame.columnconfigure(0,weight=1)
        vis_map_var_frame.rowconfigure(0,weight=1)
        vis_map_var_frame.rowconfigure(1,weight=1)

        vis_map_plot_frame = ttk.Frame(vis_map_frame)
        vis_map_plot_frame.grid(row=1, column=0, columnspan=3, sticky='nswe', pady=(10,2)) 
        vis_map_plot_frame.columnconfigure(0,weight=1)
        vis_map_plot_frame.columnconfigure(1,weight=1) 
        vis_map_plot_frame.rowconfigure(0,weight=1)

        # time interval frame
        ttk.Label(vis_map_time_frame, text="Time (hh:mm:ss) from mission-epoch", wraplength="110", justify='center').grid(row=0, column=0,columnspan=2,ipady=5)
        ttk.Label(vis_map_time_frame, text="From").grid(row=1, column=0, sticky='ne')

        self.vis_map_time_from_entry = ttk.Entry(vis_map_time_frame, width=10, takefocus = False)
        self.vis_map_time_from_entry.grid(row=1, column=1, sticky='nw', padx=10)
        self.vis_map_time_from_entry.insert(0,'00:00:00')
        self.vis_map_time_from_entry.bind("<FocusIn>", lambda args: self.vis_map_time_from_entry.delete('0', 'end'))
        
        ttk.Label(vis_map_time_frame, text="To").grid(row=2, column=0, sticky='ne')
        self.vis_map_time_to_entry = ttk.Entry(vis_map_time_frame, width=10, takefocus = False)
        self.vis_map_time_to_entry.grid(row=2, column=1, sticky='nw', padx=10)
        self.vis_map_time_to_entry.insert(0,'10:00:00')
        self.vis_map_time_to_entry.bind("<FocusIn>", lambda args: self.vis_map_time_to_entry.delete('0', 'end'))

        # projection  
        PROJ_TYPES = ['Mercator', 'EquidistantConic', 'LambertConformal', 'Robinson', 'LambertAzimuthalEqualArea', 'Gnomonic']   
             
        self._proj_type = tk.StringVar() # using self so that the variable is retained even after exit from the function
        self._proj_type.set("Mercator") # initialize

        def proj_type_combobox_change(event=None):
            if self._proj_type.get() == "Mercator":
                self._prj_typ_frame = proj_specs_container_frames['Mercator']
            elif self._proj_type.get() == "EquidistantConic":
                self._prj_typ_frame = proj_specs_container_frames['EquidistantConic']
            elif self._proj_type.get() == "LambertConformal":
                self._prj_typ_frame = proj_specs_container_frames['LambertConformal']
            elif self._proj_type.get() == "Robinson":
                self._prj_typ_frame = proj_specs_container_frames['Robinson']
            elif self._proj_type.get() == "LambertAzimuthalEqualArea":
                self._prj_typ_frame = proj_specs_container_frames['LambertAzimuthalEqualArea']
            elif self._proj_type.get() == "Gnomonic":
                self._prj_typ_frame = proj_specs_container_frames['Gnomonic']
            self._prj_typ_frame.tkraise()

        projtype_combo_box = ttk.Combobox(vis_map_proj_type_frame, 
                                        values=PROJ_TYPES, textvariable = self._proj_type, width=25)
        projtype_combo_box.current(0)
        projtype_combo_box.grid(row=0, column=0)
        projtype_combo_box.bind("<<ComboboxSelected>>", proj_type_combobox_change)

        vis_map_var_sel_btn = ttk.Button(vis_map_var_frame, text="Var(s)", command=self.click_select_var_btn)
        vis_map_var_sel_btn.grid(row=0, column=0)
        self.vis_map_var_sel_disp = tk.Text(vis_map_var_frame, state='disabled',height = 2, width = 3, background="light grey")
        self.vis_map_var_sel_disp.grid(row=1, column=0, sticky='nsew', padx=20, pady=20) 
        
        # plot frame
        plot_btn = ttk.Button(vis_map_plot_frame, text="Plot", command=self.click_plot_btn)
        plot_btn.grid(row=0, column=0, sticky='e', padx=20)

    def click_select_var_btn(self):
        """ Create window to ask what should be the y-variable(s). Multiple variables can be configured."""
        # reset any previously configured variables
        self.vis_map_attr.reset_variables()
        
        # create window to ask which satellite 
        select_var_win = tk.Toplevel()
        select_var_win.rowconfigure(0,weight=1)
        select_var_win.rowconfigure(1,weight=1)
        select_var_win.columnconfigure(0,weight=1)
        select_var_win.columnconfigure(1,weight=1)

        select_sat_win_frame = ttk.LabelFrame(select_var_win, text='Select Satellite')
        select_sat_win_frame.grid(row=0, column=0, padx=10, pady=10) 

        select_var_frame = ttk.LabelFrame(select_var_win, text='Select Variable')
        select_var_frame.grid(row=0, column=1, padx=10, pady=10) 

        okcancel_frame = ttk.Label(select_var_win)
        okcancel_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10) 

        # place the widgets in the frame
        available_sats = [x._id for x in config.mission.spacecraft]# get all available satellite-ids for which outputs are available
 
        sats_combo_box = ttk.Combobox(select_sat_win_frame, 
                                        values=available_sats)
        sats_combo_box.current(0)
        sats_combo_box.grid(row=0, column=0)

        self._vis_map_var= tk.StringVar() # using self so that the variable is retained even after exit from the function, make sure variable name is unique
        j = 0
        k = 0
        for _var in list(PlotMapVars):
            var_rbtn = ttk.Radiobutton(select_var_frame, text=_var, variable=self._vis_map_var, value=_var)
            var_rbtn.grid(row=j, column=k, sticky='w')
            j = j + 1
            if(j==5):
                j=0
                k=k+1

        def click_ok_btn():
            self.vis_map_attr.update_variables(sats_combo_box.get(), self._vis_map_var.get())
            
        def click_exit_btn():
            self.vis_map_var_sel_disp.configure(state='normal')
            self.vis_map_var_sel_disp.delete(1.0,'end')
            [sats, vars] = self.vis_map_attr.get_variables()
            vars_str = [str(sats[k]+'.'+vars[k]) for k in range(0,len(sats))]
            self.vis_map_var_sel_disp.insert(1.0,' '.join(vars_str))
            self.vis_map_var_sel_disp.configure(state='disabled')
            select_var_win.destroy()

        ok_btn = ttk.Button(okcancel_frame, text="Add", command=click_ok_btn, width=15)
        ok_btn.grid(row=0, column=0, sticky ='e')
        cancel_btn = ttk.Button(okcancel_frame, text="Exit", command=click_exit_btn, width=15)
        cancel_btn.grid(row=0, column=1, sticky ='w') 

    def update_time_interval_in_attributes_variable(self):
        """ Update the time-interval of interest from the user-input."""
        # read the plotting time interval 
        time_start = str(self.vis_map_time_from_entry.get()).split(":") # split and reverse list
        time_start.reverse()
        # convert to seconds
        x = 0
        for k in range(0,len(time_start)):
            x = x + float(time_start[k]) * (60**k)
        time_start_s = x

        time_end = str(self.vis_map_time_to_entry.get()).split(":") # split and reverse list
        time_end.reverse()
        # convert to seconds
        x = 0
        for k in range(0,len(time_end)):
            x = x + float(time_end[k]) * (60**k)
        time_end_s = x
        
        self.vis_map_attr.update_time_interval(time_start_s, time_end_s)

    def update_projection_in_attributes_variable(self):
        proj = self._prj_typ_frame.get_specs()
        self.vis_map_attr.update_projection(proj)

    def click_plot_btn(self):
        """ Make projected plots of the variables indicated in :code:`vis_map_attr` instance variable. 
        """
        self.update_time_interval_in_attributes_variable()
        self.update_projection_in_attributes_variable()

        [time_start_s, time_end_s] = self.vis_map_attr.get_time_interval()
        proj = self.vis_map_attr.get_projection()

        # get the variable data
        [sat_id, var] = self.vis_map_attr.get_variables()

        # get the epoch and time-step from the file belonging to the first variable (this shall be the same for all the variables, simply choosing the first one)
        sat_prop_out_info = orbitpy.util.OutputInfoUtility.locate_output_info_object_in_list(out_info_list=config.mission.outputInfo,
                                                                            out_info_type=orbitpy.util.OutputInfoUtility.OutputInfoType.PropagatorOutputInfo,
                                                                            spacecraft_id=sat_id[0]
                                                                            )                                                                            
        sat_state_fp = sat_prop_out_info.stateCartFile
        
        # read the epoch and time-step size and fix the start and stop indices
        (epoch_JDUT1, step_size, duration) = orbitpy.util.extract_auxillary_info_from_state_file(sat_state_fp)

        logger.debug("epoch_JDUT1 is " + str(epoch_JDUT1))
        logger.debug("step_size is " + str(step_size))

        time_start_index = int(time_start_s/step_size)
        time_end_index = int(time_end_s/step_size)

        sat_state_df = pd.read_csv(sat_state_fp,skiprows = [0,1,2,3]) 
        sat_state_df.set_index('time index', inplace=True)

        # check if the user-specified time interval is within bounds
        min_time_index = min(sat_state_df.index)
        max_time_index = max(sat_state_df.index)
        if(time_start_index < min_time_index or time_start_index > max_time_index or 
           time_end_index < min_time_index or time_end_index > max_time_index or
           time_start_index > time_end_index):
            logger.info("Please enter valid time-interval.")
            return

        sat_state_df = sat_state_df.iloc[time_start_index:time_end_index]
        plt_data = pd.DataFrame(index=sat_state_df.index)
        # iterate over the list of vars 
        num_vars = len(var)
        varname = []
        for k in range(0,num_vars): 
            # extract the y-variable data from of the particular satellite
            # search for the orbit-propagation data corresponding to the satellite with identifier = sat_id[k]
            _sat_prop_out_info = orbitpy.util.OutputInfoUtility.locate_output_info_object_in_list(out_info_list=config.mission.outputInfo,
                                                                            out_info_type=orbitpy.util.OutputInfoUtility.OutputInfoType.PropagatorOutputInfo,
                                                                            spacecraft_id=sat_id[k]
                                                                            )
            _sat_state_fp = _sat_prop_out_info.stateCartFile
            _sat_kepstate_fp = _sat_prop_out_info.stateKeplerianFile
            # load the cartesian eci state data, get data only in the relevant time-interval
            _sat_state_df = pd.read_csv(_sat_state_fp, skiprows = [0,1,2,3]) 
            _sat_state_df.set_index('time index', inplace=True)
            _sat_state_df = _sat_state_df.iloc[time_start_index:time_end_index]
            # load the keplerian state data, get data only in the relevant time-interval
            _sat_kepstate_df = pd.read_csv(_sat_kepstate_fp, skiprows = [0,1,2,3]) 
            _sat_kepstate_df.set_index('time index', inplace=True)
            _sat_kepstate_df = _sat_kepstate_df.iloc[time_start_index:time_end_index]
            
            _sat_df = pd.concat([_sat_state_df, _sat_kepstate_df], axis=1)

            # get the (lat, lon) coords 
            _lat = np.zeros((len(_sat_df["x [km]"]), 1))
            _lon = np.zeros((len(_sat_df["x [km]"]), 1))
            sat_df_index = list(_sat_df.index)
            sat_df_x = list(_sat_df["x [km]"])
            sat_df_y = list(_sat_df["y [km]"])
            sat_df_z = list(_sat_df["z [km]"])
            for m in range(0,len(_sat_df["x [km]"])):
                time = epoch_JDUT1 + sat_df_index[m] * step_size * 1/86400  
                [_lat[m], _lon[m], _y] = instrupy.util.GeoUtilityFunctions.eci2geo([sat_df_x[m], sat_df_y[m], sat_df_z[m]], time)
          
            # add new column with the data
            (_varname, _data) = PlotMapVars.get_data_from_orbitpy_file(sat_df=_sat_df, sat_id=sat_id[k], var=var[k], step_size=step_size, epoch_JDUT1=epoch_JDUT1)
            varname.append(_varname)
            plt_data[_varname+'lat [deg]'] = _lat
            plt_data[_varname+'lon [deg]'] = _lon
            plt_data[_varname] = _data
        
        # make the plot
        fig_win = tk.Toplevel()
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(1,1,1,projection=proj) 
        ax.stock_img()        
        for k in range(0,num_vars):            
            s = ax.scatter(plt_data.loc[:,varname[k]+'lon [deg]'] , plt_data.loc[:,varname[k]+'lat [deg]'], c=plt_data.loc[:,varname[k]], transform=ccrs.PlateCarree()) # TODO: Verify the use of the 'transform' parameter https://scitools.org.uk/cartopy/docs/latest/tutorials/understanding_transform.html,
                                                                                                   #       https://stackoverflow.com/questions/42237802/plotting-projected-data-in-other-projectons-using-cartopy
            cb = fig.colorbar(s)
            cb.set_label(varname[k])
        ax.coastlines()
        
        #cbar.set_clim(-.5, .5) # set limits of color map
                
        canvas = FigureCanvasTkAgg(fig, master=fig_win)  # A tk.DrawingArea.
        canvas.draw()
        canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

        toolbar = NavigationToolbar2Tk(canvas, fig_win)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

     
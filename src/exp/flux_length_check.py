from qm.qua import *
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm import SimulationConfig
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.plot import interrupt_on_close
from qualang_tools.loops import from_array
from exp.RO_macros import multiRO_declare, multiRO_measurement, multiRO_pre_save
import matplotlib.pyplot as plt
import warnings
# from common_fitting_func import *
warnings.filterwarnings("ignore")
import exp.config_par as gc
from qualang_tools.units import unit
u = unit(coerce_to_integer=True)
from exp.config_par import get_offset

import xarray as xr
import time
from exp.QMMeasurement import QMMeasurement

import numpy as np

class Flux_length_check( QMMeasurement ):
    """

    Parameters:
    ro_elements is RO \n
    xy_elements is XY \n
    Z_elements is Z \n

    set_flux_quanta: \n
        unit in flux quanta, ref to integer flux quanta \n
    flux_quanta: \n
        unit in voltage.\n
    freq_range: \n
        is a tuple ( upper bound, lower bound), unit in MHz, ref to idle IF \n
    freq_resolution: \n
        is a float, unit in MHz, ref to idle IF \n
    flux_type: \n
        enumerate offset, pulse

    return: \n
    dataset \n
    coors: ["mixer","frequency"]\n
    attrs: ref_xy_IF, ref_xy_LO, z_offset\n
    """

    def __init__( self, config, qmm: QuantumMachinesManager ):
        super().__init__( config, qmm )

        self.ro_elements = ["q1_ro"]
        self.z_elements = ["q1_z"]
        self.xy_elements = ["q1_xy"]
        
        self.preprocess = "ave"
        self.initializer = None
        
        self.flux_type = "pulse" #offset or pulse
        self.xy_driving_time = 10
        self.xy_amp_mod = 0.01
        self.flux_quanta = 0.6
        self.set_flux_quanta = 0.1

        self.freq_range = ( -10, 10 )
        self.freq_resolution = 0.2

        

    def _get_qua_program( self ):
        
        self.qua_freqs = self._lin_freq_array()

        self.qua_xy_driving_time = self.xy_driving_time/4 *u.us
        self._attribute_config()

        with program() as qua_prog:

            iqdata_stream = multiRO_declare( self.ro_elements )
            n = declare(int)  
            n_st = declare_stream()
            df = declare(int)  
            if (self.flux_type == "offset"):
                for i, z in enumerate(self.z_elements):
                    set_dc_offset( self.z_elements[0], "single", get_offset(self.z_elements[0],self.config)+self.set_flux_quanta*self.flux_quanta )
            elif(self.flux_type == "pulse"):
                pass
            else:
                print("no such flux_type")
            with for_(n, 0, n < self.shot_num, n + 1):
                with for_(*from_array(df, self.qua_freqs)):

                    # Initialization
                    if self.initializer is None:
                        wait(1*u.us, self.ro_elements)
                    else:
                        try:
                            self.initializer[0](*self.initializer[1])
                        except:
                            print("initializer didn't work!")
                            wait(1*u.us, self.ro_elements)

                    # operation
                    if (self.flux_type == "offset"):
                        pass
                    elif(self.flux_type == "pulse"):
                        for i, z in enumerate(self.z_elements):
                            play( "const"*amp( self.set_flux_quanta*self.flux_quanta/self.config["waveforms"][f"{self.z_elements[0]}_const_wf"]["sample"] ), z, duration=self.qua_xy_driving_time+10)
                            wait(5)
                    else:
                        print("no such flux_type")
                    
                    for i, xy in enumerate(self.xy_elements):
                        update_frequency( xy, self.ref_xy_IF[i] +df )
                        play("const"*amp( self.xy_amp_mod ), xy, duration=self.qua_xy_driving_time)
                    align()

                    # measurement
                    multiRO_measurement( iqdata_stream, self.ro_elements, weights='rotated_'  )

                # assign(index, index + 1)
                save(n, n_st)
            with stream_processing():
                n_st.save("iteration")
                multiRO_pre_save( iqdata_stream, self.ro_elements, (len(self.qua_freqs),))

        return qua_prog
        

        
    
    def _get_fetch_data_list( self ):
        ro_ch_name = []
        for r_name in self.ro_elements:
            ro_ch_name.append(f"{r_name}_I")
            ro_ch_name.append(f"{r_name}_Q")

        data_list = ro_ch_name + ["iteration"]   
        return data_list
    
    def _data_formation( self ):
        freqs_mhz = self.qua_freqs/1e6
        coords = { 
            "mixer":np.array(["I","Q"]), 
            "frequency": freqs_mhz,
            #"prepare_state": np.array([0,1])
            }
        match self.preprocess:
            case "shot":
                dims_order = ["mixer","shot","frequency"]
                coords["shot"] = np.arange(self.shot_num)
            case _:
                dims_order = ["mixer","frequency"]

        output_data = {}
        for r_idx, r_name in enumerate(self.ro_elements):
            data_array = np.array([ self.fetch_data[r_idx*2], self.fetch_data[r_idx*2+1]])
            output_data[r_name] = ( dims_order, np.squeeze(data_array))

        dataset = xr.Dataset( output_data, coords=coords )

        # dataset = dataset.transpose("mixer", "prepare_state", "frequency", "amp_ratio")

        self._attribute_config()
        dataset.attrs["ro_LO"] = self.ref_ro_LO
        dataset.attrs["ro_IF"] = self.ref_ro_IF
        dataset.attrs["xy_LO"] = self.ref_xy_LO
        dataset.attrs["xy_IF"] = self.ref_xy_IF
        dataset.attrs["z_offset"] = self.z_offset

        dataset.attrs["z_amp_const"] = self.z_amp
        dataset.attrs["flux_type"] = self.flux_type
        dataset.attrs["xy_driving_time"] = self.xy_driving_time
        dataset.attrs["xy_amp_mod"] = self.xy_amp_mod
        dataset.attrs["flux_quanta"] = self.flux_quanta
        dataset.attrs["set_flux_quanta"] = self.set_flux_quanta

        dataset.attrs["freq_range"] = self.freq_range
        dataset.attrs["freq_resolution"] = self.freq_resolution
        return dataset

    def _attribute_config( self ):
        self.ref_ro_IF = []
        self.ref_ro_LO = []
        for r in self.ro_elements:
            self.ref_ro_IF.append(gc.get_IF(r, self.config))
            self.ref_ro_LO.append(gc.get_LO(r, self.config))

        self.ref_xy_IF = []
        self.ref_xy_LO = []
        for xy in self.xy_elements:
            self.ref_xy_IF.append(gc.get_IF(xy, self.config))
            self.ref_xy_LO.append(gc.get_LO(xy, self.config))

        self.z_offset = []
        self.z_amp = []
        for z in self.z_elements:
            self.z_offset.append( gc.get_offset(z, self.config ))
            self.z_amp.append(gc.get_const_wf(z, self.config ))

    def _lin_freq_array( self ):

        freq_r1_qua = self.freq_range[0] * u.MHz
        freq_r2_qua = self.freq_range[1] * u.MHz
        freq_resolution_qua = self.freq_resolution * u.MHz
        freqs_qua = np.arange(freq_r1_qua,freq_r2_qua,freq_resolution_qua )
        
        return freqs_qua

def plot_flux_dep_qubit( data, flux, dfs, ax=None ):
    """
    data shape ( 2, N, M )
    2 is I,Q
    N is freq
    M is flux
    """
    idata = data[0]
    qdata = data[1]
    zdata = idata +1j*qdata
    s21 = zdata

    if type(ax)==None:
        fig, ax = plt.subplots()
        ax.set_title('pcolormesh')
        fig.show()
    ax[0].pcolormesh( dfs, flux, idata, cmap='RdBu')# , vmin=z_min, vmax=z_max)
    ax[1].pcolormesh( dfs, flux, qdata, cmap='RdBu')# , vmin=z_min, vmax=z_max)

def plot_ana_flux_dep_qubit( data, flux, dfs, freq_LO, freq_IF, abs_z, ax=None, iq_rotate=0 ):
    """
    data shape ( 2, N, M )
    2 is I,Q
    N is freq
    M is flux
    """
    idata = data[0]
    qdata = data[1]
    zdata = (idata +1j*qdata)*np.exp(1j*(iq_rotate/180)*np.pi)
    s21 = zdata

    abs_freq = freq_LO+freq_IF+dfs
    if type(ax)==None:
        fig, ax = plt.subplots()
        ax.set_title('pcolormesh')
        fig.show()
    pcm = ax[0].pcolormesh( abs_freq, abs_z+flux, np.abs(zdata), cmap='RdBu')# , vmin=z_min, vmax=z_max)
    ax[0].axvline(x=freq_LO+freq_IF, color='b', linestyle='--', label='ref IF')
    ax[0].axvline(x=freq_LO, color='r', linestyle='--', label='LO')
    ax[0].axhline(y=abs_z, color='black', linestyle='--', label='idle z')
    plt.colorbar(pcm, label='Value')
    # Add a color bar
    ax[0].legend()
    pcm = ax[1].pcolormesh( abs_freq, abs_z+flux, np.imag(zdata), cmap='RdBu')# , vmin=z_min, vmax=z_max)
    ax[1].axvline(x=freq_LO+freq_IF, color='b', linestyle='--', label='ref IF')
    ax[1].axvline(x=freq_LO, color='r', linestyle='--', label='LO')
    ax[1].axhline(y=abs_z, color='black', linestyle='--', label='idle z')
    plt.colorbar(pcm, label='Value')

    ax[1].legend()



def plot_ana_flux_dep_qubit_1D( data, flux, dfs, freq_LO, freq_IF, abs_z, ax=None, iq_rotate=0 ):   # 20240530 test by Sean
    """
    data shape ( 2, N, M )
    2 is I,Q
    N is flux
    M is freq
    """
    idata = data[0]
    qdata = data[1]
    zdata = (idata +1j*qdata)*np.exp(1j*(iq_rotate/180)*np.pi)  # data shape ( N, M )
    s21 = zdata

    # print(np.shape(data))
    # print(np.shape(flux))
    # print(np.shape(dfs))
    # print(np.shape(zdata))

    mid_flux_index = (len(flux))//2
    mid_flux = abs_z + flux[mid_flux_index]
    mid_zdata = zdata[mid_flux_index]    # data shape ( N )

    abs_freq = freq_LO+freq_IF+dfs

    if type(ax)==None:
        fig, ax = plt.subplots()
        ax.set_title('pcolormesh')
        fig.show()

    
    ax[0].plot( abs_freq, np.real(mid_zdata), color='b', label=f"flux = {mid_flux:.3f}V" )
    ax[1].plot( abs_freq, np.imag(mid_zdata), color='b', label=f"flux = {mid_flux:.3f}V" )

    ax[1].set_xlabel('XY frequency [MHz]')
    ax[0].set_ylabel('Amplitude [V]')
    ax[1].set_ylabel('Amplitude [V]')

    ax[0].legend()
    ax[1].legend()
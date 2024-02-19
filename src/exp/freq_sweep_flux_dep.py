

from qm.qua import *
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm import SimulationConfig
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.loops import from_array
from exp.RO_macros import multiRO_declare, multiRO_measurement, multiRO_pre_save
import matplotlib.pyplot as plt
import warnings
from qualang_tools.units import unit
u = unit(coerce_to_integer=True)

warnings.filterwarnings("ignore")
import xarray as xr

def freq_sweep_flux_dep( ro_element:list, z_element:list, config:dict, qm_machine:QuantumMachinesManager, n_avg:int=100, flux_settle_time:int=1000, freq_span:float=3, flux_span:float=0.3, flux_resolution:float=0.015, freq_resolution:float=0.05, initializer:tuple=None )->xr.Dataset:
    """
    flux_settle_time unit in ns\n    
    return is dataset with coords\n
    ["mixer","flux","frequency"]\n

    """
    freq_span_qua = freq_span * u.MHz
    freq_resolution_qua = freq_resolution * u.MHz

    freqs_qua = np.arange(-freq_span_qua/2,freq_span_qua/2,freq_resolution_qua)
    fluxes = np.arange(-flux_span,flux_span+flux_resolution,flux_resolution)

    freqs_mhz = freqs_qua/1e6 #  Unit in MHz

    freqs_len = freqs_qua.shape[0]
    flux_len = fluxes.shape[0]

    with program() as multi_res_spec_vs_flux:
        # QUA macro to declare the measurement variables and their corresponding streams for a given number of resonators
        iqdata_stream = multiRO_declare( ro_element )

        n = declare(int)
        n_st = declare_stream()
        df = declare(int)  # QUA variable for sweeping the readout frequency detuning around the resonance
        dc = declare(fixed)  # QUA variable for sweeping the fluxes bias

        with for_(n, 0, n < n_avg, n + 1):
            with for_(*from_array(df, freqs_qua)):
                for ro in ro_element:
                    resonator_IF = config['elements'][ro]["intermediate_frequency"]
                    update_frequency(ro, df + resonator_IF)

                with for_(*from_array(dc, fluxes)):
                    # initializaion
                    if initializer is None:
                        wait(1*u.us,ro_element)
                    else:
                        try:
                            initializer[0](*initializer[1])
                        except:
                            wait(1*u.us,ro_element)

                    # Operations
                    for z in z_element:
                        set_dc_offset(z, "single", dc)
                    wait(flux_settle_time * u.ns)  

                    # Readout
                    multiRO_measurement( iqdata_stream, ro_element, weights='rotated_')
                    
            save(n, n_st)

        with stream_processing():
            n_st.save("n")
            multiRO_pre_save( iqdata_stream, ro_element, (freqs_len, flux_len))
            
    #######################

    qm = qm_machine.open_qm(config)
    job = qm.execute(multi_res_spec_vs_flux)
    ro_ch_name = []
    for r_name in ro_element:
        ro_ch_name.append(f"{r_name}_I")
        ro_ch_name.append(f"{r_name}_Q")

    data_list = ro_ch_name + ["n"]   
    results = fetching_tool(job, data_list=data_list, mode="live")
    output_data = {}
    while results.is_processing():
        fetch_data = results.fetch_all()
        for r_idx, r_name in enumerate(ro_element):
            output_data[r_name] = np.array([fetch_data[r_idx*2], fetch_data[r_idx*2+1]])
        iteration = fetch_data[-1]
        # Progress bar
        progress_counter(iteration, n_avg, start_time=results.get_start_time()) 
    # Close the quantum machines at the end in order to put all fluxes biases to 0 so that the fridge doesn't heat-up
    qm.close()
    
    # Creating an xarray dataset
    fetch_data = results.fetch_all()
    for r_idx, r_name in enumerate(ro_element):
        output_data[r_name] = ( ["mixer","frequency","flux"],
                               np.array([fetch_data[r_idx*2], fetch_data[r_idx*2+1]]) )
    dataset = xr.Dataset(
        output_data,
        coords={ "mixer":np.array(["I","Q"]), "frequency": freqs_mhz, "flux": fluxes }
    )
    return dataset


def plot_flux_dep_resonator( data, freqs, fluxes, ax=None ):
    """
    data shape ( 2, N, M )
    2 is I,Q
    N is fluxes
    M is freq
    """
    idata = data[0]
    qdata = data[1]
    zdata = idata +1j*qdata

    if ax==None:
        fig, ax = plt.subplots()
        ax.set_title('pcolormesh')
        fig.show()
    ax.pcolormesh(fluxes, freqs, np.abs(zdata), cmap='RdBu')# , vmin=z_min, vmax=z_max)
    
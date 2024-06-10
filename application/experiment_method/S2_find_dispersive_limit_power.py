import warnings
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt


# 20231216 Test complete :Ratis
# 20240206 Test complete :Jacky

# Dynamic config
from OnMachine.SetConfig.config_path import spec_loca, config_loca
from config_component.configuration import import_config
from config_component.channel_info import import_spec
from ab.QM_config_dynamic import initializer

spec = import_spec( spec_loca )
config = import_config( config_loca ).get_config()
qmm, _ = spec.buildup_qmm()
init_macro = initializer(1000,mode='wait')

# Measurement
n_avg = 100  # The number of averages
ro_elements = ["q0_ro"]
from exp.rofreq_sweep_power_dep import *
freq_range = (-15,15)
freq_resolution = 0.1
amp_max_ratio = 1.5
amp_resolution = 0.01
amp_scale = "lin"   # "lin", "log"

dataset = frequency_sweep_power_dep( ro_elements, config, qmm, n_avg=n_avg, freq_range=freq_range, freq_resolution=freq_resolution, amp_resolution=amp_resolution, amp_max_ratio=amp_max_ratio, amp_scale=amp_scale, initializer=init_macro)  


# Plot
dfs = dataset.coords["frequency"].values
amps = dataset.coords["amp_ratio"].values

for ro_name, data in dataset.data_vars.items():
    fig, ax = plt.subplots()
    plot_power_dep_resonator(dfs, amps, data.values, ax, amp_scale)
    ax.set_title(ro_name)
    ax.set_xlabel("additional IF freq (MHz)")
    ax.set_ylabel("amp scale")



save_data = True
if save_data:
    from exp.save_data import save_nc, save_fig
    save_dir = r"C:\Users\quant\SynologyDrive\09 Data\Fridge Data\Qubit\20240521_DR4_5Q4C_0430#7\00 raw data"
    save_nc(save_dir, f"power_dep_resonator_{ro_elements[0]}", dataset)
    save_fig(save_dir, f"power_dep_resonator_{ro_elements[0]}")

plt.show()
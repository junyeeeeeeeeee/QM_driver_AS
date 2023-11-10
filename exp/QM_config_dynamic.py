from qualang_tools.units import unit
from numpy import array


#######################
# AUXILIARY FUNCTIONS #
#######################
u = unit(coerce_to_integer=True)


############################################
#            control_spec class            #
############################################

class Circuit_info:
    """This object contains the information about RO and XY control on the chip"""
    def __init__(self,q_num,**kwargs):
        self.q_num = q_num
        self.init_XyInfo()
        self.QsRoInfo = {}
    
    ### Below about RO information ###
    

    ### Below about XY information ###    
    def init_XyInfo(self):
        '''Info for a pi-pulse should envolve:\n
        1)pi_amp, 2)pi_len, 3)qubit_LO, 4)qubit_IF(MHz), 5)drag_coef, 6)anharmonicity(MHz), 7)AC_stark_detuning
        '''
        self.QsXyInfo = {}
        self.QsXyInfo["register"] = []
        for idx in range(1,self.q_num+1):
            for info in ["pi_amp_q","pi_len_q","qubit_LO_q","qubit_IF_q","drag_coef_q","anharmonicity_q","AC_stark_detuning_q","waveform_func_q"]:
                self.QsXyInfo[info+str(idx)] = 0 
            self.QsXyInfo["register"].append("q"+str(idx))
        # CW pulse info
        self.QsXyInfo["const_len"] = 1000
        self.QsXyInfo["const_amp"] = 300 * u.mV
        # Saturation pulse info
        self.QsXyInfo["saturation_len"] = 5 * u.us
        self.QsXyInfo["saturation_amp"] = 0.5
        

    def update_aXyInfo_for(self,target_q,**kwargs):
        '''target_q : "q5"\n
        kwargs :\n
        amp(pi_amp)=0.2\nlen(pi_len)=20\nLO(qubit_LO)=4.3\nIF(qubit_IF)=80\ndraga(drag_coef)=0.5\ndelta or anh or d(anharmonicity)=-200\n
        AC(AC_stark_detuning)=8,func='gauss' or 'drag'
        '''
        for name in list(kwargs.keys()):
            if name.lower() == 'amp':
                self.QsXyInfo["pi_amp_"+target_q] = kwargs[name] 
            elif name.lower() == 'len':
                self.QsXyInfo["pi_len_"+target_q] = kwargs[name]
            elif name.lower() == 'lo':
                self.QsXyInfo["qubit_LO_"+target_q] = kwargs[name]
            elif name.lower() == 'if':
                self.QsXyInfo["qubit_IF_"+target_q] = kwargs[name]
            elif name.lower() in ['draga','drag_coef'] :
                self.QsXyInfo["drag_coef_"+target_q] = kwargs[name]
            elif name.lower() in ["delta","d","anh","anharmonicity"]:
                self.QsXyInfo["anharmonicity_"+target_q] = kwargs[name]
            elif name.lower() in ['ac',"AC_stark_detuning"]:
                self.QsXyInfo["AC_stark_detuning_"+target_q] = kwargs[name]
            elif name.lower() in ['waveform',"func",'wf']:
                self.QsXyInfo["waveform_func_"+target_q] = kwargs[name]
            else:
                raise KeyError("I don't know what you are talking about!")
    
    def update_XyInfoS_for(self,target_q:str,InfoS:list | dict):
        ''' target_q : "q5"\n
            InfoS : \n
                if type is list : [pi_amp, pi_len, qubit_LO, qubit_IF(MHz), drag_coef, anharmonicity(MHz), AC_stark_detuning]\n
                if type is dict : {"amp", "len", "LO", "IF", "drag_coef", "anharmonicity", "AC_stark_detuning"}
        '''
        if isinstance(InfoS,list):
            vals = ["pi_amp_", "pi_len_", "qubit_LO_", "qubit_IF_", "drag_coef_", "anharmonicity_", "AC_stark_detuning_"]
            for idx in range(len(InfoS)):
                self.QsXyInfo[vals[idx]+target_q] = InfoS[idx]
        elif isinstance(InfoS,dict):
            for keyname in InfoS:
                self.update_aXyInfo_for(target_q,name=InfoS[keyname])
        else:
            raise TypeError("InfoS should be a list or dict! For a single value use `update_aPiInfo_for()`")

    def export_xyinfo( self, path ):
        import pickle
        # define dictionary
        # create a binary pickle file 
        f = open(path,"wb")
        # write the python object (dict) to pickle file
        pickle.dump(self.QsXyInfo,f)
        # close file
        f.close()

    def import_xyinfo( self, path ):
        import pickle
        # Read dictionary pkl file
        with open(path, 'rb') as fp:
            self.QsXyInfo = pickle.load(fp)
        print("XY information loaded successfully!")

class Waveform:
    def __init__(self,xyInfo:dict):
        self.QsXyInfo = xyInfo
    def build_waveform(self,target_q:str,func:str,axis:str,**kwargs)->dict:
        ''' Create the pulse waveform for XY control for target qubit\n
            target_q : "q2"\n
            func : "drag" or "gauss"\n
            axis : "x" or "y" or "x/2" or "y/2" or "-x/2" or "-y/2"
        '''
        from qualang_tools.config.waveform_tools import drag_gaussian_pulse_waveforms
        # check the info is contained the data about target Q
        if target_q not in self.QsXyInfo["register"]:
            raise KeyError(f"There are not any info in 'QsXyInfo' about target {target_q}")
        # search the waveform function
        if func.lower() in ['drag','dragg','gdrag']:
            def wf_func(amp, width, sigma, *args):
                drag_gaussian_pulse_waveforms(amp, width, sigma, args[0], args[1], args[2])
        elif func.lower() in ['gauss','g','gaussian']:
            def wf_func(amp, width, sigma, *args):
                drag_gaussian_pulse_waveforms(amp, width, sigma, 0, args[1], args[2])
        else:
            raise ValueError("Only surpport Gaussian or DRAG-gaussian waveform!")
        
        # Create the waveform array for I and Q
        angle = 1/len(axis.split("/")) # if "X/2" angle = 1/2, other angle = 1 (π)
        rotation_to = -1 if axis.split("/")[0][0]=="-" else 1
        scale = rotation_to*angle
        # check pulse sigma
        if kwargs != [] and list(kwargs.keys())[0].lower() in ["sigma","s","sfactor","s-factor"]:
            S_factor = kwargs[list(kwargs.keys())[0]]
        else:
            S_factor = 4

        if axis[0].lower() == 'x':
            wf, der_wf = array(
                wf_func(self.QsXyInfo["pi_amp_"+target_q]*scale, self.QsXyInfo["pi_len_"+target_q], self.QsXyInfo["pi_len_"+target_q]/S_factor, self.QsXyInfo["drag_coef_"+target_q], self.QsXyInfo["anharmonicity_"+target_q], self.QsXyInfo["AC_stark_detuning_"+target_q])
            )
            I_wf = wf
            Q_wf = der_wf
        elif axis[0].lower() == 'y':
            wf, der_wf = array(
                wf_func(self.QsXyInfo["pi_amp_"+target_q]*scale, self.QsXyInfo["pi_len_"+target_q], self.QsXyInfo["pi_len_"+target_q]/S_factor, self.QsXyInfo["drag_coef_"+target_q], self.QsXyInfo["anharmonicity_"+target_q], self.QsXyInfo["AC_stark_detuning_"+target_q])
            )
            I_wf = (-1)*der_wf
            Q_wf = wf
        else:
            raise ValueError("Check the given axis, It should start with 'x' or 'y'!")
    
        return {"I":I_wf, "Q":Q_wf}
        






class QM_config():
    def __init__( self ):

        self.__config = {
            "version": 1,
            "controllers": {},
            "elements": {},
            "pulses": {},
            "waveforms": {
                "zero_wf": {"type": "constant", "sample": 0.0},
            },
            "digital_waveforms": {
                "ON": {"samples": [(1, 0)]},
            },
            "integration_weights": {},
            "mixers": {},
        }
    def set_wiring( self, controller_name ):
        update_setting = {
            controller_name:{
                "analog_outputs": {
                    1: {"offset": 0.0},  # I readout line
                    2: {"offset": 0.0},  # Q readout line
                    3: {"offset": 0.0},  # I qubit1 XY
                    4: {"offset": 0.0},  # Q qubit1 XY
                    5: {"offset": 0.0},  # I qubit2 XY
                    6: {"offset": 0.0},  # Q qubit2 XY
                    7: {"offset": 0.0},  # I qubit3 XY
                    8: {"offset": 0.0},  # Q qubit3 XY
                    9: {"offset": 0.0},  # I qubit4 XY
                    10: {"offset": 0.0},  # Q qubit4 XY
                },
                "digital_outputs": {
                    1: {},
                    3: {},
                    5: {},
                    7: {},
                    9: {},
                },
                "analog_inputs": {
                    1: {"offset": 0, "gain_db": 0},  # I from down-conversion
                    2: {"offset": 0, "gain_db": 0},  # Q from down-conversion
                },
            }
        }
        self.__config["controllers"].update(update_setting)

    def get_config( self ):
        return self.__config
    
    def update_multiplex_readout_channel( self, common_wiring:dict, individual_setting:list):
        """
        common wiring ex.
        {
            "I":("con1",1)
            "Q":("con1",2)
            "freq_LO": 6, # GHz
            "mixer": "octave_octave1_1",
            "time_of_flight": 250, # ns
            "integration_time": 2000 # ns
        }
        individual setting : list
        {
            "name":"r1",
            "freq_RO": 6.01, # GHz
            "amp": 0.01 # V
        }
        register readout pulse by name rp f"readout_pulse_{name}"
        """

        freq_LO = int(common_wiring["freq_LO"] * u.GHz) 
        electrical_delay = int(common_wiring["time_of_flight"])
        mixer_name = common_wiring["mixer"]

        resonator_element_template_dict = {
            "mixInputs": {
                "I": common_wiring["I"],
                "Q": common_wiring["Q"],
                "lo_frequency": freq_LO,
                "mixer": mixer_name,
            },
            "intermediate_frequency":  None, 
            "operations": {
            },
            "outputs": {
                "out1": ("con1", 1),
                "out2": ("con1", 2),
            },
            "time_of_flight": electrical_delay,
            "smearing": 0,
        }
        integration_time = common_wiring["integration_time"]
        readout_pulse_template_dict = {
            "operation": "measurement",
            "length": integration_time,
            "waveforms": {},
            "integration_weights": {
                "cos": "cosine_weights",
                "sin": "sine_weights",
                "minus_sin": "minus_sine_weights",

            },
            "digital_marker": "ON",
        }
        
        self.__config["mixers"] = {
            mixer_name:[],
        }

        mixers_template_dict = {
            "intermediate_frequency": 100,
            "lo_frequency": freq_LO,
            "correction": (1, 0, 0, 1),  
        }

        self.__config["integration_weights"].update({
            "cosine_weights": {
                "cosine": [(1.0, integration_time)],
                "sine": [(0.0, integration_time)],
            },
            "sine_weights": {
                "cosine": [(0.0, integration_time)],
                "sine": [(1.0, integration_time)],
            },
            "minus_sine_weights": {
                "cosine": [(0.0, integration_time)],
                "sine": [(-1.0, integration_time)],
            },
        })

        for setting in individual_setting:
            pulse_name = f"readout_pulse_{setting['name']}"
            waveform_name = f"readout_wf_{setting['name']}"
            freq_RO = int(setting["freq_RO"] * u.GHz) 
            freq_IF = freq_RO-freq_LO

            # Complete element config setting
            complete_element = resonator_element_template_dict
            complete_element["intermediate_frequency"] = freq_IF
            resonator_name = setting["name"]

            complete_element["operations"]["readout"] = pulse_name
            self.update_element( resonator_name, complete_element )

            # Complete pulse config setting
            complete_pulse = readout_pulse_template_dict
            complete_pulse["waveforms"] = {
                "I": waveform_name,
                "Q": "zero_wf",
            }
            self.__config["pulses"][pulse_name] = complete_pulse

            # Complete waveform config setting
            self.__config["waveforms"][waveform_name] = {
                "type": "constant", 
                "sample": setting["amp"]
            }
            # Complete mixers config setting
            complete_mixer = mixers_template_dict
            complete_mixer["intermediate_frequency"] = freq_IF
            self.__config["mixers"][mixer_name].append(complete_mixer)


    def update_readout_channel( self, name, wiring:dict, freq_LO, freq_IF ):
        """
        LO freq : GHz
        IF freq : MHz
        """

        resonator_name = name
        setting = {
            "intermediate_frequency":  int(freq_IF * u.MHz), 
        }
        self.update_element( resonator_name, setting )
        

    def update_xy_element(self, wiringANDmachine:list, XYinfo:dict):
        """
        target_q : "q2"..\n
        wiringANDmachine ex:\n
        [{\n
            "name":"q2"
            "I":("con1", 3),\n
            "Q":("con1", 4),\n
            "mixer": "octave_octave1_2"\n
        },]\n

        xyinfo is from Circuit_info().QsXyInfo
        """
        
        for wiringInfo in wiringANDmachine:
            # create xy dict in element
            xy_element_template_dict = {
                "mixInputs": {
                    "I": wiringInfo["I"],
                    "Q": wiringInfo["Q"],
                    "lo_frequency": XYinfo["qubit_LO_"+wiringInfo['name']]*u.GHz,
                    "mixer": wiringInfo["mixer"],
                },
                "intermediate_frequency": XYinfo["qubit_IF_"+wiringInfo['name']]*u.MHz,  
                "operations": {
                    "cw": "const_pulse",
                    "saturation": "saturation_pulse",
                    "x180": f"x180_pulse_{wiringInfo['name']}",
                    "x90": f"x90_pulse_{wiringInfo['name']}",
                    "-x90": f"-x90_pulse_{wiringInfo['name']}",
                    "y90": f"y90_pulse_{wiringInfo['name']}",
                    "y180": f"y180_pulse_{wiringInfo['name']}",
                    "-y90": f"-y90_pulse_{wiringInfo['name']}",
                }
            }
            self.update_element(name=f"{wiringInfo['name']}_xy", setting=xy_element_template_dict)
            # Create the mixer info for control
            '''To do'''
            mixer_template_list = [   
                {
                    "intermediate_frequency": qubit_IF_q4, 
                    "lo_frequency": qubit_LO_q2,
                    "correction": (1, 0, 0, 1),
                }
            ]
            # create corresponding waveform name in pulses dict, create waveform list in waveforms dict
            wave_maker = Waveform(XYinfo)
            for waveform in  self.__config["elements"][f"{wiringInfo['name']}_xy"]["operations"]:
                if waveform not in ["cw", "saturation"]:
                    rotate_to = "minus_" if waveform[0] == "-" else ""
                    new_wf_namae = rotate_to + waveform.split("-")[-1]
                    self.__config["pulses"][f"{waveform}_pulse_{wiringInfo['name']}"] = {
                        "operation": "control",
                        "length": XYinfo[f"pi_len_{wiringInfo['name']}"],
                        "waveforms": {
                            "I": f"{new_wf_namae}_I_wf_{wiringInfo['name']}",
                            "Q": f"{new_wf_namae}_Q_wf_{wiringInfo['name']}",
                        }
                    }

                    # Create waveform list
                    for waveform_basis in self.__config["pulses"][f"{waveform}_pulse_{wiringInfo['name']}"]["waveforms"]:
                        ''' waveform_basis is "I" or "Q" '''
                        waveform_name = self.__config["pulses"][f"{waveform}_pulse_{wiringInfo['name']}"]["waveforms"][waveform_basis]
                        posit_minus= waveform_name.split("_")[0] if waveform_name.split("_")[0]=='minus_' else ""
                        axis = waveform_name.split("_")[1] if waveform_name.split("_")[0]=='minus_' else waveform_name.split("_")[0]
                        scale = "/2" if axis[1:] == "90" else ""

                        wf = wave_maker.build_waveform(target_q=wiringInfo['name'],func="drag",axis=posit_minus+axis+scale)
                        
                        self.__config["waveforms"][waveform_name] = {"type": "arbitrary", "samples":wf[waveform_basis].tolist()}

        # create constant and saturation waveform    
        for waveform in ["cw", "saturation"]:
            wfna = "const" if waveform == "cw" else  waveform
            self.__config["pulses"][f"{wfna}_pulse"] = {
                "operation": "control",
                "length": XYinfo[f"{wfna}_len"],
                "waveforms": {
                    "I": f"{wfna}_wf",
                    "Q": "zero_wf",
                }
            } 
            self.__config["waveforms"][f"{wfna}_wf"] = {"type": "constant", "samples":XYinfo[f"{wfna}_amp"]}       
        self.__config["waveforms"]["zero_wf"] = {"type": "constant", "samples":0.0}

        


    def update_element( self, name:str, setting:dict ):
        update_setting = {name:setting}
        self.__config["elements"].update(update_setting)

    def export_config( self, path ):
        import pickle

        # define dictionary
        # create a binary pickle file 
        f = open(path,"wb")
        # write the python object (dict) to pickle file
        pickle.dump(self.__config,f)
        # close file
        f.close()

    def import_config( self, path ):
        import pickle
        # Read dictionary pkl file
        with open(path, 'rb') as fp:
            self.__config = pickle.load(fp)

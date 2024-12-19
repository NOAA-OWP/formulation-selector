"""Processing script for CAMELS EA-LSTM benchmarking study
Kratzert et al 2019 https://doi.org/10.5194/hess-23-5089-2019
https://hess.copernicus.org/articles/23/5089/2019/#Ch1.S2.SS6.SSS1

531 CAMELS basins

Metrics:
NSE: Nash Sutcliffe Efficiency
alpha_nse: alpha NSE decomposition, Gupta et al 2009: the variability ratio sigma_m/sigma_o
beta_nse: beta NSE decomposition, Gupta et al 2009: bias; ratio of means mu_m/mu_o
FHV: top 2% peak flow bias, Yilmaz et al 2008
FLV: 30% low flow bias, Yilmaz et al 2008
FMS: bias of FDC midsegment slope, Yilmaz et al 2008

The better-performing LSTM Models considered by Kratzert et al 2019:
EA-LSTM MSE seed111
EA-LSTM ensemble n=8
EA-LSTM NSE seed 111
EA-LSTM NSE ensemble n=8 (third-best performing)
LSTM MSE seed111
LSTM MSE ensemble n=8 (very close to best performing)
LSTM NSE seed 111
LSTM NSE ensemble n=8 (best performing) 

Note LSTM ensembles mean 8 different random seeds by taking the mean prediction
at each step of all n different models under e/ configuration.

Benchmark process based models calibrated CONUS-wide:
VIC CONUS-wide calibrated (worst performance)
mHm CONUS-wide calibrated (poor performance)

Benchmark process based models basin-wise calibrated:
HBV calibrated ensemble n=100 (good performance)
SAC-SMA
VIC (worst performance)
FUSE 900
FUSE 902
FUSE 904
mHm

Should Ignore VIC ensemble n=1000 uncalibrated, very bad performance

Using if modl_name == 'ensemble' within the lstm_model_types loop
means that only ensembles are considered (not individual seeds)

Usage:
python proc_ealstm_agu24.py "/path/to/ealstm_proc_config.yaml"

"""


import pickle
import argparse
import pandas as pd
from pathlib import Path
import yaml
import fs_proc.proc_eval_metrics as pem

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process the YAML config file.')
    parser.add_argument('path_config', type=str, help='Path to the YAML configuration file')
    args = parser.parse_args()
    # The path to the configuration
    path_config = args.path_config # "~/git/formulation-selector/scripts/eval_ingest/ealstm/ealstm_proc_config.yaml"

    if not Path(path_config).exists():
        raise ValueError("The provided path to the configuration file does not exist: {path_config}")

    # Load the YAML configuration file
    with open(path_config, 'r') as file:
        config = yaml.safe_load(file)

    # ----- File IO
    print("Converting schema to DataFrame")
    # Read in the config file & convert to pd.DataFrame
    col_schema_df = pem.read_schm_ls_of_dict(schema_path = path_config)

    # Extract path and format the home_dir in case it was defined in file path
    # path_camels = col_schema_df['path_camels'].loc[0].format(home_dir = str(Path.home()))
    path_data = col_schema_df['path_data'].loc[0].format(home_dir = str(Path.home())) #"~/git/ealstm_regional_modeling/notebooks/all_metrics.p"
    dir_save = col_schema_df['dir_save'].loc[0].format(home_dir = str(Path.home()))

    # ------------- BEGIN CUSTOMIZED DATASET MUNGING -------------------

    # ---- Read in Kratzert et al 2019 metrics results acquired from github repo
    print("Custom code: Reading/formatting non-standardized input datasets")
    with open(path_data, 'rb') as file:
        dat_metr = pickle.load(file)

    # Transform from dict of metrics containing subdicts of model results to
    #   dict of model results containing dataframe of each metric
    
    # list out each model type:
    metrics = list(dat_metr.keys())
    model_types = list(dat_metr[metrics[0]].keys())

    benchmark_names = list(dat_metr[metrics[0]]['benchmarks'].keys())

    # Keys of model names to select:
    model_names_sel = ['ensemble'] + benchmark_names

    # Each model type has different seeds or formulations
    dat_metr[metrics[0]][model_types[0]].keys()



    # Extract LSTM ensemble model metrics
    lstm_model_types = [x for x in list(dat_metr[metrics[0]].keys()) if x!= 'benchmarks']
    dict_modl_names_lstm = dict()
    for sel_modl_name in lstm_model_types:
        dict_modl_names_lstm[sel_modl_name] = pd.DataFrame()
        for metric, vals in dat_metr.items():
            dict_models = dict()
            for model, vv in vals.items():
                if model == sel_modl_name:
                    for modl_name, metr_vals in vv.items():
                        if modl_name == 'ensemble':
                            full_modl_name = model +'_' + modl_name
                            df_metr = pd.DataFrame(metr_vals.items(), columns = ['gageID',metric])
                            if dict_modl_names_lstm[sel_modl_name].shape[0] == 0:
                                dict_modl_names_lstm[sel_modl_name] = pd.concat([dict_modl_names_lstm[sel_modl_name], df_metr])
                            else:
                                dict_modl_names_lstm[sel_modl_name] = pd.merge(dict_modl_names_lstm[sel_modl_name], df_metr, on='gageID')

    ls_gage_ids = df_metr['gageID'].tolist()

    # Extract the process-based model metrics
    # Create dict of dfs for each benchmark model, with df containing eval metrics
    dict_modl_names = dict()
    for sel_modl_name in benchmark_names:
        dict_modl_names[sel_modl_name] = pd.DataFrame()
        for metric, vals in dat_metr.items():
            dict_models = dict()
            print(metric)
            for model, vv in vals.items():
                print(f'....{model}')
                for modl_name, metr_vals in vv.items():
                    if modl_name == sel_modl_name:
                        full_modl_name = model +'_' + modl_name
                        df_metr = pd.DataFrame(metr_vals.items(), columns = ['gageID',metric])
                        # SUBSET TO JUST THOSE SAME LOCATIONS EVALUATED WITH LSTM
                        df_metr = df_metr[df_metr['gageID'].isin(ls_gage_ids)] 
                        if dict_modl_names[sel_modl_name].shape[0] == 0:
                            dict_modl_names[sel_modl_name] = pd.concat([dict_modl_names[sel_modl_name], df_metr])
                        else:
                            dict_modl_names[sel_modl_name] = pd.merge(dict_modl_names[sel_modl_name], df_metr, on='gageID')


    
    dict_modl_names.update(dict_modl_names_lstm)
    ds_name_og = col_schema_df['dataset_name']
    # Operate over each dataset
    for ds, df in dict_modl_names.items():
        print(f'Processing {ds}')

        # Create NNSE
        df['NNSE'] = 1/(2-df['NSE'])

        # Format the dataset name
        col_schema_df['dataset_name'] = [x.format(ds=ds) for x in ds_name_og]
        # Generate the standardized netcdf file:
        ds = pem.proc_col_schema(df, col_schema_df, dir_save)
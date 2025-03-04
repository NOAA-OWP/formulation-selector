'''
@title: Find US basins compatible with NHDplus inside Julie Mai's xSSA datasets
@author: Guy Litt <guy.litt@noaa.gov>
@description: Reads in the xSSA dataset, 
    subset xSSA data to just NHDplus basins, 
    and converts to a standard format expected by the formulation-selector tooling.
@usage: python proc_xssa_metrics.py "/full/path/to/xssaus_config.yaml"

Changelog/contributions
    2024-12-17 Originally created, GL
'''
import argparse
import pandas as pd
from pathlib import Path
import yaml
from fs_proc.proc_eval_metrics import read_schm_ls_of_dict, proc_col_schema
import numpy as np
import re
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process the YAML config file.')
    parser.add_argument('path_config', type=str, help='Path to the YAML configuration file')
    args = parser.parse_args()
    # The path to the configuration
    path_config = args.path_config # '~/git/formulation-selector/scripts/eval_ingest/xssa_us/xssaus_prep_config.yaml' 

    if not Path(path_config).exists():
        raise ValueError("The provided path to the configuration file does not exist: {path_config}")

    # Load the YAML configuration file
    with open(path_config, 'r') as file:
        config = yaml.safe_load(file)

    # ----- File IO
    print("Converting schema to DataFrame")
    # Read in the config file & convert to pd.DataFrame
    col_schema_df = read_schm_ls_of_dict(schema_path = path_config)

    # Extract path and format the home_dir in case it was defined in file path
    
    dir_xssa = col_schema_df['dir_data'].loc[0].format(home_dir = str(Path.home()))
    dir_save = col_schema_df['dir_save'].loc[0].format(home_dir = str(Path.home()))

    # BEGIN CUSTOMIZED DATASET MUNGING

    # list files from xssa analysis:
    dir_xssa = Path('/Users/guylitt/noaa/regionalization/data/julemai-xSSA/scripts/data/xSSA_analysis')
    names_xssa = [x.name for x in dir_xssa.iterdir()]
    def _select_numeric_prefix(strings):
        selected_strings = []
        for s in strings:
            # Split the string at the first underscore
            parts = s.split('_', 1)
            # Check if the prefix is numeric
            if parts[0].isdigit():
                selected_strings.append(s)
        return selected_strings

    # Select strings with purely numeric prefix before the first '_', aka the possible USGS gage ids
    files_usgs = _select_numeric_prefix(names_xssa)

    # Unique USGS gage id locations:
    usgs_gage_ids = np.unique([x.split('_',1)[0] for x in files_usgs])


    new_cols = col_schema_df['metric_cols'][0].split('|')
    # new_cols = ['W_wt_precip_corr', 'V_wt_rainsnow_part', 'U_wt_perc', 'T_wt_pot_melt', 'S_wt_delay_ro',
    #              'R_wt_srfc_ro', 'Q_wt_snow_bal', 'P_wt_baseflow', 'P_wt_baseflow', 'N_wt_quickflow', 'M_wt_infilt']
    # Combine the xSSA results 

    dict_mean_xssa_wt = dict()
    for usgs_gid in usgs_gage_ids:
        files_gid = [x for x in files_usgs if usgs_gid in x]
        file_gid_proc = [x for x in files_gid if 'processes.csv' in x][0]
        file_gid_wt = [x for x in files_gid if 'weights.csv' in x][0]

        # Read xssa results & remove leading spaces
        dat_proc_xssa = pd.read_csv(Path(dir_xssa)/Path(file_gid_proc))
        dat_proc_xssa.columns = [x.lstrip() for x in dat_proc_xssa.columns.tolist()]
        cols_proc = [x for x in  dat_proc_xssa.columns.tolist() if x != 'date']

        dat_wt_xssa = pd.read_csv(Path(dir_xssa)/Path(file_gid_wt))
        
        # Temporally merge
        dat_all_xssa = pd.merge(left=dat_proc_xssa, right = dat_wt_xssa, on='date')

        # TODO remove this placeholder once weighting figured out.
        # Multiply weight to each process sensitivity
        df_xssa_wt = dat_all_xssa.apply(lambda x: x*dat_all_xssa[' weight '] if x.name in cols_proc else x)

        # Rename columns
        # These are the standardized column names defined in formulation-selector/pkg/fs_proc/fs_proc/fs_categories.yaml:

        df_cols_mtch = pd.DataFrame({'new_cols': new_cols})
        df_cols_mtch['key'] = [x.split('_')[0] for x in df_cols_mtch['new_cols']]

        df_orig_cols = pd.DataFrame({'orig_cols': cols_proc})
        df_orig_cols['key'] = [re.search(r'\$(.*?)\$', x).group(1) for x in cols_proc]
        df_cols_map = pd.merge(df_cols_mtch, df_orig_cols, on = 'key')
        rename_dict = dict(zip(df_cols_map['orig_cols'], df_cols_map['new_cols']))
        df_xssa_wt.rename(columns=rename_dict, inplace=True)

        # TODO remove this placeholder once weighting figured out.
        # Temporally aggregate:
        mean_df = df_xssa_wt[df_cols_map['new_cols']].mean().to_frame().transpose()
        mean_df['basin_id'] = usgs_gid
        dict_mean_xssa_wt[usgs_gid] = mean_df

    df_all_locs_mean_wt = pd.concat(dict_mean_xssa_wt)
     # Rename column names:
#         ['Precipitation Correction $W$',
#  'Rain-Snow Partitioning $V$',
#  'Percolation $U$',
#  'Potential Melt $T$',
#  'Convolution (dlyd runoff) $S$',
#  'Convolution (srfc runoff) $R$',
#  'Snow Balance $Q$',
#  'Baseflow $P$',
#  'Evaporation $O$',
#  'Quickflow $N$',
#  'Infiltration $M$']



    # ---- Read in Julie Mai's 2022 Nat Comm xSSA results
    print("Custom code: Reading/formatting non-standardized input datasets")
    df_all_data = pd.read_csv(path_data,sep = '; ',dtype={col_schema_df['gage_id'].loc[0] :str})

    # Ensure appropriate str formats & remove extraneous spaces that exist in this particular dataset
    df_all_data.columns = df_all_data.columns.str.replace(' ','')
    df_all_data[col_schema_df['gage_id'].loc[0]] = df_all_data[col_schema_df['gage_id'].loc[0]].str.replace(' ','')

    # Read in CAMELS data (simply to retrieve the gauge_ids)
    df_camlh = pd.read_csv(path_camels,sep=';',dtype={'gauge_id' :str})
    
    # Subset the xssa dataset to CAMELS basins
    print(f"Subsetting the dataset {col_schema_df['dataset_name']} to CAMELS basins")
    df_camls_merge = df_camlh.merge(df_all_data, left_on= 'gauge_id', right_on = col_schema_df['gage_id'].loc[0], how='inner')
    df = df_camls_merge.drop(columns = df_camlh.columns)
    # END CUSTOMIZED DATASET MUNGING

    # ------ Extract metric data and write to file
    
    ds = proc_col_schema(df_all_locs_mean_wt, col_schema_df, dir_save)
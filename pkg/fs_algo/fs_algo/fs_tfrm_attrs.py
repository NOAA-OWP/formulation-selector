"""Attribute aggregation & transformation script
Using the attribute transformation configuration file,
aggregate and transform existing attributes to create new attributes

Details:
If additional attribute transformations desired, the natural step in the workflow
is after the attributes have been acquired, and before running fs_proc_algo.py 

If attributes needed for aggregation do not exist for a given
comid, the fs_algo.tfrm_attrs. writes the missing attributes to file

Refer to the example config file, e.g. 
`Path(f'~/git/formulation-selector/scripts/eval_ingest/xssa/xssa_attrs_tform.yaml')`

Usage:
python fs_tfrm_attrs.py "/path/to/tfrm_config.yaml"
"""

import argparse
import yaml
import pandas as pd
from pathlib import Path
import fs_algo.fs_algo_train_eval as fsate
import fs_algo.tfrm_attr as fta
import itertools
from collections import ChainMap
import subprocess
import numpy as np
import os
import re

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'process the algorithm config file')
    parser.add_argument('path_tfrm_cfig', type=str, help='Path to the YAML configuration file specific for algorithm training')
    args = parser.parse_args()

    path_tfrm_cfig = Path(args.path_tfrm_cfig)#path_tfrm_cfig = Path(f'~/git/formulation-selector/scripts/eval_ingest/xssa/xssa_attrs_tform.yaml') 

    with open(path_tfrm_cfig, 'r') as file:
        tfrm_cfg = yaml.safe_load(file)

    # Read from transformation config file:
    catgs_attrs_sel = [x for x in list(itertools.chain(*tfrm_cfg)) if x is not None]
    idx_tfrm_attrs = catgs_attrs_sel.index('transform_attrs')

    # dict of file input/output, read-only combined view
    idx_file_io = catgs_attrs_sel.index('file_io')
    fio = dict(ChainMap(*tfrm_cfg[idx_file_io]['file_io'])) 
    overwrite_tfrm = fio.get('overwrite_tfrm',False)

    # Extract desired content from attribute config file
    path_attr_config=fsate.build_cfig_path(path_tfrm_cfig, Path(fio.get('name_attr_config')))
    attr_cfig = fsate.AttrConfigAndVars(path_attr_config) 
    attr_cfig._read_attr_config()

    # Define all directory paths in case used in f-string evaluation
    dir_base = attr_cfig.attrs_cfg_dict.get('dir_base') 
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets')
    home_dir = attr_cfig.attrs_cfg_dict.get('home_dir',Path.home())

    # Define path to store missing comid-attribute pairings:
    path_need_attrs = fta.std_path_miss_tfrm(dir_db_attrs)

    #%% READ COMIDS FROM CUSTOM FILE (IF path_comid present in tfrm config)
    # Extract location of custom file containing comids:
    path_comid = fio.get('path_comid', None)

    ls_comid = list()
    # Read in comid from custom file (e.g. predictions)
    if path_comid:
        path_comid = eval(f"f'{fio.get('path_comid', None)}'")
        path_comid = Path(path_comid)
        colname_comid = fio.get('colname_comid') 
        df_comids = fta.read_df_ext(path_comid) # Simply read in a file
        
        # Now we need to make sure we select the comids!
        all_uniq_comids = df_comids[colname_comid].unique()
        # Run check that no nwissite data are present
        if df_comids[colname_comid].astype(str).str.contains('USGS').any():
            raise ValueError(f"\nUnexpected non-comid retrievals from reading\n{path_comid}\n\n"\
                            f"Hint: Reconsider the colname_comid in {path_tfrm_cfig}")
        ls_comid = ls_comid + list(df_comids[colname_comid].unique())

    #%%  READ COMIDS GENERATED FROM proc.attr.hydfab 
    likely_ds_types = ['training','prediction']
    loc_id_col = 'comid'
    name_attr_config = fio.get('name_attr_config', None)

    ls_comids_attrs = list()
    if  name_attr_config: 
        # Attribute metadata containing a comid column as standard format 
        path_attr_config = fsate.build_cfig_path(path_tfrm_cfig, name_attr_config)
        try:
            ls_comids_attrs = fta._get_comids_std_attrs(path_attr_config)
        except:
            print(f"No basin comids acquired from standardized metadata.")

    # Compile unique comid values
    comids = list(set(ls_comid + ls_comids_attrs))
    # #%% Parse aggregation/transformations in config file
    tfrm_cfg_attrs = tfrm_cfg[idx_tfrm_attrs]

    # # Create the custom functions
    dict_cstm_vars_funcs = fta._retr_cstm_funcs(tfrm_cfg_attrs)

    # Note that this is a flattened length size, based on the total 
    # number of transformation functions & which transformations are needed
    dict_retr_vars = dict_cstm_vars_funcs.get('dict_retr_vars')

    #%% Retrieve comid-attribute data of interest & grab missing data
    # all the variables of interest
    all_retr_vars = list(set([vv for k, v in dict_retr_vars.items() for vv in v]))

    # Read in available comid data of interest (all comids + attributes)
    df_attr_all = fsate.fs_read_attr_comid(dir_db_attrs=dir_db_attrs,
                                              comids_resp=comids,
                                              attrs_sel=all_retr_vars,_s3=None,
                                               storage_options=None,
                                               read_type='all',reindex=True)
    # Create unique combination of comid-attribute pairings:
    df_attr_all['uniq_cmbo'] = df_attr_all['featureID'].astype(str) + '_' + df_attr_all['attribute'].values
    
    # ALL NEEDED UNIQUE COMBOS:
    must_have_uniq_cmbo = [f"{comid}_{var}" for comid in comids for var in all_retr_vars]

    # Determine which comid-attribute pairings missing using unique key
    #uniq_cmbo_absent = [item for item in must_have_uniq_cmbo if item not in df_attr_all['uniq_cmbo'].values]
    uniq_cmbo_absent = list(set(must_have_uniq_cmbo) - set(df_attr_all['uniq_cmbo']))

    # Split items not in series back into comids and attributes
    df_missing = pd.DataFrame({'comid':[x.split('_')[0] for x in uniq_cmbo_absent],
                               'attribute': [re.sub(r'^\d+_','',x) for x in uniq_cmbo_absent],
                               'config_file' : Path(path_tfrm_cfig).name,
                                'uniq_cmbo':np.nan,
                                'dl_dataset':np.nan
                              }).drop_duplicates().reset_index()
    
    # Save this to file, appending if missing data already exist.
    df_missing.to_csv(path_need_attrs, mode = 'a',
                                header= not path_need_attrs.exists(),
                                index=False)
    print(f"Wrote needed comid-attributes to \n{path_need_attrs}")

    #%% Run R script to search for needed data. 
    # The R script reads in the path_need_attrs csv and searches for these data
    if df_missing.shape[0]>0: # Some data were missing
        path_fs_attrs_miss = fio.get('path_fs_attrs_miss').format(home_dir = home_dir)

        if path_fs_attrs_miss:
            args = [str(path_attr_config)]
            try:
                print(f"Attempting to retrieve missing attributes using {Path(path_fs_attrs_miss).name}")
                result = subprocess.run(['Rscript', path_fs_attrs_miss] + args, capture_output=True, text=True)
                print(result.stdout) # Print the output from the Rscript
                print(result.stderr)  # If there's any error output
            except:
                print(f"Could not run the Rscript {path_fs_attrs_miss}." +
                        "\nEnsure proc.attr.hydfab R package installed and appropriate path to fs_attrs_miss.R")
###############################################################################
    #%% Run the standard processing of attribute transformation:
    fta.tfrm_attr_comids_wrap(comids=comids, path_tfrm_cfig=path_tfrm_cfig)

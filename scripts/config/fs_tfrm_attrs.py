# If additional attribute transformations desired, the natural step in the workflow
#  is after the attributes have been acquired, and before running fs_proc_algo.py 

import argparse
import yaml
import pandas as pd
from pathlib import Path
import fs_algo.fs_algo_train_eval as fsate
import fs_algo.fs_tfrm_attr as fta
import itertools
from collections import ChainMap


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'process the algorithm config file')
    parser.add_argument('path_tfrm_cfig', type=str, help='Path to the YAML configuration file specific for algorithm training')
    args = parser.parse_args()

    home_dir = Path.home()
    path_tfrm_cfig = Path(args.path_tfrm_cfig)#path_tfrm_cfig = Path(f'{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa/xssa_attrs_tform.yaml') 

    with open(path_tfrm_cfig, 'r') as file:
        tfrm_cfg = yaml.safe_load(file)

    # Read from transform config file:
    catgs_attrs_sel = [x for x in list(itertools.chain(*tfrm_cfg)) if x is not None]
    idx_tfrm_attrs = catgs_attrs_sel.index('transform_attrs')
    idx_file_io = catgs_attrs_sel.index('file_io')
    fio = dict(ChainMap(*tfrm_cfg[idx_file_io]['file_io'])) # dict of file input/output, read-only combined view

    # Extract desired content from attribute config file
    path_attr_config=fsate.build_cfig_path(path_tfrm_cfig, Path(fio.get('name_attr_config')))
    attr_cfig = fsate.AttrConfigAndVars(path_attr_config) # TODO consider fsate
    attr_cfig._read_attr_config()

    # Define all directory paths in case used in f-string evaluation
    dir_base = attr_cfig.attrs_cfg_dict.get('dir_base') 
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets')

    #%% READ COMIDS FROM CUSTOM FILE (IF path_comids present in tfrm config)
    # Extract location of custom file containing comids:
    path_comid = eval(f"f'{fio.get('path_comids', None)}'")
    ls_comid = list()
    # Read in comid from custom file (e.g. predictions)
    if path_comid:
        path_comid = Path(path_comid)
        colname_comid = fio.get('colname_comid') # TODO adjust this to fio 
        df_comids = fta.read_df_ext(path_comid)
        ls_comid = ls_comid + df_comids[colname_comid].to_list()

    #%%  READ COMIDS GENERATED FROM proc_attr_hydfab 
    likely_ds_types = ['training','prediction']
    loc_id_col = 'comid'
    name_attr_config = fio.get('name_attr_config', None)# TODO read this from the tfrm_attrs config fio 

    ls_comids_attrs = list()
    if  name_attr_config: 
        # Attribute metadata containing a comid column as standard format 
        path_attr_config = fsate.build_cfig_path(path_tfrm_cfig, name_attr_config)#fsate.build_cfig_path(path_algo_config, name_attr_config)
        ls_comids_attrs = fta._get_comids_std_attrs(path_attr_config)
        
    # Compile unique comid values
    comids = list(set(ls_comid + ls_comids_attrs))
    #%% Parse aggregation/transformations in config file
    tfrm_cfg_attrs = tfrm_cfg[idx_tfrm_attrs]

    # Create the custom functions
    dict_cstm_vars_funcs = fta._retr_cstm_funcs(tfrm_cfg_attrs)
    # Note that this is a flattened length size, based on the total # of transformation functions & which transformations are needed
    
    # Desired custom variable names (corresponds to 'attribute' column) 
    dict_all_cstm_vars = dict_cstm_vars_funcs.get('dict_all_cstm_vars')

    # functions: The list of the actual function objects
    dict_func_objs = dict_cstm_vars_funcs['dict_tfrm_func_objs']
    # functions: Desired transformation functions w/ vars (as str objs (corresponds to 'data_source' column))
    dict_all_cstm_funcs = dict_cstm_vars_funcs.get('dict_cstm_func')
    ls_all_cstm_funcs = list(dict_all_cstm_funcs.values())
    # functions: The just-function in string format
    dict_cstm_func = dict_cstm_vars_funcs['dict_tfrm_func']
    # vars: The dict of attributes to aggregate for each custom variable name
    dict_retr_vars = dict_cstm_vars_funcs.get('dict_retr_vars')

    # TODO create a wrapper function for all steps in config transformation??
    # proc_tfrm_cfg(tfrm_cfg= tfrm_cfg, idx_tfrm_attrs: int,
                    #    all_attr_ddf=all_attr_ddf))
    for comid in comids:
        # Filepath substring structures based on comids 
        # THIS IS INTENDED TO BE A HARD-CODED FILENAME STRUCTURE!!
        # fp_struct_tfrm=f'_{comid}_tfrmattr' # The unique string in the filepath name based on custom attributes created by RaFTS users

        # # Lazy load dask df of transform attributes for a given comid
        # tfrm_attr_ddf =  fta._subset_ddf_parquet_by_comid(dir_db_attrs=dir_db_attrs,
        #                                             fp_struct=fp_struct_tfrm)
        
   
        #%% IDENTIFY NEEDED ATTRIBUTES/FUNCTIONS
        # ALL attributes for a given comid, read using a file
        all_attr_ddf = fta._subset_ddf_parquet_by_comid(dir_db_attrs,
                                        fp_struct=comid)

        # Identify the needed functions based on querying the comid's attr data's 'data_source' column
        #  Note the custom attributes used the function string as the 'data_source'
        dict_need_vars_funcs = fta._id_need_tfrm_attrs(
                                all_attr_ddf=all_attr_ddf,
                                ls_all_cstm_vars=None,
                                ls_all_cstm_funcs = ls_all_cstm_funcs)

        # TODO Check whether all variables used for aggregation exist in parquet files
        # Find the custom variable names we need to create; also the key values in the dicts returned by _retr_cstm_funcs()
        cstm_vars_need =  [k for k, val in dict_all_cstm_funcs.items() if val in dict_need_vars_funcs.get('funcs')]

        #%% Loop over each needed attribute:
        ls_df_rows = list()
        for new_var in cstm_vars_need: 
            if len(cstm_vars_need) != len(dict_need_vars_funcs.get('funcs')):
                raise ValueError("DO NOT PROCEED! Double check assumptions around fta._id_need_tfrm_attrs indexing")
            
            # Retrieve the transformation function object
            func_tfrm = dict_func_objs[new_var]

            # The attributes used for creating the new variable
            attrs_retr_sub = dict_retr_vars.get(new_var)
            
            # Retrieve the variables of interest for the function
            df_attr_sub = fsate.fs_read_attr_comid(dir_db_attrs, comids_resp=[comid], attrs_sel=attrs_retr_sub,
                            _s3 = None,storage_options=None,read_type='filename')
            
            # Apply transformation
            # Subset data to variables and compute new attribute
            attr_val = fta._sub_tform_attr_ddf(all_attr_ddf=all_attr_ddf, 
                        retr_vars=attrs_retr_sub, func = func_tfrm)
            
            # Populate new values in the new dataframe
            new_df = fta._gen_tform_df(all_attr_ddf=all_attr_ddf, 
                                new_var_id=new_var,
                                attr_val=attr_val,
                                tform_type = dict_cstm_func.get(new_var),
                                retr_vars = attrs_retr_sub)
            ls_df_rows.append(new_df)

        if len(ls_df_rows) >0:
            df_new_vars = pd.concat(ls_df_rows)
            # Update existing dataset with new attributes/write updates to file
            df_new_vars_updated = fta.io_std_attrs(df_new_vars=df_new_vars,
                            dir_db_attrs=dir_db_attrs,
                            comid=comid, 
                            attrtype='tfrmattr')

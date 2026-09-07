'''
Helper functions for processing response variable datasets in a standardized fashion. 
In addition some limited functionality to also prepare & standardize hfATLAS predictor datasets.

:description: functions read in yaml schema and standardize response variable datasets
:note: developed using python v3.12

'''
#  Changelog/contributions
#     2024-07-02 Originally created, GL
#     2024-07-09 added different file format/dir path options; add file format checkers, GL
#     2024-08-13 update docstrings, GL
#     2025-08-18 add logging, GL
#     2026-07-24 implement pint unit mapping before stripping, GL
import pandas as pd
from pathlib import Path
import yaml
import xarray as xr
import netCDF4
import warnings
import os
import shutil
from importlib import resources as impresources
from rafts_prep import data
from itertools import compress
import pynhd as nhd
import logging
import __future__
import sys
import rafts_algo.utils as raftsutil
#pd.set_option('future.no_silent_downcasting', True)

def std_dir_logs(dir_input:str | os.PathLike) -> Path:
    """The standard RaFTS directory for logs

    :param dir_input: The path to the RaFTS directory 'input'
    :type dir_input: str | os.PathLike
    :return: The standard directory for logs
    :rtype: Path
    :seealso: :mod:`proc.attr.hydfab`:func:`std_dir_log`
    """
    if 'home_dir' in str(dir_input):
        warnings.warn("The home_dir placeholder in dir_input assumed to be Path.home()")

        dir_input = dir_input.format(home_dir = str(Path.home()))
    log_dir = Path(dir_input).parent / Path('logs') 
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def std_path_log(dir_input: str | os.PathLike, path_config: str | os.PathLike,
                    script:str = '')-> Path:
    """Standard the path to log files for the script

    :param dir_input: The RaFTS directory path to 'input' folder
    :type dir_input: str | os.PathLike
    :param path_config: Path of the config file which needs logging
    :type path_config: str | os.PathLike
    :param script: The script running the config file, defaults to ''
    :type script: str, optional
    :return: The path to the log file
    :rtype: Path
    :seealso: :mod:`proc.attr.hydfab`:func:`std_path_log`
    """
    if 'home_dir' in str(dir_input):
        dir_input = dir_input.format(home_dir = str(Path.home()))

    ds_dir = Path(path_config).parent.stem
    log_dir = std_dir_logs(dir_input)
    log_ds_dir = log_dir / ds_dir
    log_ds_dir.mkdir(parents=True, exist_ok=True)
    if not script == '':
         script = '_' + script
    filename = str(Path(path_config).stem) + script + '.log'
    path_log = Path(log_ds_dir /  Path(filename))
    return path_log

def _proc_flatten_ls_of_dict_keys(config: dict, key: str) -> list:
    keys_cs = list()
    for v in config[key]:
        keys_cs.append(list(v.keys()))
    return [x for xs in keys_cs for x in xs]

def _read_std_config():
    """Read the standardized categorical mappings with uncertainty bounds.

    This function now points to 'rafts_categories.yaml'.

    :return: YAML configuration file mappings as a dictionary.
    :rtype: dict
    """
    catg_file = impresources.files('rafts_prep').joinpath('data', 'rafts_categories.yaml')
    with catg_file.open("rt") as f:
        std_config = yaml.safe_load(f)
    return std_config


def _conv_ls_dicts_df_long():
    """Convert the YAML configuration into a long-format pandas DataFrame.

    This function has been updated to parse the nested dictionary structure
    from the 'rafts_categories_uncn.yaml' file, extracting the category, 
    response variable, description, and its min/max limits into a tidy DataFrame.

    :param config: Dictionary loaded from the YAML configuration file.
    :type config: dict
    :seealso: :func:`_read_std_config()`
    :return: A long-format DataFrame with the configuration schema.
    :rtype: pd.DataFrame
    """
    config = _read_std_config()
    data_list = []
    for category, items in config.items():
        if category == 'target_var_mappings':
            for item in items:
                for var, description in item.items():
                    data_list.append({
                        'var': var,
                        'description': description,
                        'category': category,
                        'min_lim': None,
                        'max_lim': None
                    })
        else:
            for item in items:
                var = item['resp_var']
                description = item['description']
                min_lim = item['Q_lims']['min_lim']
                max_lim = item['Q_lims']['max_lim']
                data_list.append({
                    'var': var,
                    'description': description,
                    'category': category,
                    'min_lim': min_lim,
                    'max_lim': max_lim
                })

    df = pd.DataFrame(data_list)
    return df

def _proc_check_input_config(
    config: dict, 
    std_keys:list[str]=['file_io','col_schema','formulation_metadata','references'],
    req_col_schema:list[str]=['gage_id', 'respvar_cols'],
    req_form_meta:list[str]=[
        'dataset_name','formulation_base','target_var','start_date', 
        'end_date','cal_status'
        ],
    req_file_io:list[str]=['dir_save', 'save_type','save_loc']
    )-> None:
    """    Check input config file to ensure it contains the minimum expected 
    |    categories

    :param config: A dataset's configuration file for rafts_prep
    :type config: dict
    :param std_keys: Expected keys in the config file dict, defaults to ['file_io','col_schema','formulation_metadata','references']
    :type std_keys: list[str], optional
    :param req_col_schema: The required keys inside col_schema, defaults to ['gage_id', 'respvar_cols']
    :type req_col_schema: list[str], optional
    :param req_form_meta: Required keys inside formulation_metadata, defaults to [ 'dataset_name','formulation_base','target_var','start_date', 'end_date','cal_status' ]
    :type req_form_meta: list[str], optional
    :param req_file_io: Required keys inside file_io, defaults to ['dir_save', 'save_type','save_loc']
    :type req_file_io: list[str], optional
    :seealso: :func:`read_schm_ls_of_dict`
    """
    # Changelog/contributions
    # 2024 Summer, originally created, GL
    # 2025-08-19, add logging, make checks more explicit, GL
    #:TODO: add further checks after testing more datasets
    
    # Expected standard keys:

    if any(key not in std_keys for key in config.keys()):
        logging.error(f"Provided keys in the input config file: {config.keys()} \
                         do not match the standard keys: {std_keys}")
        raise ValueError(f"Provided keys in the input config file: {config.keys()} \
                         do not match the standard keys: {std_keys}")

    # required keys defined inside col_schema
    keys_col_schema = _proc_flatten_ls_of_dict_keys(config, 'col_schema')
    if not all([x in keys_col_schema for x in req_col_schema]):
        logging.error("The input config file expects the following"
                        " defined under 'col_schema':"
                        f" {', '.join(req_col_schema)}")
        raise ValueError("The input config file expects the following"
                        " defined under 'col_schema':"
                        f" {', '.join(req_col_schema)}")

    # required keys defined in formulation_metadata
    keys_form_meta = _proc_flatten_ls_of_dict_keys(config, 'formulation_metadata')
    if not all([x in keys_form_meta for x in req_form_meta]):
        logging.error("The input config file expects the following"
                        " defined under 'formulation_metadata':"
                        f" {', '.join(req_form_meta)}")
        raise ValueError("The input config file expects the following"
                        " defined under 'formulation_metadata':"
                        f" {', '.join(req_form_meta)}")

    # required keys defined in file_io
    keys_file_io = _proc_flatten_ls_of_dict_keys(config, 'file_io')
    if not all([x in keys_file_io for x in req_file_io]):
        logging.error(f"The input config file expects the following"
                        f" defined under 'formulation_metadata': {', '.join(req_file_io)}")
        raise ValueError(f"The input config file expects the following"
                        f" defined under 'formulation_metadata': {', '.join(req_file_io)}")

def read_schm_ls_of_dict(schema_path: str | os.PathLike) -> pd.DataFrame:
    """Read a dataset's configuration file designed as a list of dicts

    :param schema_path: path to the user-created configuration file
    :type schema_path: str | os.PathLike
    :return: the filepath to the schema
    :rtype: pd.DataFrame

    """
    # Changelog/contributions
    #   2024-07-02 Originally created, GL
    #.  2025-10-10 add home_dir handling, GL
    #.  2026-07-23 revise file_io: Only attempt to .format if the string actually contains the home_dir placeholder, Gemini3.1pro
    # Load the YAML configuration file
    with open(schema_path, 'r') as file:
        config = yaml.safe_load(file)

    # Run check on expected config formats
    _proc_check_input_config(config)

    # Check for home_dir inside file_io & assign '~' if not present
    home_dir = next((d['home_dir'] for d in config.get('file_io') if 'home_dir' in d), '~')
    
    # Convert dict of lists into pd.DataFrame
    ls_form = list()
    for k, vv in config.items():
        for v in vv:
            if k == 'file_io':
                for key, value in v.items():
                    # Only attempt to format if the string actually contains the home_dir placeholder
                    if isinstance(value, str) and '{home_dir}' in value:
                        new_path = value.format(home_dir=home_dir)
                    else:
                        new_path = value
                    
                    if home_dir in new_path:
                        new_path = str(Path(new_path).expanduser())
                    v[key] = new_path
            ls_form.append(pd.DataFrame(v, index = [0]))
    df_all = pd.concat(ls_form, axis=1)

    return df_all
# --------------------------------------------------------------------------- #
# ----------------------- Standard dirs & paths ----------------------------- #
def name_std_uniq(dataset_name:str, formulation_id:str) -> str:
    # Create the unique filename corresponding to a dataset & formulation
    uniq_filename = f'{dataset_name}_{formulation_id}'
    return uniq_filename
def dir_std_dataset(dir_save: str|os.PathLike, 
                    dataset_name: str) -> os.PathLike:
    save_dir_base = Path(Path(dir_save) / Path('user_data_std') / dataset_name)
    return save_dir_base
def path_std_dataset(dir_save: str|os.PathLike, dataset_name:str,
                formulation_id:str, fmt:str = ['nc','zarr'][0])->os.PathLike:
    dir_save_base = dir_std_dataset(dir_save,dataset_name)
    uniq_filename = name_std_uniq(dataset_name,formulation_id)
    if fmt == 'zarr':
        uniq_filename = uniq_filename + '_zarr'
    save_path = Path(dir_save_base / Path(f'{uniq_filename}.{fmt}'))
    return save_path
def dir_std_meta_raw(dir_save:str|os.PathLike, dataset_name:str)->os.PathLike:
    dir_save_base = dir_std_dataset(dir_save, dataset_name)
    dir_save_meta = Path(dir_save_base / Path('metadata'))
    return dir_save_meta
def path_std_meta_raw(dir_save: str | os.PathLike, dataset_name:str,
                      formulation_id:str,fmt=['csv','parquet']) -> os.PathLike:
    uniq_filename = name_std_uniq(dataset_name,formulation_id)
    dir_save_meta = dir_std_meta_raw(dir_save, dataset_name)
    path_save_meta = dir_save_meta / f'{uniq_filename}_metadata.{fmt}'
    return path_save_meta
def dir_std_eval_metr(dir_save:str|os.PathLike,dataset_name:str)->os.PathLike:
    dir_save_base = dir_std_dataset(dir_save, dataset_name)
    dir_eval_metr = dir_save_base / 'eval' / 'metrics'
    return dir_eval_metr
def path_std_eval_metr(dir_save: str | os.PathLike, dataset_name:str,
                      formulation_id:str) -> os.PathLike:
    dir_eval_metr =dir_std_eval_metr(dir_save,dataset_name)
    uniq_filename = name_std_uniq(dataset_name,formulation_id)
    save_path_eval_metr = dir_eval_metr / Path(f'{uniq_filename}.csv')
    return save_path_eval_metr

def std_form_id(col_schema_df:pd.DataFrame)->str:
    """The standardized formulation id generator - these should be unique

    :param col_schema_df: Generated by `read_schm_ls_of_dict`
    :type col_schema_df: pd.DataFrame
    :return: The standardized name describing a formulation
    :rtype: str
    """
    # TODO generate a unique formulation-id checker

    formulation_id =  col_schema_df.loc[0, 'formulation_id']
    formulation_base =  col_schema_df.loc[0, 'formulation_base']

    if formulation_id == None:
        # Create formulation_id as a combination of formulation_base and 
        # other elements
        formulation_id = '_'.join(
            list(
                filter(
                    None,
                    [
                        formulation_base,
                        '_v',
                        col_schema_df.loc[0, 'formulation_ver'], 
                        '_',
                        col_schema_df.loc[0,'dataset_name']
                    ]
                )
            )
        ) 
    return formulation_id

def _save_dir_struct(dir_save: str | os.PathLike, 
                        dataset_name: str, 
                        save_type:str ) -> tuple[Path, dict]:
    # Create a standard directory saving structure (in cases of local filesaving)
    # Changelog / contributions
    #. 2024 Summer - originally created
    #. 2025-09-01 Commented out dirs that haven't been used but keeping as 
    #       placeholders; adapted with standardized dir/path funcs, GL
    save_dir_base = dir_std_dataset(dir_save, dataset_name) #Path(Path(dir_save) / Path('user_data_std') / dataset_name)
    save_dir_base.mkdir(exist_ok=True, parents = True)

    other_save_dirs = dict()
    if save_type == 'csv' or save_type == 'parquet': # For non-hierachical files
        # Otherwise single hierarchical files will be saved in lieu of
        # subdirectories populated w/ .csv files

        # Design dir structure for writing multiple files
        #save_dir_attr = Path(save_dir_base / Path('attributes'))
        save_dir_eval_metr = dir_std_eval_metr(dir_save,dataset_name)
        #save_dir_eval_ts = Path(save_dir_base / Path('eval')/Path('timeseries'))
        save_dir_meta = dir_std_meta_raw(dir_save,dataset_name)
        #save_dir_meta_lic = Path(save_dir_meta/Path('license'))
        #save_dir_config =  Path(save_dir_base / Path('config'))
        # Generate the expected subdirectories for storing multiple files
        # save_dir_attr.mkdir(exist_ok=True, parents = True)
        save_dir_eval_metr.mkdir(exist_ok=True, parents = True)
        #save_dir_eval_ts.mkdir(exist_ok=True, parents = True)
        save_dir_meta.mkdir(exist_ok=True, parents = True)
        #save_dir_config.mkdir(exist_ok=True, parents = True)
        other_save_dirs = {#'attr': save_dir_attr, 
                            'eval_metr': save_dir_eval_metr, 
                            #'eval_ts' : save_dir_eval_ts,
                            'meta': save_dir_meta, 
                            #'meta_lic': save_dir_meta_lic, 
                            #'config': save_dir_meta
                            }

    return save_dir_base, other_save_dirs
# --------------------------------------------------------------------------- #
def _proc_check_std_rafts_ids(vars_map: list, category=['metric','target_var'][0]):
    """
    Run check to ensure that variables are listed in the standardized 
        rafts_categories.yaml

    :param vars_map: user-defined variable listing of the anticipated mapped
        variables (e.g. ['NSE','RMSE'])
    :type vars_map: list
    :param category: choose the category of 'metric' or 'target_var' desired
        from the rafts standardized categories file. Defaults to 'metric'
    :type category: list, optional
    :raises ValueError: If at least one of the provided vars_map is not standard,
        raises error. 
    """

    # perform check on input data and convert to list if needed:
    if isinstance(vars_map,str):
        vars_map = [vars_map]
        
    if isinstance(category,list) and len(category)>1:
        logging.error(f'Expect {category} to be a single value, not list')
        raise ValueError(f'Expect {category} to be a single value, not list')

    # Read in the standardized names
    df_std_config = _conv_ls_dicts_df_long()
    # Subset the categories (e.g. target_variables or metrics)
    sub_std_config = df_std_config[df_std_config['category'].str.contains(category)]

    # Check to make sure that each metric is inside the standardized names
    bool_chck = [any(sub_std_config['var'] == x) for x in vars_map]
    
    if not all(bool_chck):
        bad_vars = list(compress(vars_map,[not x for x in bool_chck]))
        allowable_vars = ",".join(sub_std_config['var'])
        logging.error(f'The following {category} mappings defined in the'
                            ' dataset schema do not correspond to the'
                            f' standardized {category} names:'
                            f' {", ".join(bad_vars)} \n Allowable'
                            f' variables include: {allowable_vars}')
        raise ValueError(f'The following {category} mappings defined in the'
                            ' dataset schema do not correspond to the'
                            f' standardized {category} names:'
                            f' {", ".join(bad_vars)} \n Allowable'
                            f' variables include: {allowable_vars}')
    else:
        logging.info(f'The {category} mappings from the dataset schema match'
                ' expected format.')


def _proc_check_input_df(df: pd.DataFrame, 
                         col_schema_df: pd.DataFrame,
                         val_metrics: bool = True) -> pd.DataFrame:
    """
    Checks the input dataset for consistency in expected column format as 
        generated from the yaml config file.

    :param df: The dataset of interest containing at a minimum catchment ID 
        and evaluation metrics
    :type df: pd.DataFrame
    :param col_schema_df: The column schema naming convention ingested from 
        the yaml file corresponding to the dataset.
    :type col_schema_df: pd.DataFrame
    :param val_metrics: Set to True to validate the metric columns in the input dataframe.
    :type val_metrics: bool
    :return: wide format df ensuring that the unique identifier for 
        each row is 'gage_id'
    :rtype: pd.DataFrame


    """
    # Changelog/contributions
    #     2024-07-09, originally created, GL
    #     2024-07-11, bugfix in case index is already named 'gage_id', GL

    gage_id = col_schema_df.loc[0, 'gage_id']
    metric_cols = col_schema_df.loc[0, 'respvar_cols']
    metrics = metric_cols.split('|')

    # check that all metric columns in schema file are in input dataframe
    # extract column names holding metrics
    metric_columns = metric_cols.split("|")

    if df.columns.isin(metric_columns).sum() != len(metrics):

        # get names of metrics not in df
        missing_columns = [
            col for col in metric_columns if col not in df.columns
            ]

        logging.warning('\nThe following metric columns are not in your input'
                      f' dataframe, df:\n    {", ".join(missing_columns)}\n'
                      ' \nRevise the config file or ensure'
                       ' the input data is in appropriate format\n'
                        ' (i.e. wide format for each variable)')
 
    if not df.index.name == 'gage_id':
        # Change the name to gage_id   
        df.rename(columns = {gage_id : 'gage_id'},inplace=True)
        if not any(df.columns.str.contains('gage_id')):
            msg_err_colname = f'Expecting one df column to be named: {gage_id}' \
                                ' - per the config file. Inspect config file' \
                                ' and/or dataframe col names'
            logging.error(msg_err_colname)
            raise ValueError(msg_err_colname)
        # Set gage_id as the index
        if any(df['gage_id'].duplicated()):
            logging.warning('Expect only one gage_id for each row in the data.'
                          ' Convert df to wide format when passing to'
                          ' proc_col_schema(). This could create problems'
                           ' if writing standardized data in hierarchical format.')
        else: # We can set the index as 'gage_id'
            df.set_index('gage_id', inplace=True)


    # Standardize the metrics
    metric_mappings = col_schema_df['respvar_mappings'][0].split('|')

    if val_metrics:
        # Run check that mappings are part of standardized column naming
        _proc_check_std_rafts_ids(metric_mappings, category = 'metric')
    else:
        logging.warning('Skipping validation of metric mappings')
    # rename metrics to the standardized format
    df = df.rename(columns = dict(zip(metrics, metric_mappings)))

    return df
    
def proc_col_schema(df: pd.DataFrame, 
                    col_schema_df: pd.DataFrame, 
                    dir_save: str | os.PathLike, 
                    check_nwis: bool = False
                    ) -> xr.Dataset:
    """
    Process model evaluation metrics into individual standardized files 
        and save a standardized metadata file.

    :param df: pd.DataFrame type. The dataset of interest containing at a 
        minimum catchment ID and evaluation metrics
    :type df: pd.DataFrame
    :param col_schema_df: The column schema naming convention ingested from 
        the yaml file corresponding to the dataset. To create the schema df,
        refer to :func:`read_schm_ls_of_dict`
    :type col_schema_df: pd.DataFrame
    :param dir_save: Path for saving the standardized metric data file(s)
        and the metadata file.
    :type dir_save: str | os.PathLike
    :param check_nwis: Set to True if NWIS gage ids are the standard location 
        identifier in this dataset. If True, this checks whether NWIS gage ids
        are missing leading zeros and provides a correction if needed. Also
        expects `col_schema_df['featureSource'] == 'nwissite'`.
    :type check_nwis: bool
    :raises ValueError: when dir_save does not contain the expected directory
        structure in cases when saving non-hierarchical file formats
    :return: dataset of the standardized data/metadata
    :rtype: xr.Dataset

    :seealso: :func:`read_schm_ls_of_dict`

    """
    # Changelog/contributions
    #  2024-07-02, originally created, GL
    #  2025-08-19, add logging & to_netcdf mode ='w' to overwrite, GL

    logging.info(f"Standardizing datasets and writing to {dir_save}")
    # Based on the standardized column schema naming conventions
    dataset_name =  col_schema_df.loc[0, 'dataset_name']
    formulation_id = std_form_id(col_schema_df)
    save_type = col_schema_df.loc[0, 'save_type']
    save_loc = col_schema_df.loc[0, 'save_loc']
    if 'val_respvar' in col_schema_df.columns:
        # Convert to string and lower() so 'True', 'true', and boolean True all evaluate safely
        val_metrics = str(col_schema_df.loc[0, 'val_respvar']).lower() == 'true'
    else:
        val_metrics = False
    
    # IMPORTANT: Run create_hfatlas_unit_mapper before cleaning the df column names:
    mapper_df = raftsutil.create_hfatlas_unit_mapper(raw_columns=df.columns)

    # TODO add cloud or local saving
    if save_loc == 'local':
         # Optionally creates dir structure  if save_type == 'csv' or 'parquet'
        _save_dir_base, _other_save_dirs = _save_dir_struct(
                                                        dir_save, 
                                                        dataset_name, 
                                                        save_type
                                                        )
    elif save_loc == 'aws':
        logging.info("TODO ensure connect credentials here")
        # TODO define _save_dir_base here in case .csv are desired in cloud

    # Run format checker/df renamer on input data based on config file's entries:
    df = _proc_check_input_df(df,col_schema_df,val_metrics)

    # Run format checker on nwissite gage ids for missing leading zeros
    if check_nwis and col_schema_df['featureSource'].values[0] == 'nwissite':
        # Run check on NWIS gage IDS - make sure leading zeros exist where needed.
        df_new = check_fix_nwissite_gageids(
            df=df, 
            gage_id_col = col_schema_df['gage_id'].values[0],
            featureSource = col_schema_df['featureSource'].values[0], 
            featureID=col_schema_df['featureID'].values[0],
            replace_orig_gage_id_col=True)
        
        check_equal_df = df_new.equals(df)
        if not check_equal_df == None:
            warn_str_diff = (f"The {col_schema_df['gage_id'].values[0]} column" 
                          f" in the input dataset has nwissite gage ID values"
                          f"missing leading zeros. Auto-corrected gage ids may not"
                          f" have caught all issues. Consider inspecting input data.")
            logging.warning(warn_str_diff
                         )
            
            df = df_new.copy()
    elif col_schema_df['featureSource'].values[0] == 'nwissite':
        logging.info(f"The input dataset uses nwissite gage ids. Consider setting\
              \ncheck_nwis=True to run a check on whether the "
              f"{col_schema_df['gage_id'].values[0]} column "
              f"\nin the dataset contains appropriately formatted gage ids, \
              \nspecifically that leading zeros haven't been inadvertently removed.")

    # Convert dataframe to the xarray dataset and add metadata:
    ds = df.to_xarray()
    ds.attrs = col_schema_df.fillna('').astype(str).to_dict('index')[0]
    
    # TODO query a database for the lat/lon corresponding to the gage-id if 
    # lat/lon not already provided

    # Save the standardized dataset
    if save_type == 'csv' or save_type == 'parquet':
        logging.warning(f'Using dataset save_type of {save_type}. STRONGLY RECOMMENDED to use save_type="netcdf"')
        if len(_other_save_dirs) == 0:
            logging.error(
                'Expected _save_dir_struct to generate values in _other_save_dirs'
                )
            raise ValueError(
                'Expected _save_dir_struct to generate values in _other_save_dirs'
                )
        logging.warning("PROBLEM when saving rafts_prep data as .csv or .parquet is that " \
                "rafts_algo.utils assumes netcdf and some refactoring may be needed there.")
        # TODO allow output write to a variety of locations (e.g. local/cloud)
        # Write data in long format
        save_path_eval_metr = path_std_eval_metr(dir_save,dataset_name,formulation_id)
        dir_std_base = save_path_eval_metr.parent.parent.parent.parent     
        if save_type == 'csv':
            df.to_csv(save_path_eval_metr)
        else:
            save_path_eval_metr = Path(str(save_path_eval_metr).replace('.csv','.parquet'))
            df.to_parquet(save_path_eval_metr)
        logging.info(f"Wrote simple standardized dataset to {save_path_eval_metr}")
        # Write metadata table corresponding to these metric data table(s) 
        # (e.g. startDate, endDate)
        
        if save_type == 'csv':
            save_path_meta = path_std_meta_raw(dir_save, dataset_name, formulation_id,fmt='csv') 
            col_schema_df.to_csv(save_path_meta)
        else:
            save_path_meta = path_std_meta_raw(dir_save, dataset_name, formulation_id,fmt='parquet') 
            col_schema_df.to_parquet(save_path_meta)
        logging.info(f"Saved files within a sub-directory structure inside {dir_save}")
    elif save_type == 'netcdf': # This is preferred!!
        save_path_nc = path_std_dataset(dir_save, dataset_name,
                formulation_id, fmt = 'nc')
        if Path(save_path_nc).exists():
            logging.warning(f"NetCDF file {save_path_nc} already exists and will be overwritten.")
            Path(save_path_nc).unlink() # Delete the pre-existing file
        ds.to_netcdf(save_path_nc,mode='w',format='NETCDF4') # mode='w' overwrites
        logging.info(f"Saved netcdf file as {save_path_nc}")
        dir_std_base = Path(save_path_nc).parent.parent
    # Ensure that the original names are mapped in case renamer modifies them (for hfATLAS pint data)
    raftsutil.save_hfatlas_unit_mapper(mapper_df=mapper_df, 
                                    dir_std_base = dir_std_base,
                                     ds=dataset_name,cstm_str="resp_vars")


    return ds # Returning not intended use case, but it's an option

def check_fix_nwissite_gageids(df:pd.DataFrame, gage_id_col:str,
                                featureSource:str = 'nwissite', 
                                featureID:str='USGS-{gage_id}',
                                replace_orig_gage_id_col:bool=True) -> pd.DataFrame:
    """Checks whether USGS gage ID values corresponding to nwissite data follow expected format

    :param df: DataFrame containing a column with nwissite gage id column for format checking
    :type df: pd.DataFrame
    :param gage_id_col: The column name of the gage id column, defaults to 'basin'
    :type gage_id_col: str, optional
    :param featureSource: The :mod:`pynhd` / :language:R: :mod:`nhdplusTools` featureSource describing the source of data, defaults to 'nwissite'
    :type featureSource:  str, optional
    :param featureID: The conversion string to get values inside `df[gage_id_col`] into the `featureSource`'s expected format,, defaults to 'USGS-{gage_id}'
    :type featureID: str, optional
    :param replace_orig_gage_id_col: Should the data inside `df[gage_id_col`] be replaced with the corrected values? If not, an added column named `'fix'` is added, defaults to True
    :type replace_orig_gage_id_col: bool, optional
    :return: The provided `df`, modified in cases when inappropriate `gage_id_col`'s data format found
    :rtype: pd.DataFrame
    """
    # Changelog/contributions:
    #     2024 originally created, GL
    #     2025-06-17 fix: ensure str in gage_id build, and ensure gage_id_col in dataframe contains all str type

    ls_still_bad = list()
    if featureSource == 'nwissite':
        logging.info(f"Checking {df.shape[0]} total USGS gage station IDs for appropriate nwissite format.")
        logging.info(f"This may take {round(df.shape[0]/60/3.2,2)} minutes for the first check")
        nldi = nhd.NLDI()
        ls_bad_ids = list()
        for ix, row  in df.iterrows():
            gid = row[gage_id_col]
            try:
                comid = nldi.navigate_byid(fsource=featureSource,fid= featureID.format(gage_id=gid),
                                        navigation='upstreamMain',
                                        source='flowlines',
                                        distance=1 # the shortest distance
                                        ).loc[0]['nhdplus_comid'] 
            except: # Could not process this particular gid
                ls_bad_ids.append(gid)                                                     
        ls_prezero = ['0'+str(x) for x in ls_bad_ids]

        logging.info(f"Checking whether prepending '0' fixes {len(ls_prezero)} total gage_ids that were not recognized during the first check")
        logging.info(f"This may take {round(len(ls_prezero)/60/3.2,2)} minutes for the second check.")
        for prezero in ls_prezero:
            try:
                nldi.navigate_byid(fsource=featureSource,fid= featureID.format(gage_id=prezero),
                                                navigation='upstreamMain',
                                                source='flowlines',
                                                distance=1 # the shortest distance
                                                ).loc[0]['nhdplus_comid']
            except:
                ls_still_bad.append(prezero)
                pass

        
        if len(ls_bad_ids) > 0:
            logging.info('Some improvements to nwissite IDs found')
            conv_df = pd.DataFrame({'wrong_id': ls_bad_ids,
                                    'good_id' : ls_prezero})
            cmbo_df = df.merge(conv_df, left_on = gage_id_col, right_on ='wrong_id', how='left') 
            cmbo_df['fix'] = cmbo_df['good_id']
            cmbo_df.fillna({'fix':cmbo_df[gage_id_col]},inplace=True)
            # In case some values are still bad, set the 'fix' column's bad vals to NA
            cmbo_df.loc[cmbo_df[gage_id_col].isin(ls_still_bad),'fix'] = pd.NA

            
            cmbo_df.drop(columns = ['wrong_id','good_id'], inplace = True)

            if replace_orig_gage_id_col:
                logging.info(f"Replacing original data from the '{gage_id_col}' column with corrected values.")
                cmbo_df[gage_id_col] = cmbo_df['fix']
                cmbo_df.drop(columns = ['fix'],inplace=True )
            else:
                logging.info(f"Corrected values provided in the 'fix' column of the returned DataFrame.")

            df=cmbo_df.copy()                
            if len(ls_still_bad)>0:
                logging.warning("Some gage_id values still not recognized by USGS nwissite dataset.")
        elif len(ls_still_bad) > 0:
            logging.warning("Some gage_id values still not recognized by USGS nwissite dataset.")
            logging.info(f"Consider checking the following gage_ids: {', '.join(ls_still_bad)}")
        df[gage_id_col] = df[gage_id_col].astype(str)
    return df

def create_custom_nexus_id(gage_id, nexus_id):
    """
    Creates a custom unique identifier combining a gage ID and a nexus ID.
    Supports scalar values, Pandas Series, ArrowStringArrays, lists, or a mix.
    
    :param gage_id: The original basin or gage identifier.
    :param nexus_id: The terminal downstream nexus identifier.
    :return: A custom identifier string (or Pandas Series) formatted as '{gage_id}__{nexus_id}'.
    """
    # Check if inputs are array-like (catches Series, Arrow arrays, np.arrays, lists)
    gage_is_array = hasattr(gage_id, "__iter__") and not isinstance(gage_id, (str, bytes))
    nex_is_array = hasattr(nexus_id, "__iter__") and not isinstance(nexus_id, (str, bytes))
    
    if gage_is_array and nex_is_array:
        return pd.Series(gage_id).astype(str) + "__" + pd.Series(nexus_id).astype(str)
    elif nex_is_array:
        # gage_id is scalar, nexus_id is an array
        return str(gage_id) + "__" + pd.Series(nexus_id).astype(str)
    elif gage_is_array:
        # gage_id is an array, nexus_id is scalar
        return pd.Series(gage_id).astype(str) + "__" + str(nexus_id)
    else:
        # Both are scalars
        return f"{gage_id}__{nexus_id}"
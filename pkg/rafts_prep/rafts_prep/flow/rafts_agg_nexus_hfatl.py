"""
rafts_agg_nexus_hfatl.py

Aggregate hfATLAS attributes by custom nexus-gage identifiers or full-domain nexuses.

:description: Universal aggregator script. Depending on the config provided, it reads 
              either a training mapping or a prediction crosswalk, loads the raw 
              hfATLAS attributes, and performs area-weighted aggregation.
:usage: 
uv run python rafts_agg_nexus_hfatl.py --path_attr_config "nex_test_attr_config.yaml"
uv run python rafts_agg_nexus_hfatl.py --path_pred_config "nex_test_pred_config_hf22.yaml"
"""

import argparse
import pandas as pd
from pathlib import Path
import logging
import numpy as np
import sys
import yaml

# RaFTS / Formulation Selector imports
import rafts_prep.proc_eval_metrics as pem
import rafts_algo.utils as raftsutil

def area_weighted_mean(x):
    """Calculate the weighted mean, handling NaNs safely."""
    weights = df_merged.loc[x.index, area_col_name]
    # Only use weights where the data value and the weight are not NaN
    mask = x.notna() & weights.notna()
    if mask.sum() == 0 or weights[mask].sum() == 0:
        return np.nan
    return np.average(x[mask], weights=weights[mask])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Aggregate hfATLAS attributes.')
    parser.add_argument('--path_attr_config', type=str, default=None, help='Path to the attribute YAML (for training)')
    parser.add_argument('--path_pred_config', type=str, default=None, help='Path to the prediction YAML (for prediction)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not args.path_attr_config and not args.path_pred_config:
        logging.error("You must provide either --path_attr_config or --path_pred_config")
        sys.exit(1)

    # ==========================================
    # 1. DETERMINE MODE & EXTRACT BASE CONFIG
    # ==========================================
    if args.path_pred_config:
        run_mode = 'prediction'
        logging.info("Initializing in PREDICTION mode...")
        path_pred_config = Path(args.path_pred_config).expanduser()
        
        with open(path_pred_config, 'r') as f:
            pred_config = yaml.safe_load(f)
            
        # Dynamically find the attribute config from the prediction config
        name_attr_config = pred_config.get('name_attr_config')
        path_attr_config = Path(raftsutil.build_cfig_path(path_pred_config, name_attr_config))
    else:
        run_mode = 'training'
        logging.info("Initializing in TRAINING mode...")
        path_attr_config = Path(args.path_attr_config).expanduser()

    if not path_attr_config.exists():
        logging.error(f"Attribute config not found: {path_attr_config}")
        sys.exit(1)

    # ==========================================
    # 2. PARSE ATTRIBUTE CONFIGURATIONS
    # ==========================================
    attr_cfig = raftsutil.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()
    home_dir = raftsutil._define_home_dir(attr_cfig.attr_config)
    
    try:
        name_prep_config = [x for x in attr_cfig.attr_config.get('file_io', []) if 'name_prep_config' in x][0]['name_prep_config']
    except IndexError:
        logging.error("Could not find 'name_prep_config' in the 'file_io' section of the attribute config.")
        sys.exit(1)
        
    path_prep_config = raftsutil.build_cfig_path(path_attr_config, name_prep_config)
    
    config_df = pem.read_schm_ls_of_dict(schema_path=path_prep_config)
    raw_config = config_df.iloc[0].dropna().to_dict()
    fio = {k: raftsutil.resolve_fstrings(v, raw_config) for k, v in raw_config.items()}
    
    dataset_name = fio.get('dataset_name')
    formulation_id = pem.std_form_id(config_df)
    save_path_eval_metr = pem.path_std_eval_metr(fio['dir_save'], dataset_name, formulation_id)
    dir_std_base = save_path_eval_metr.parent.parent.parent.parent
    map_divide_id_col = fio.get('map_divide_id_col', 'divide_id')
    
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets')
    ds = datasets[0]
    
    attr_select_list = attr_cfig.attr_config.get('attr_select', [])
    attrs_all = [v for x in attr_select_list for k, v in x.items() if '_vars' in k]
    attrs_sel = [x for x in list(np.concatenate([a for a in attrs_all if a])) if x]
    
    paths_raw = [x.get('paths_hfatl') for x in attr_select_list if x.get('paths_hfatl') is not None]
    paths_hfatl = [Path(str(p).format(home_dir=str(home_dir))).expanduser() for p in paths_raw[0]] if paths_raw else []
    
    hfatl_id_col = next((x.get('hfatl_id_col') for x in attr_select_list if 'hfatl_id_col' in x), map_divide_id_col)
    hfatl_id_format = next((x.get('hfatl_id_format') for x in attr_select_list if 'hfatl_id_format' in x), None)

    # ==========================================
    # 3. SET RUN-MODE SPECIFIC VARIABLES
    # ==========================================
    if run_mode == 'prediction':
        resolve_dict = pred_config.copy()
        resolve_dict['home_dir'] = str(home_dir)
        resolve_dict['dir_std_base'] = str(dir_std_base)
        resolve_dict['ds'] = str(ds)
        
        resolved_pred = {k: raftsutil.resolve_fstrings(v, resolve_dict) if isinstance(v, str) else v for k, v in pred_config.items()}
        
        mapping_file_path = Path(resolved_pred.get('path_crosswalk_ids'))
        target_id_col = resolved_pred.get('pred_file_comid_colname', 'nexus_id')
        
        # Override to None because full domain data doesn't use the custom 'USGS-{gage}_{div}' format
        hfatl_id_format = None 
        
        save_dir = Path(str(dir_db_attrs).format(ds=ds)) / 'prediction'
        out_path = save_dir / "attr_all_prediction.parquet"
        
    else:
        mapping_file_path = dir_std_base / dataset_name / f"{dataset_name}_nexus_divide_mapping.csv"
        target_id_col = 'custom_id'
        
        save_dir = Path(str(dir_db_attrs).format(ds=ds)) / 'all'
        out_path = save_dir / "attr_all.parquet"

    # ==========================================
    # 4. LOAD MAPPING / CROSSWALK
    # ==========================================
    if not mapping_file_path.exists():
        logging.error(f"Mapping file not found: {mapping_file_path}")
        sys.exit(1)
        
    logging.info(f"Loading mapping from {mapping_file_path.name}...")
    if mapping_file_path.suffix == '.parquet':
        df_mapping = pd.read_parquet(mapping_file_path)
    else:
        df_mapping = pd.read_csv(mapping_file_path, dtype=str)
        
    if 'divide_id' in df_mapping.columns and map_divide_id_col != 'divide_id':
        df_mapping = df_mapping.rename(columns={'divide_id': map_divide_id_col})
        
    df_mapping[map_divide_id_col] = df_mapping[map_divide_id_col].astype(str)

    # ==========================================
    # 5. LOAD RAW HFATLAS ATTRIBUTES
    # ==========================================
    unique_divides = df_mapping[map_divide_id_col].unique().tolist()
    logging.info(f"Loading raw hfATLAS attributes for {len(unique_divides)} unique divides...")
    
    df_raw_attrs = raftsutil.read_hfatlas_wrap_dask(
        paths_hfatl=paths_hfatl, 
        attrs_sel=attrs_sel, 
        map_id_col=hfatl_id_col,
    )
    
    raw_columns = pd.read_parquet(paths_hfatl[0]).columns
    mapper_df = raftsutil.create_hfatlas_unit_mapper(raw_columns=raw_columns)
    raftsutil.save_hfatlas_unit_mapper(mapper_df=mapper_df, dir_std_base=dir_std_base, ds=ds)

    # ==========================================
    # 6. RECONSTRUCT ID FOR MERGING
    # ==========================================
    if hfatl_id_format:
        logging.info(f"Applying hfatl_id_format '{hfatl_id_format}' to construct merge keys...")
        df_mapping[hfatl_id_col] = df_mapping.apply(
            lambda row: hfatl_id_format.format(
                gage_id=row.get('gage_id', ''),
                divide_id=row.get(map_divide_id_col, '')
            ),
            axis=1
        )
        merge_col = hfatl_id_col
    elif hfatl_id_col != map_divide_id_col and hfatl_id_col in df_raw_attrs.columns:
        df_raw_attrs = df_raw_attrs.rename(columns={hfatl_id_col: map_divide_id_col})
        merge_col = map_divide_id_col
    else:
        merge_col = map_divide_id_col

    # ==========================================
    # 7. CLEAN AND UNPACK COMPLEX COLUMNS
    # ==========================================
    logging.info("Unpacking complex struct columns...")
    data_cols = [c for c in attrs_sel if c in df_raw_attrs.columns]

    for col in data_cols:
        if df_raw_attrs[col].dtype == 'object':
            df_raw_attrs[col] = df_raw_attrs[col].apply(
                lambda x: list(x.values())[0] if isinstance(x, dict) else (
                          x[0] if isinstance(x, (list, np.ndarray)) else x)
            )
        df_raw_attrs[col] = pd.to_numeric(df_raw_attrs[col], errors='coerce')

    # ==========================================
    # 8. AGGREGATE BY TARGET ID
    # ==========================================
    logging.info(f"Merging mapping and computing aggregations by {target_id_col}...")
    df_merged = pd.merge(df_mapping, df_raw_attrs, on=merge_col, how='inner')

    agg_dict = {
        col: 'mean' 
        for col in data_cols 
        if col not in ['area_sqkm', 'areasqkm'] and col in df_merged.columns
    }
    
    area_col_name = None
    for area_col in ['area_sqkm', 'areasqkm']:
        if area_col in df_merged.columns:
            agg_dict[area_col] = 'sum'
            area_col_name = area_col
            break

    try:
        if area_col_name is None:
            raise ValueError("No area column found in the dataset to use as weights.")
            
        logging.info("Attempting area-weighted mean aggregation...")
        wm_agg_dict = {
            col: area_weighted_mean 
            for col in data_cols 
            if col != area_col_name and col in df_merged.columns
        }
        wm_agg_dict[area_col_name] = 'sum'
        
        df_aggregated = df_merged.groupby(target_id_col).agg(wm_agg_dict).reset_index()
        logging.info("Area-weighted mean aggregation successful!")
        
    except Exception as e:
        logging.warning(f"Area-weighted mean failed ({e}). Falling back to simple mean.")
        df_aggregated = df_merged.groupby(target_id_col).agg(agg_dict).reset_index()

    logging.info("Reshaping aggregated attributes to RaFTS standard long-format schema...")
    
    featureSource = fio.get('featureSource', 'nexus')
    
    df_long = df_aggregated.melt(
        id_vars=[target_id_col], 
        var_name='attribute', 
        value_name='value'
    )
    
    df_long = df_long.rename(columns={target_id_col: 'featureID'})
    df_long['featureSource'] = featureSource
    df_long['data_source'] = "hfATLAS_aggregated_nexus"
    df_long['dl_timestamp'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    df_long['vpuid'] = 'all' 
    
    final_columns = ['vpuid', 'featureID', 'featureSource', 'data_source', 'dl_timestamp', 'attribute', 'value']
    df_long = df_long[final_columns]

    # ==========================================
    # 9. EXPORT TO ALGORITHM DATABASE
    # ==========================================
    save_dir.mkdir(parents=True, exist_ok=True)
    df_long.drop(columns=['vpuid']).to_parquet(out_path, index=False)
    
    logging.info(f"✅ Success! Analysis-ready aggregated attributes for {df_aggregated.shape[0]} target locations saved to:")
    logging.info(f"   {out_path}")
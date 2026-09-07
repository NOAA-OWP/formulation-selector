'''
@title: Ingest and Prepare Data for hfATLAS Workflow
@description: Reads the local hfATLAS Parquet and Hydrofabric GPKG, 
    generates response metrics, extracts geometries, and builds partitioned attributes.
@usage: python prep_hfatl_metrics.py "/full/path/to/hfatl_prep_config.yaml"
'''
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import rafts_prep.proc_eval_metrics as pem
import rafts_algo.utils as raftsutil
import logging

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process the YAML config file.')
    parser.add_argument('path_config', type=str, help='Path to the YAML configuration file')
    args = parser.parse_args()
    
    path_prep_config = Path(args.path_config).expanduser() 

    if not path_prep_config.exists():
        raise ValueError(f"The provided path to the configuration file does not exist: {path_prep_config}")

    # Load Prep Config
    col_schema_df = pem.read_schm_ls_of_dict(schema_path=path_prep_config)
    home_dir = raftsutil._make_home_dir([])
    path_data = Path(col_schema_df['path_data'].loc[0].format(home_dir=home_dir))
    dir_save = col_schema_df['dir_save'].loc[0].format(home_dir=home_dir)
    dataset_name = col_schema_df['dataset_name'].loc[0]

    # Initialize logging
    path_log = pem.std_path_log(dir_input=dir_save, path_config=path_prep_config, script='prep_hfatl_metrics')
    logging.basicConfig(level=logging.INFO, filename=path_log, format='%(asctime)s - %(levelname)s - %(message)s')

    # Load Attribute Config
    path_attr_config = raftsutil.build_cfig_path(path_prep_config, "hfatl_attr_config.yaml")
    attr_cfig = raftsutil.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()
    
    hf_io = attr_cfig.attr_config.get('hydrofabric_io', [])
    context = {'home_dir': home_dir}
    path_hf_gpkg = Path(raftsutil.resolve_fstrings(hf_io[0]['path_hf_gpkg'], context))
    hf_layer = hf_io[1]['hf_layer']
    hf_map_id_col = hf_io[2]['hf_map_id_col']
    
    dir_db_attrs = Path(str(attr_cfig.attrs_cfg_dict.get('dir_db_attrs')).split('{')[0])
    dir_std_base = Path(attr_cfig.attrs_cfg_dict.get('dir_std_base'))
    ds_dir = dir_std_base / dataset_name
    gpkg_loc_path = ds_dir / f"{dataset_name}_loc.gpkg"

    logging.info("Generating Mock Response Metrics from raw data...")
    # Read raw hfATLAS data
    df_ha = pd.read_parquet(path_data)
    
    # Check for and clean pint tuple formats just in case
    is_tuple_format = df_ha.columns.astype(str).str.match(r"^\('.*', '.*'\)$")
    if is_tuple_format.any():
        df_ha = raftsutil.clean_hfatlas_columns(df_ha)
        
    # --- DYNAMIC COLUMN DETECTION ---
    # The raw HydroATLAS parquet might use hf_uid, hf_id, id, or divide_id.
    # We must find the correct column before extracting the data.
    detected_id_col = None
    for c in ["hf_uid", "hf_id", "divide_id", "id"]:
        if c in df_ha.columns:
            detected_id_col = c
            break
            
    if not detected_id_col:
        raise KeyError(f"Could not find a valid ID column in {path_data.name}. Available columns: {list(df_ha.columns)}")
        
    # Extract the first 60 IDs, cast to string, and strip the 'hf_id_' prefix if it exists
    raw_ids = df_ha[detected_id_col].head(60).astype(str)
    div_ids = raw_ids.str.replace("hf_id_", "").tolist()
    
    # Generate test metrics (NSE/KGE) to mimic hydrologic model output
    df_metrics = pd.DataFrame({
        hf_map_id_col: div_ids,
        'NSE': np.random.uniform(0.1, 0.9, len(div_ids)),
        'KGE': np.random.uniform(0.1, 0.9, len(div_ids))
    })

    # Standardize Dataset (.nc file)
    pem.proc_col_schema(df_metrics, col_schema_df, dir_save)

    # Core hfATLAS Extraction API
    logging.info("Extracting points GPKG...")
    gdf_hf_points = raftsutil.generate_algo_points_gpkg_wrap(
        div_ids=pd.Series(div_ids),
        path_hf_gpkg=path_hf_gpkg, 
        path_gpkg_rafts_prep=gpkg_loc_path,
        hf_layer=hf_layer,
        map_id_col=hf_map_id_col,
        featureSource='hf_test_source'
    )
    
    logging.info("Lazy-loading and merging hfATLAS attributes...")
    ha_vars = attr_cfig.attr_config['attr_select'][1]['ha_vars']
    df_hfatlas = raftsutil.read_hfatlas_wrap_dask([path_data], attrs_sel=ha_vars, map_id_col=hf_map_id_col)
    
    logging.info("Writing VPU-partitioned parquet attributes...")
    raftsutil.hfatl_hf_cmbo_wrap(
        df_hfatlas=df_hfatlas,
        gdf_hf=gdf_hf_points,
        ds=dataset_name,
        dir_db_attrs=dir_db_attrs, 
        featureSource='hf_test_source',
        vpu_mapped=True
    )
    
    # Generate Metadata Parquets
    meta_df = pd.DataFrame({
        'gage_id': div_ids,
        'featureID': div_ids,
        'featureSource': ['hf_test_source'] * len(div_ids)
    })
    meta_df.to_parquet(ds_dir / f"nldi_feat_{dataset_name}_training.parquet")
    meta_df.to_parquet(ds_dir / f"nldi_feat_{dataset_name}_prediction.parquet")
    
    logging.shutdown()
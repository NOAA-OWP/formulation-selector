"""Aggregate hfATLAS attributes by gaged basins

:description: Reads a hydrofabric GPKG (either a single file or a directory of files), 
              extracts the divide-to-gage mapping, loads the raw hfATLAS attributes, 
              and aggregates them to the gage level.
:details: Expects the prep config to contain the path_hf_basins_gpkg inside file_io section.
:usage: 
uv run python rafts_agg_hfatl_basin.py --path_prep_config "regn_prep_config.yaml" --path_attr_config "regn_attr_config.yaml"

Changelog/contributions
    2026-05-22 Created with Gemini3.1Pro
    2026-09-02 Refactored to utilize targeted Pydantic AttrSelectConfig validation.
    2026-09-21 Refactored Prep YAML parsing to explicitly extract file_io mapping columns, preventing ID merge failures.
"""
# TODO add _std_rafts_prep_ds_companion_gpkg_path and ensure geometry is written to file
import argparse
import pandas as pd
import geopandas as gpd
from pathlib import Path
import yaml
import logging
import re
import numpy as np

# RaFTS / Formulation Selector imports
import rafts_prep.proc_eval_metrics as pem
import rafts_algo.utils as raftsutil
from rafts_prep.schemas.rafts_prep_pydantic_schemas import AttrSelectConfig, flatten_yaml_list

# Calculate the weighted mean, handling NaNs safely
def area_weighted_mean(x):
    weights = df_merged.loc[x.index, area_col_name]
    # Only use weights where the data value and the weight are not NaN
    mask = x.notna() & weights.notna()
    if mask.sum() == 0 or weights[mask].sum() == 0:
        return np.nan
    return np.average(x[mask], weights=weights[mask])
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Aggregate hfATLAS attributes based on hydrofabric divides.')
    parser.add_argument('--path_prep_config', type=str, required=True, help='Path to the prep YAML configuration file')
    parser.add_argument('--path_attr_config', type=str, required=True, help='Path to the attribute YAML configuration file')
    parser.add_argument('--validate', action='store_true', default=False,
                        help='If present, enables schema validation of the aggregated output. Defaults to False.')
    args = parser.parse_args()
    
    arg_val = args.validate
    if arg_val:
        logging.info("Schema validation enabled. Using statically imported schemas from rafts_algo.schemas.")

    path_prep_config = Path(args.path_prep_config).expanduser()
    path_attr_config = Path(args.path_attr_config).expanduser()

    if not path_prep_config.exists():
        raise FileNotFoundError(f"Prep config not found: {path_prep_config}")
    if not path_attr_config.exists():
        raise FileNotFoundError(f"Attribute config not found: {path_attr_config}")

    # ==========================================
    # 1. PARSE CONFIGURATIONS
    # ==========================================
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Parsing configurations...")

    # A. Parse Attribute Config base variables
    attr_cfig = raftsutil.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()
    home_dir = raftsutil._define_home_dir(attr_cfig.attr_config)

    # B. Parse Prep Config directly from YAML to preserve 'file_io' spatial mapping variables
    with open(path_prep_config, 'r') as f:
        prep_cfg_raw = yaml.safe_load(f)
        
    fio = flatten_yaml_list(prep_cfg_raw.get('file_io', []))
    fio = {k: raftsutil.resolve_fstrings(v, {'home_dir': str(home_dir)}) if isinstance(v, str) else v for k, v in fio.items()}

    cs = flatten_yaml_list(prep_cfg_raw.get('col_schema', []))
    cs = {k: raftsutil.resolve_fstrings(v, {'home_dir': str(home_dir)}) if isinstance(v, str) else v for k, v in cs.items()}

    fm = flatten_yaml_list(prep_cfg_raw.get('formulation_metadata', []))

    # Extract geospatial mappings
    path_hf_basins_gpkg = Path(fio.get('path_hf_basins_gpkg')) if 'path_hf_basins_gpkg' in fio else None
    if path_hf_basins_gpkg:
        gpkg_pattern = fio.get('gpkg_filename_pattern', r'gage_(.*)\.gpkg')
        if path_hf_basins_gpkg.exists():
            logging.info(f"Hydrofabric basins GPKG path: {path_hf_basins_gpkg}")
        else:
            logging.error(f"Specified path_hf_basins_gpkg does not exist: {path_hf_basins_gpkg}")
    else:
        # Fatal: every downstream reference (gpkg_pattern, path_hf_basins_gpkg.is_dir(), etc.)
        # requires this to be set. Logging alone previously let execution fall
        # through to a confusing NameError/AttributeError far below instead of
        # a clear config error here.
        msg = "Missing the path_hf_basins_gpkg in the prep config, which is required to perform divide attribute aggregation to basin scales"
        logging.error(msg)
        raise ValueError(msg)

    divides_layer = fio.get('hf_divides_layer', 'divides')
    map_divide_id_col = fio.get('map_divide_id_col', 'divide_id')
    dataset_name = fm.get('dataset_name', 'aggregated')
    
    gage_id_col_gpkg = fio.get('gage_id_col_gpkg', cs.get('gage_id'))
    if not gage_id_col_gpkg:
        logging.error("Expecting 'gage_id_col_gpkg' or 'gage_id' entries in the prep config.")
        print("Consider adding 'gage_id_col_gpkg' entry to prep config")

    regex_compiled = re.compile(gpkg_pattern, re.IGNORECASE)

    hf_layer = fio.get('hf_fp_layer', 'flowpaths')
    vpu_id_col = fio.get('vpu_id_col', 'vpuid')
    dir_std_base = Path(attr_cfig.attrs_cfg_dict.get('dir_std_base'))

    # C. Validate and Extract Attribute Selection Config
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets')
    if len(datasets) > 1:
        logging.error("Multiple datasets imcompatible with rafts_agg_hfatl_basin.py")
    ds = datasets[0]
    dir_db_attrs_agg_save = raftsutil.std_dir_ds_agg(dir_db_attrs, ds)
    
    attr_select_raw = attr_cfig.attr_config.get('attr_select', [])
    flat_attr_select = flatten_yaml_list(attr_select_raw)
    
    # Scrub commented-out YAML list items (which parse as None) before Pydantic validation
    if 'hfatl_vars' in flat_attr_select and isinstance(flat_attr_select['hfatl_vars'], list):
        flat_attr_select['hfatl_vars'] = [v for v in flat_attr_select['hfatl_vars'] if v is not None]
        
    validated_attr_select = AttrSelectConfig(**flat_attr_select)
    
    attrs_sel = validated_attr_select.hfatl_vars
    hfatl_id_col = validated_attr_select.hfatl_id_col
    
    paths_hfatl = []
    for p in validated_attr_select.paths_hfatl:
        resolved_path = Path(p.format(home_dir=str(home_dir))).expanduser()
        if resolved_path.exists():
            paths_hfatl.append(resolved_path)

    if not paths_hfatl:
        raise ValueError("No valid hfATLAS paths found in attribute config.")

    # ==========================================
    # 2. BUILD DIVIDE -> GAGE MAPPING
    # ==========================================
    logging.info(f"Extracting spatial mapping from {path_hf_basins_gpkg}")
    mapping_dfs = []

    if path_hf_basins_gpkg.is_dir():
        # Scenario 1: Subdirectory of individual GPKG files
        logging.info("Directory detected. Scanning for individual gage GPKG files...")
        for gpkg_path in path_hf_basins_gpkg.glob("*.gpkg"):
            match = regex_compiled.search(gpkg_path.name)
            if not match:
                continue
            gage_id = match.group(1)
            
            # Read just the ID and area columns to save RAM
            gdf = gpd.read_file(gpkg_path, layer=divides_layer, columns=[map_divide_id_col], engine="pyogrio")
            gdf[gage_id_col_gpkg] = gage_id
            mapping_dfs.append(pd.DataFrame(gdf.drop(columns='geometry', errors='ignore')))
            
    elif path_hf_basins_gpkg.is_file():
        # Scenario 2: Single consolidated GPKG file
        logging.info("Single file detected. Reading consolidated mapping...")
        gdf = gpd.read_file(path_hf_basins_gpkg, layer=divides_layer, engine="pyogrio")
        if gage_id_col_gpkg not in gdf.columns:
            raise ValueError(f"Consolidated GPKG is missing the required gage ID column: '{gage_id_col_gpkg}'")
        mapping_dfs.append(pd.DataFrame(gdf[[map_divide_id_col, gage_id_col_gpkg]]))
    else:
        raise FileNotFoundError(f"Hydrofabric path is neither a file nor directory: {path_hf_basins_gpkg}")

    df_mapping = pd.concat(mapping_dfs, ignore_index=True).drop_duplicates()
    logging.info(f"Successfully mapped {df_mapping.shape[0]} divides to {df_mapping[gage_id_col_gpkg].nunique()} unique gages.")

    # ==========================================
    # 3. LOAD RAW HFATLAS ATTRIBUTES
    # ==========================================
    unique_divides = df_mapping[map_divide_id_col].unique().tolist()
    logging.info(f"Loading raw hfATLAS attributes for {len(unique_divides)} unique divides...")
    
    # We only need to load the divides that are actually mapped to our gages
    df_raw_attrs = raftsutil.read_hfatlas_wrap_dask(
        paths_hfatl=paths_hfatl, 
        attrs_sel=attrs_sel, 
        map_id_col=hfatl_id_col,
    )
    # Generate the attribute column name mapper to keep track of pint units that get 
    # stripped throughout algo training & prediction
    raw_columns = pd.read_parquet(paths_hfatl[0]).columns
    mapper_df = raftsutil.create_hfatlas_unit_mapper(raw_columns=raw_columns)
    raftsutil.save_hfatlas_unit_mapper(mapper_df=mapper_df, dir_std_base = dir_std_base, ds=ds)

    # Safety rename if the parquet ID column name differs from the hydrofabric ID column name
    if hfatl_id_col != map_divide_id_col and hfatl_id_col in df_raw_attrs.columns:
        df_raw_attrs = df_raw_attrs.rename(columns={hfatl_id_col: map_divide_id_col})

    # ==========================================
    # 4. CLEAN AND UNPACK COMPLEX COLUMNS
    # ==========================================
    logging.info("Unpacking complex struct columns...")
    # Get columns we care about (excluding the ID column)
    data_cols = [c for c in attrs_sel if c in df_raw_attrs.columns]

    for col in data_cols:
        # Unpack PyArrow dictionaries/arrays safely
        if df_raw_attrs[col].dtype == 'object':
            df_raw_attrs[col] = df_raw_attrs[col].apply(
                lambda x: list(x.values())[0] if isinstance(x, dict) else (
                          x[0] if isinstance(x, (list, np.ndarray)) else x)
            )
        # Force numeric, pushing unparseable values to NaN
        df_raw_attrs[col] = pd.to_numeric(df_raw_attrs[col], errors='coerce')

    # ==========================================
    # 5. AGGREGATE
    # ==========================================
    logging.info("Merging mapping and computing aggregations...")
    df_merged = pd.merge(df_mapping, df_raw_attrs, on=map_divide_id_col, how='inner')

    # Build the fallback aggregation dictionary safely
    agg_dict = {
        col: 'mean' 
        for col in data_cols 
        if col not in ['area_sqkm', 'areasqkm'] and col in df_merged.columns
    }
    
    # Identify the area column if it exists for our weighting
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
        
        # Build a new aggregation dictionary using the custom weighted mean function
        wm_agg_dict = {
            col: area_weighted_mean 
            for col in data_cols 
            if col != area_col_name and col in df_merged.columns
        }
        wm_agg_dict[area_col_name] = 'sum'
        
        # Perform the area-weighted aggregation grouped by the gage_id!
        df_aggregated = df_merged.groupby(gage_id_col_gpkg).agg(wm_agg_dict).reset_index()
        logging.info("Area-weighted mean aggregation successful!")
        
    except Exception as e:
        logging.warning(f"Area-weighted mean failed ({e}). Falling back to simple mean.")
        # Perform the fallback aggregation grouped by the gage_id!
        df_aggregated = df_merged.groupby(gage_id_col_gpkg).agg(agg_dict).reset_index()

    logging.info("Reshaping aggregated attributes to RaFTS standard long-format schema...")
    
    # Extract tracking definitions directly from parsed dictionaries
    featureSource = cs.get('featureSource', 'hf_id')
    featureID_format = cs.get('featureID', '{gage_id}')
    
    # Melt from Wide to Long
    df_long = df_aggregated.melt(
        id_vars=[gage_id_col_gpkg], 
        var_name='attribute', 
        value_name='value'
    )
    
    # Rename column to featureID
    df_long = df_long.rename(columns={gage_id_col_gpkg: 'featureID'})
    
    # Apply the featureID_format (e.g'USGS-{gage_id}') to match downstream queries
    df_long['featureID'] = df_long['featureID'].astype(str).apply(lambda gid: featureID_format.format(gage_id=gid))
    
    # Append standard RaFTS tracking columns
    df_long['featureSource'] = featureSource
    df_long['data_source'] = "hfATLAS_aggregated"
    df_long['dl_timestamp'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # For basin-aggregated data, VPU is conceptually 'all'
    df_long['vpuid'] = 'all' 
    
    final_columns = ['vpuid', 'featureID', 'featureSource', 'data_source', 'dl_timestamp', 'attribute', 'value']
    df_long = df_long[final_columns]

    # ==========================================
    # 6. EXPORT DIRECTLY TO ALGORITHM DATABASE
    # ==========================================
    # Format the base attributes directory with the dataset name
    dir_db_attrs_ds = Path(str(dir_db_attrs).format(ds=ds))
    
    # Save into the 'all' VPU subdirectory as expected by rafts_read_attr_comid
    save_dir = dir_db_attrs_ds / 'all'
    save_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = save_dir / "attr_all.parquet"

    # Drop vpuid right before saving, as the directory structure implies the VPU
    df_attr_out = df_long.drop(columns=['vpuid'])
    if arg_val:
        raftsutil.validate_input_attributes(df_attr_out, arg_val=arg_val)
    df_attr_out.to_parquet(out_path, index=False)


    logging.info("Generating standard algorithm points GPKG companion file...")
    
    # Resolve the companion GPKG path based on the response dataset (.nc)
    path_rafts_dat_resp = raftsutil._std_rafts_prep_ds_paths(dir_std_base=dir_std_base, ds=ds, mtch_str='*.nc')
    path_gpkg_rafts_prep = raftsutil._std_rafts_prep_ds_companion_gpkg_path(path_rafts_dat_resp[0])

    path_gpkg_rafts_prep.parent.mkdir(parents=True, exist_ok=True)

    # Execute the requested spatial wrapper
    gdf_hf = raftsutil.generate_algo_points_gpkg_wrap(
        div_ids=df_mapping[map_divide_id_col], 
        path_hf_gpkg=path_hf_basins_gpkg,  # Use the subset basin path parsed earlier
        path_gpkg_rafts_prep=None, 
        hf_layer=hf_layer,
        map_id_col=map_divide_id_col,
        featureSource=featureSource,
        vpu_id_col=vpu_id_col, # epsg = 4326
    )

    if gage_id_col_gpkg in gdf_hf.columns and gage_id_col_gpkg in df_mapping.columns:
        gdf_hf = gdf_hf.drop(columns=[gage_id_col_gpkg])

    # Merge the mapping dataframe to get the real gage_ids back
    gdf_hf = gdf_hf.merge(df_mapping, on=map_divide_id_col, how='inner')
    
    # Overwrite the placeholder columns populated by the wrapper
    gdf_hf['gage_id'] = gdf_hf[gage_id_col_gpkg]
    gdf_hf['featureID'] = gdf_hf[gage_id_col_gpkg]
    gdf_hf['comid'] = gdf_hf[gage_id_col_gpkg]
    
    # Save the corrected companion file
    gdf_hf.to_file(path_gpkg_rafts_prep, driver="GPKG", layer='outlet')
    logging.info(f"Saved corrected GPKG geometry companion to: {path_gpkg_rafts_prep}")

    logging.info(f"✅ Success! Analysis-ready aggregated attributes for {df_aggregated.shape[0]} basins saved to:")
    logging.info(f"   {out_path}")
"""
build_nexus_crosswalk.py

Traverses the hydrofabric flowpath network to map EVERY nexus to all of its 
upstream contributing divides. Writes a RaFTS-compatible crosswalk parquet file 
using the prediction configuration parameters.

Note this script is not recommended for use since crosswalk files should be created
in hfATLAS workflows.

That said, an example use of this script would be:

# 5. Prepare full-domain nexus crosswalk for prediction step 
echo "--> Building full-domain nexus crosswalk..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PREP}/build_nexus_crosswalk.py" "${DIR_CONFIG}/nex_test_pred_config_hf22.yaml" || {
    echo "ERROR: Nexus crosswalk build failed."
    exit 1
}
"""

import argparse
import pandas as pd
import geopandas as gpd
import networkx as nx
from pathlib import Path
import logging
import yaml

import rafts_algo.utils as raftsutil

# Set up standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_nexus_crosswalk(path_pred_config: Path):
    logging.info(f"Parsing prediction configuration: {path_pred_config.name}")
    
    # 1. Parse Pred Config
    with open(path_pred_config, 'r') as f:
        pred_config = yaml.safe_load(f)
        
    # 2. Parse Associated Attr Config to get base variables (dir_std_base, ds, home_dir)
    name_attr_config = pred_config.get('name_attr_config')
    path_attr_config = raftsutil.build_cfig_path(path_pred_config, name_attr_config)
    
    if not path_attr_config or not Path(path_attr_config).exists():
        logging.error(f"Attribute config not found: {path_attr_config}")
        return
        
    attr_cfig = raftsutil.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()
    
    home_dir = raftsutil._define_home_dir(attr_cfig.attr_config)
    datasets = attr_cfig.attrs_cfg_dict.get('datasets', [''])
    ds = datasets[0] if datasets else ''
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base', '')
    
    # Merge variables for f-string path resolution
    resolve_dict = pred_config.copy()
    resolve_dict['home_dir'] = str(home_dir)
    resolve_dict['dir_std_base'] = str(dir_std_base)
    resolve_dict['ds'] = str(ds)
    
    resolved_pred = {}
    for k, v in pred_config.items():
        if isinstance(v, str):
            resolved_pred[k] = raftsutil.resolve_fstrings(v, resolve_dict)
        else:
            resolved_pred[k] = v
            
    # 3. Extract paths from the resolved prediction config
    path_hf_gpkg = Path(resolved_pred.get('path_hf_finl_gpkg'))
    out_parquet_path = resolved_pred.get('path_crosswalk_ids')
    
    if not path_hf_gpkg or not out_parquet_path:
        logging.error("Missing 'path_hf_finl_gpkg' or 'path_crosswalk_ids' in prediction config.")
        return
        
    out_parquet = Path(out_parquet_path)
    
    # Extract optional column definitions with standard NextGen fallback defaults
    fp_layer = resolved_pred.get('hf_fp_layer', 'flowpaths')
    fp_id_col = resolved_pred.get('hf_fp_id_col', 'id')
    fp_toid_col = resolved_pred.get('fp_toid_col', 'toid')
    divide_id_col = resolved_pred.get('map_divide_id_col', 'divide_id')

    # 4. Read the flowpaths layer
    logging.info(f"Reading '{fp_layer}' layer from {path_hf_gpkg}...")
    fp_gdfs = []
    
    if path_hf_gpkg.is_dir():
        for gpkg_file in path_hf_gpkg.glob("*.gpkg"):
            try:
                gdf = gpd.read_file(
                    gpkg_file, 
                    layer=fp_layer, 
                    columns=[divide_id_col, fp_id_col, fp_toid_col], 
                    engine='pyogrio'
                )
                fp_gdfs.append(gdf)
            except Exception as e:
                logging.debug(f"Skipped {gpkg_file.name}: {e}")
    elif path_hf_gpkg.is_file():
        try:
            gdf = gpd.read_file(
                path_hf_gpkg, 
                layer=fp_layer, 
                columns=[divide_id_col, fp_id_col, fp_toid_col], 
                engine='pyogrio'
            )
            fp_gdfs.append(gdf)
        except Exception as e:
            logging.error(f"Failed to read flowpaths. Error: {e}")
            return
    else:
        logging.error(f"Hydrofabric path is neither a file nor directory: {path_hf_gpkg}")
        return
        
    if not fp_gdfs:
        logging.error("No valid flowpaths could be loaded.")
        return

    gdf_fp = pd.concat(fp_gdfs, ignore_index=True)
    gdf_fp = gdf_fp.dropna(subset=[divide_id_col])
    
    logging.info("Building directed network graph...")
    # 5. Build the Directed Graph (water flows from fp_id to fp_toid)
    G = nx.from_pandas_edgelist(
        gdf_fp, 
        source=fp_id_col, 
        target=fp_toid_col, 
        create_using=nx.DiGraph()
    )
    
    # 6. Accumulate Upstream Divides
    logging.info(f"Calculating upstream contributing areas for {len(gdf_fp)} features...")
    crosswalk_records = []
    
    # Create a fast lookup dictionary for flowpath -> divide_id mapping
    fp_to_div = dict(zip(gdf_fp[fp_id_col], gdf_fp[divide_id_col]))
    
    # Identify all unique downstream connections (nexuses)
    unique_nexuses = gdf_fp[fp_toid_col].dropna().unique()
    
    for count, nexus_id in enumerate(unique_nexuses):
        if count % 5000 == 0 and count > 0:
            logging.info(f"Processed {count} / {len(unique_nexuses)} nexuses...")
            
        # Get all ancestors (upstream nodes) for this nexus
        try:
            upstream_fps = nx.ancestors(G, nexus_id)
        except nx.NetworkXError:
            upstream_fps = set()
            
        # The flowpaths immediately terminating at this nexus are direct predecessors
        direct_fps = set(G.predecessors(nexus_id)) if nexus_id in G else set()
        
        all_upstream_fps = upstream_fps.union(direct_fps)
        
        # Map the flowpaths back to their underlying divide_ids
        upstream_divides = {fp_to_div[fp] for fp in all_upstream_fps if fp in fp_to_div}
        
        for div_id in upstream_divides:
            crosswalk_records.append({
                'nexus_id': str(nexus_id),
                'divide_id': str(div_id)
            })

    # 7. Save the Crosswalk
    if crosswalk_records:
        df_crosswalk = pd.DataFrame(crosswalk_records)
        out_parquet.parent.mkdir(parents=True, exist_ok=True)
        df_crosswalk.to_parquet(out_parquet, index=False)
        logging.info(f"Success! Saved crosswalk with {len(df_crosswalk)} mappings to {out_parquet}")
    else:
        logging.warning("No crosswalk records were generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a nexus-to-divide crosswalk from RaFTS prediction config.")
    parser.add_argument("path_pred_config", type=str, help="Path to the YAML prediction configuration file.")
    
    args = parser.parse_args()
    generate_nexus_crosswalk(Path(args.path_pred_config).expanduser())
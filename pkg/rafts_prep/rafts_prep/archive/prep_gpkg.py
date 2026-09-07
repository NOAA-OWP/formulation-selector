# Converted from proc.attr.hydfab R package to python using Gemini3Pro

import logging
import warnings
from pathlib import Path
import os
from typing import List, Union, Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

logger = logging.getLogger(__name__)

def std_path_gpkg_db(dir_db_gpkg: Union[str, Path]) -> Path:
    """
    Standardize the filepath to the large GeoPackage database containing 
    all locations ever acquired when running RaFTS.
    
    Args:
        dir_db_gpkg: The directory of the geopackage database.
        
    Returns:
        Path to the global 'all_locs.gpkg' database.
    """
    dir_db_gpkg = Path(dir_db_gpkg)
    dir_db_gpkg.mkdir(parents=True, exist_ok=True)
    return dir_db_gpkg / "all_locs.gpkg"

def std_write_geom_map_gpkg(
    gdf: gpd.GeoDataFrame, 
    path_save_gpkg: Union[str, Path], 
    epsg: Optional[int] = 4326
) -> gpd.GeoDataFrame:
    """
    Remove duplicates and write comid-geometry mappings to file.
    
    Removes the duplicate item corresponding to the most NA values in a row, 
    but only for duplicated gage_id values. This handles cases where a secondary 
    attempt at grabbing a comid was more successful.
    
    Args:
        gdf: GeoDataFrame of comid/gage_id/geometry mappings.
        path_save_gpkg: The full filepath to write the .gpkg.
        epsg: The EPSG code to use for the CRS. Defaults to 4326.
        
    Returns:
        The cleaned GeoDataFrame written to the file.
    """
    path_save_gpkg = Path(path_save_gpkg)
    
    # Count total NA, pick least-NA rows when duplicates exist
    gdf = gdf.copy()
    gdf['tot_na'] = gdf.isna().sum(axis=1)
    
    # Sort by gage_id and NA count, then drop duplicates keeping the first (lowest NA)
    gdf_clean = gdf.sort_values(by=['gage_id', 'tot_na']).drop_duplicates(subset=['gage_id'], keep='first')
    gdf_clean = gdf_clean.drop(columns=['tot_na'])
    
    # Ensure CRS
    if epsg is not None:
        if gdf_clean.crs is None:
            gdf_clean = gdf_clean.set_crs(epsg=epsg)
        elif gdf_clean.crs.to_epsg() != epsg:
            gdf_clean = gdf_clean.to_crs(epsg=epsg)

    # Write to GeoPackage
    # engine="pyogrio" is faster if installed, but Fiona is the default
    gdf_clean.to_file(path_save_gpkg, driver="GPKG", layer="outlet")
    
    return gdf_clean


def _load_reference_gpkgs(ref_path: Path) -> List[gpd.GeoDataFrame]:
    """Helper to load a single GeoPackage or a directory of GeoPackages."""
    gdfs = []
    if not ref_path.exists():
        logger.warning(f"Reference path does not exist: {ref_path}")
        return gdfs

    if ref_path.is_file() and ref_path.suffix.lower() == ".gpkg":
        try:
            gdfs.append(gpd.read_file(ref_path))
        except Exception as e:
            logger.error(f"Failed to read reference gpkg {ref_path}: {e}")
            
    elif ref_path.is_dir():
        for p in ref_path.rglob("*.gpkg"):
            try:
                gdfs.append(gpd.read_file(p))
            except Exception as e:
                logger.error(f"Failed to read reference gpkg {p}: {e}")
                
    return gdfs


def gen_ds_gpkg(
    dir_db_gpkg: Union[str, Path], 
    path_save_gpkg: Union[str, Path], 
    gage_ids: List[str], 
    epsg: int = 4326,
    reference_gpkg_path: Optional[Union[str, Path]] = None
) -> None:
    """
    Generate dataset GeoPackage from existing databases.
    
    Implements a geopackage database containing all locations ever acquired 
    using RaFTS and copies the relevant gage_id locations over to the dataset's 
    directory. Allows referencing external .gpkg files to harvest locations.
    
    Args:
        dir_db_gpkg: The directory containing the global .gpkg database.
        path_save_gpkg: The path to the dataset-specific .gpkg.
        gage_ids: List of gage_id identifiers to extract.
        epsg: The EPSG code to use for the CRS. Defaults to 4326.
        reference_gpkg_path: Optional. Filepath to a .gpkg or a directory of 
                             .gpkg files to use as an additional data source.
    """
    path_gpkg_all = std_path_gpkg_db(dir_db_gpkg)
    path_save_gpkg = Path(path_save_gpkg)
    
    pool_gdfs = []
    
    # 1. Load global database if it exists
    if path_gpkg_all.exists():
        pool_gdfs.append(gpd.read_file(path_gpkg_all))
        
    # 2. Load custom reference databases if provided
    if reference_gpkg_path is not None:
        pool_gdfs.extend(_load_reference_gpkgs(Path(reference_gpkg_path)))
        
    if not pool_gdfs:
        return  # No existing databases to pull from
        
    # Combine all search pools into one GeoDataFrame
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning) # Ignore pandas concat empty warnings
        gdf_pool = pd.concat(pool_gdfs, ignore_index=True)
        
    if gdf_pool.empty or 'gage_id' not in gdf_pool.columns:
        return
        
    # Subset by requested gage_ids
    gdf_ds = gdf_pool[gdf_pool['gage_id'].isin(gage_ids)]
    
    if gdf_ds.empty:
        return

    # 3. Combine with existing dataset-specific gpkg (if any)
    if path_save_gpkg.exists():
        gdf_existing = gpd.read_file(path_save_gpkg)
        
        # Check column parity (optional, mimics R strictness)
        if set(gdf_existing.columns) != set(gdf_ds.columns):
            logger.warning(f"Column mismatch between existing dataset gpkg and global db. Attempting merge anyway.")
            
        gdf_cmbo = pd.concat([gdf_existing, gdf_ds], ignore_index=True)
    else:
        gdf_cmbo = gdf_ds
        
    # Write cleanly to file
    std_write_geom_map_gpkg(gdf_cmbo, path_save_gpkg, epsg=epsg)


def update_gpkg_db(
    dir_db_gpkg: Union[str, Path], 
    path_save_gpkg: Union[str, Path], 
    epsg: int = 4326
) -> None:
    """
    Update the global geopackage database with the dataset's gpkg.
    
    Takes any additions to the dataset gpkg (after NLDI retrieval) and 
    adds them to the global gpkg database.
    
    Args:
        dir_db_gpkg: The directory containing the .gpkg database.
        path_save_gpkg: The path to the dataset-specific .gpkg containing new locations.
        epsg: The EPSG code to use for the CRS. Defaults to 4326.
    """
    path_save_gpkg = Path(path_save_gpkg)
    path_gpkg_all = std_path_gpkg_db(dir_db_gpkg)
    
    if not path_save_gpkg.exists():
        logger.warning(f"Dataset gpkg does not exist to update global db: {path_save_gpkg}")
        return
        
    gdf_ds = gpd.read_file(path_save_gpkg)
    
    # Enforce CRS
    if gdf_ds.crs is None:
        logger.warning(f"Dataset CRS from {path_save_gpkg} is unspecified. Assuming {epsg}.")
        gdf_ds = gdf_ds.set_crs(epsg=epsg)
    elif gdf_ds.crs.to_epsg() != epsg:
        logger.warning(f"Unexpected CRS in the dataset {gdf_ds.crs.to_epsg()}. Transforming to {epsg}.")
        gdf_ds = gdf_ds.to_crs(epsg=epsg)
        
    if not path_gpkg_all.exists():
        # Create global db for the first time
        std_write_geom_map_gpkg(gdf_ds, path_gpkg_all, epsg=epsg)
    else:
        # Update existing global db
        gdf_all = gpd.read_file(path_gpkg_all)
        
        if set(gdf_all.columns) != set(gdf_ds.columns):
            logger.error("Column names do not match between gpkg databases.")
            raise ValueError("Column names do not match between gpkg databases.")
            
        if gdf_all.crs != gdf_ds.crs:
            logger.error("CRS mismatch between gpkg databases.")
            raise ValueError("CRS mismatch between gpkg databases.")
            
        gdf_cmbo = pd.concat([gdf_all, gdf_ds], ignore_index=True)
        std_write_geom_map_gpkg(gdf_cmbo, path_gpkg_all, epsg=epsg)

def match_pt_to_hf_id(gdf_points, hf_gpkg_path, layer='divides'):
    """Replicates the R match_pt_to_hf_id function."""
    gdf_hf = gpd.read_file(hf_gpkg_path, layer=layer)
    
    # Ensure both are in a projected CRS (e.g., EPSG:5070 for CONUS) for accurate distance calc
    gdf_points = gdf_points.to_crs(epsg=5070)
    gdf_hf = gdf_hf.to_crs(epsg=5070)
    
    # Snap points to the nearest hydrofabric polygon/line
    snapped = gpd.sjoin_nearest(gdf_points, gdf_hf, how="left", distance_col="snap_dist_m")
    
    # Convert back to EPSG:4326
    return snapped.to_crs(epsg=4326)

def match_comids_to_hf(comid_list, hf_gpkg_path):
    """Replicates the R match_comids_to_hf function.
    Crosswalk the NHDPlus COMIDs to hydrofabric IDs

    """
    # Read just the columns we need from the flowpaths layer to save memory
    df_flowpaths = gpd.read_file(hf_gpkg_path, layer='flowpaths', columns=['id', 'comid'], ignore_geometry=True)
    
    df_input = pd.DataFrame({'comid': comid_list})
    # Merge to find the matching hydrofabric IDs
    crosswalked = df_input.merge(df_flowpaths, on='comid', how='inner')
    
    return crosswalked.rename(columns={'id': 'hf_id'})


def crosswalk_to_hf_id(df_missing: pd.DataFrame, hf_gpkg_path: Path, id_col_mapping: str) -> pd.DataFrame:
    """Crosswalks legacy COMIDs to modern hf_ids using the flowpaths layer."""
    logging.info(f"Crosswalking {len(df_missing)} COMIDs to modern hydrofabric IDs...")
    
    # Read only the necessary columns to save memory
    df_flowpaths = gpd.read_file(
        hf_gpkg_path, 
        layer='flowpaths', 
        columns=['id', 'comid'], 
        ignore_geometry=True
    )
    
    # Ensure types match for merging
    df_flowpaths['comid'] = df_flowpaths['comid'].astype(str)
    df_missing[id_col_mapping] = df_missing[id_col_mapping].astype(str)
    
    df_merged = df_missing.merge(df_flowpaths, left_on=id_col_mapping, right_on='comid', how='inner')
    
    missing_count = len(df_missing) - len(df_merged)
    if missing_count > 0:
        logging.warning(f"Could not find hydrofabric crosswalks for {missing_count} COMIDs.")
        
    df_merged['crosswalked_hf_id'] = df_merged['id']
    return df_merged

def get_downstream_point(geom) -> Point:
    """Extracts the hydrologically correct downstream point from a LineString."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == 'LineString':
        return Point(geom.coords[-1])
    elif geom.geom_type == 'MultiLineString':
        return Point(geom.geoms[-1].coords[-1])
    return geom.centroid  # Fallback


def get_centroid(geom) -> Point:
    """Extracts the centroid of a Polygon as a fallback."""
    if geom is None or geom.is_empty:
        return None
    return geom.centroid


def extract_geom(gdf: gpd.GeoDataFrame, layer_type: str) -> gpd.GeoDataFrame:
    """Extracts the correct Point geometry based on the hydrofabric layer type."""
    gdf = gdf.copy()
    if layer_type == 'flowpaths':
        logging.info("Extracting downstream pour points from flowpaths LineStrings...")
        gdf['geom'] = gdf.geometry.apply(get_downstream_point)
    elif layer_type == 'divides':
        logging.warning("Using polygon centroids as fallback for divide outlets.")
        gdf['geom'] = gdf.geometry.apply(get_centroid)
    elif layer_type == 'nexus':
        logging.info("Using raw nexus points.")
        gdf['geom'] = gdf.geometry
    else:
        raise ValueError(f"Unknown layer_type '{layer_type}'. Expected flowpaths, divides, or nexus.")
    
    return gdf.set_geometry('geom')


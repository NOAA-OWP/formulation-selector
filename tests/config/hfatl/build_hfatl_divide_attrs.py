'''
@title: Derive a divide-level hfATLAS attribute fixture for the hfATLAS integration test
@author: Guy Litt <guy.litt@noaa.gov>
@description: The checked-in `integ_test_predictors_x300.parquet` fixture is gage-level
    (one row per USGS gage, keyed by `featureID`), but `rafts_agg_hfatl_basin.py` expects
    raw hfATLAS attributes at the *divide* level so it can area-weight-aggregate them up
    to gages using a hydrofabric GPKG's divide-to-gage mapping. This script derives a
    divide-level fixture by broadcasting each of the 30 gages' attribute rows across its
    child divides in `hfv4_x30.gpkg`, carrying each divide's real `areasqkm` for weighting.
    Note `divide_id` alone is not globally unique in this GPKG (each gage's catchments are
    numbered independently, e.g. every gage has its own 'cat-1'); the unique per-divide key
    is `gageID_divide_id`, matching the convention used in
    `scripts/workflow_configs/00example_configs/clustering_regn_casam_jul26/regn_casam_attr_config.yaml`.
    Run once; the output is checked into `tests/data/`.
@usage:
python build_hfatl_divide_attrs.py
'''
import geopandas as gpd
import pandas as pd
from pathlib import Path

DIR_DATA = Path(__file__).resolve().parents[2] / "data"

if __name__ == "__main__":
    gdf = gpd.read_file(DIR_DATA / "hfv4_x30.gpkg", layer="divides")
    df_divides = pd.DataFrame(gdf[["gageID_divide_id", "gageID", "areasqkm"]])
    df_divides["gage_id"] = df_divides["gageID"].str.replace("USGS-", "", regex=False)

    df_attrs = pd.read_parquet(DIR_DATA / "integ_test_predictors_x300.parquet")
    df_attrs = df_attrs.rename(columns={"featureID": "gage_id"})
    # The gage-level 'area_sqkm' column doesn't apply per-divide; drop it in favor of
    # the divide's own 'areasqkm' from the hydrofabric GPKG used for area weighting.
    df_attrs = df_attrs.drop(columns=["area_sqkm"], errors="ignore")

    df_divide_attrs = pd.merge(df_divides, df_attrs, on="gage_id", how="inner")
    df_divide_attrs = df_divide_attrs.drop(columns=["gageID", "gage_id"])

    path_out = DIR_DATA / "hfv4_x30_divide_attrs.parquet"
    df_divide_attrs.to_parquet(path_out)
    print(f"Wrote {df_divide_attrs.shape[0]} divide-level rows ({df_divide_attrs['gageID_divide_id'].nunique()} unique divides) to {path_out}")

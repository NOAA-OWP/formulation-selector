import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema, Index, Check
from typing import Any, Dict, Optional, List, Tuple
import numpy as np
import re
import yaml
from pathlib import Path
import sys
import os
import rafts_algo.utils as raftsutil

# %% 1. Dynamic Configuration Loading
# When schemas.py is inside the package at pkg/rafts_algo/rafts_algo/schemas/
# REPO_ROOT is 4 levels up from schemas/

REPO_ROOT = Path(__file__).resolve().parents[4] 
# PKG_DATA_DIR: Path to attribute YAML files (e.g., attr_source_types.yml, rafts_attr_menu.yaml)
# Assuming they reside in pkg/proc.attr.hydfab/inst/extdata, relative to REPO_ROOT
PKG_DATA_DIR = REPO_ROOT / "pkg" / "proc.attr.hydfab" / "inst" / "extdata"
# PREP_CONFIG_DIR = Path(__file__).resolve().parent

# Path to YAML files
ATTR_MENU_YML = PKG_DATA_DIR / "rafts_attr_menu.yaml"

# # PREP_CONFIG_YML = PREP_CONFIG_DIR / "xssa_prep_config.yaml"
# prep_config_files = list(PREP_CONFIG_DIR.glob('*_prep_config.yaml'))
# if not prep_config_files:
#     print("Warning: Could not find any *_prep_config.yaml file in the current directory.")
#     PREP_CONFIG_YML = None # Use None if not found
# else:
#     # Use the first matching file found
#     PREP_CONFIG_YML = prep_config_files[0]
#     print(f"Info: Dynamically loaded preparation config from: {PREP_CONFIG_YML.name}")
    
def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        # Fallback or warning if paths are slightly different in dev environment
        print(f"Warning: Config file not found at {path}. Validation strictness may be reduced.")
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f)

# Load contents
attr_menu = load_yaml(ATTR_MENU_YML)
# prep_config = load_yaml(PREP_CONFIG_YML)

# Extract Valid Attributes
valid_attributes = []
if attr_menu:
    for group in attr_menu.values():
        for item in group:
            valid_attributes.extend(item.keys())

# %% 2. Introducing DataFrameSchema for dataframe objects

# --- A. Attribute Data (Input for training/prediction) ---
    # These could be validated further using rafts_attr_menu.yaml and attr_source.type.yaml file
    # Inside the R package, proc.attr.hydfab
    # i.e. *_training.parquet and *_prediction.parquet files. These shouldn't be nullable, but the code removes missing values.
schema_df_attr = DataFrameSchema({
        "featureID": Column(pa.Object, nullable=True),  # featureID can be int (comid) or str (gage_id/custom)
        "featureSource": Column(str,checks=pa.Check.isin(["COMID", "custom_hfuid","comid","hf_id","custom_hfuid", "hfuid","hfa_id","hfv22_id","hfv30_id","hfv31_id"]),nullable=True),
        "data_source": Column(str,nullable=True), # Do not perform checks on data source because there are infinite possibilities when running custom transforms
        "dl_timestamp": Column(pa.DateTime,nullable=True, required = False),
        "attribute": Column(str, nullable=True), # There are infinite possibilities with custom tfrm, so do not perform checks=pa.Check.isin(valid_attributes)
        "value": Column(float,nullable=True),
    },
    # we may refrain from enforcing a specific named index here to allow for flexibility in resetting index.
    coerce=True,
    strict=True, # For now, it is True, but set to False to allow extra columns (like internal IDs) if necessary
    name="DFAttr"
)


# --- B. Spatial/Geometry Data ---
coordinate_regex = r"[\+\-]?\d+(\.\d*)?([eE][\+\-]?\d+)?"
wkt_point_pattern = rf"^POINT\s*\({coordinate_regex}\s+{coordinate_regex}\)$" 

# Define a custom check for Shapely Point objects
def is_point(series):
    # Check if the geometry type of every item is 'Point'
    return series.map(lambda geom: geom.geom_type == "Point")



schema_gdf_comid = DataFrameSchema({
        #'sourceName': Column(str, nullable=True),
        'comid': Column(pa.Object, nullable=True),
        'measure': Column(float, nullable=True, required = False),
        'reachcode': Column(pa.Object, nullable=True, required = False), # Assuming reachcode might be string (like '01010003000003')
        'name': Column(str, nullable=True, required = False),
        'X': Column(float, nullable=True),
        'Y': Column(float, nullable=True),
        'gage_id': Column(pa.Object, nullable=False), # A fundamental location identifier
        'tot_na': Column(int, nullable=False), 
        'geometry': Column(
            "geometry",  # Do not force to 'str'
            checks=pa.Check(is_point, error="Geometries must be Points"),
            nullable=False
        ),#Column(str, checks=pa.Check.str_matches(wkt_point_pattern), nullable=False), # The point geometry corresponding to the location identifier
        'featureID': Column(pa.Object, nullable=False), # Allows str or int
        'featureSource': Column(str, checks=pa.Check.isin(["COMID", "nwissite","comid","hf_id","custom_hfuid", "hfuid","hfa_id","hfv22_id","hfv30_id","hfv31_id"] ), nullable=False),
    },
    # Keep strict=False to allow for any future unlisted columns added by geopandas/raftsutil
    coerce=True,
    strict=False, 
    name="gageid_location_mapper_gdf"
)

# --- C. Training Evaluation Results ---
def build_schema_rslt_eval_df(valid_metrics: List[str]) -> pa.DataFrameSchema:
    return pa.DataFrameSchema({
        "algorithm": Column(pa.String,checks=Check.isin(["rf", "mlp"]),nullable=False),
        "type": Column(pa.String,nullable=False),
        "metric": Column(pa.String, checks=Check.isin(valid_metrics), nullable=False),
        "mse": Column(pa.Float,nullable=False),
        "r2": Column(pa.Float,nullable=False),
        "dataset": Column(pa.String,nullable=False),
        "file_pipe": Column(pa.String,checks=Check.str_matches(r".+\.joblib$"),nullable=False),
        "algo": Column(pa.String,checks=Check.isin(["rf", "mlp"]),nullable=False),
    },
    coerce=True,strict=False,name="RsltEvalDF"
)

# --- F. Selected Attributes Schema ---
schema_attrs_sel = DataFrameSchema({
        0: Column(pa.String,nullable=False),
        },
   coerce=True,strict=False,name="AttrsSelDF"
)

# --- E. Response Data (Targets) ---
# Creating schema for dat_resp
def build_schema_dat_resp(valid_metrics: List[str]) -> pa.DataFrameSchema:
    schema_columns_dat_resp = {
        "gage_id": Column(pa.Object, nullable=False), 
        "featureID": Column(pa.Object, nullable=False),
        "featureSource": Column(str, nullable=False),
    }
    for metric in valid_metrics:
        schema_columns_dat_resp[metric] = Column(float, nullable=True) 
    return pa.DataFrameSchema(schema_columns_dat_resp, coerce=True, strict=False, name="DatResp")

# --- F. Prediction Output Schema ---
def build_schema_df_pred(
    valid_metrics: List[str],
    uncertainty_cols: List[str] = [], 
    mapie_alphas: List[float] = []
) -> pa.DataFrameSchema:
    """
    Constructs the schema for the final prediction output parquet.
    """
    
    schema_dict = {
        "featureID": Column(pa.Object, nullable=False),
        "featureSource": Column(str, nullable=False),
        "prediction": Column(float, nullable=False),
        "resp_var": Column(str, checks=Check.isin(valid_metrics) if valid_metrics else None, nullable=False),
        "dataset": Column(str, nullable=False),
        "algo": Column(str, nullable=False),
        "name_algo": Column(str, nullable=False),
    }

    # Add forestci if present
    if "forestci" in uncertainty_cols:
         schema_dict["forestci"] = Column(float, nullable=True)

    # Add MAPIE columns dynamically
    if mapie_alphas:
        for alpha in mapie_alphas:
            alpha_str = f"{alpha:.2f}" 
            schema_dict[f'mapie_lower_{alpha_str}'] = Column(float, nullable=True)
            schema_dict[f'mapie_upper_{alpha_str}'] = Column(float, nullable=True)

    return pa.DataFrameSchema(
        schema_dict,
        index=pa.Index(pa.Int), 
        coerce=True,
        strict=False,
        name="DFPred"
    )

 #%% Schemas for rafts_tfrm_attrs.py
schema_df_comids = DataFrameSchema({
        "featureID": Column(pa.Object, nullable=False),  # accepts int or str
        "featureSource": Column(str,checks=pa.Check.isin(["COMID", "custom_hfuid"]),nullable=False),
        "data_source": Column(str,nullable=False),# Do not perform checks on data source because there are infinite possibilities when running custom transforms
        "dl_timestamp": Column(pa.DateTime,nullable=False),
        "attribute": Column(str, nullable=False), # There are infinite possibilities with custom transforms, so do not perform checks=pa.Check.isin(valid_attributes)
        "value": Column(float,nullable=False),
        "gage_id": Column(pa.Object,nullable=False),
    }
    ,coerce=True,strict=False,name="DFComids"
)

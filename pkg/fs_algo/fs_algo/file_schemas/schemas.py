import pandera.pandas as pa
from pandera import Column, DataFrameSchema, Index, Check
#from typing import Any, Dict, Optional, Tuple
import numpy as np
#import re
import yaml
from pathlib import Path

# %% Get data_source values
# Path to YAML files
root_dir = Path(__file__).resolve().parents[3]

attr_source_yml_path = root_dir / "proc.attr.hydfab" / "inst" / "extdata" / "attr_source_types.yml"
attr_menu_path = root_dir / "proc.attr.hydfab" / "inst" / "extdata" / "fs_attr_menu.yaml"

# Extract attribute sources
with open(attr_source_yml_path, "r") as f:
    raw_sources = yaml.safe_load(f)

data_source_values = [
    d.get("internal_dataset_name")
    for v in raw_sources.values()
    for d in v if isinstance(d, dict) and "internal_dataset_name" in d
]
data_source_values = [v for v in data_source_values if v]  # Remove None


# Eaxtract valid attributes
with open(attr_menu_path, "r") as f:
    attr_menu = yaml.safe_load(f)

valid_attributes = []
for group in attr_menu.values():
    for item in group:
        valid_attributes.extend(item.keys())


# Extract metrics from xssa_prep_config.yaml
root_dir_prep = Path(__file__).resolve().parents[4]
prep_config_path = root_dir_prep / "scripts" / "eval_ingest" / "xssa" / "xssa_prep_config.yaml"

with open(prep_config_path, "r") as f:
    prep_config = yaml.safe_load(f)

col_schema = prep_config["col_schema"]

# Extract the 'metric_mappings' value
metric_mappings_str = None
for item in col_schema:
    if isinstance(item, dict) and "metric_mappings" in item:
        metric_mappings_str = item["metric_mappings"]
        break
valid_metrics = metric_mappings_str.split("|")

    # %% Introducing DataFrameSchema for dataframe objects
    # These could be validated further using fs_attr_menu.yaml and attr_source.type.yaml file
    # Inside the R package, proc.attr.hydfab
schema_df_attr = DataFrameSchema({
        "featureID": Column(pa.Object, nullable=False),  # accepts int or str
        "featureSource": Column(str,checks=pa.Check.isin(["COMID", "custom_hfuid"]),nullable=False),
        "data_source": Column(str,checks=pa.Check.isin(data_source_values),nullable=False),
        # "data_source": Column(str,checks=pa.Check.isin(["hydroatlas__v1", "usgs_nhdplus__v2"]),nullable=False),
        "dl_timestamp": Column(pa.DateTime,nullable=False),
        "attribute": Column(str, checks=pa.Check.isin(valid_attributes), nullable=False),
        "value": Column(float,nullable=False),
    },
    index=Index(int, name=None),coerce=True,strict=True,name="DFAttr"
)


wkt_point_pattern = r"^POINT\s*\(\-?\d+(\.\d+)?\s+\-?\d+(\.\d+)?\)$"    
schema_gdf_comid = DataFrameSchema({
        "comid": Column(int, nullable=False),
        "gage_id": Column(int, nullable=False),
        "geometry": Column(str,checks=pa.Check.str_matches(wkt_point_pattern),nullable=False)
    },
    index=Index(int),coerce=True,strict=True,name="GDFComid"
)


schema_rslt_eval_df = pa.DataFrameSchema({
        "algorithm": Column(pa.String,checks=Check.isin(["rf", "mlp"]),nullable=False),
        "type": Column(pa.String,checks=Check.isin(["random forest regressor", "multi-layer perceptron regressor"]),nullable=False),
        "metric": Column(pa.String, checks=Check.isin(valid_metrics), nullable=False),
        "mse": Column(pa.Float,nullable=False),
        "r2": Column(pa.Float,nullable=False),
        "dataset": Column(pa.String,nullable=False),
        "file_pipe": Column(pa.String,checks=Check.str_matches(r".+\.joblib$"),nullable=False),
        "algo": Column(pa.String,checks=Check.isin(["rf", "mlp"]),nullable=False),
    },
    index=pa.Index(pa.Int),coerce=True,strict=True,name="RsltEvalDF"
)

schema_attrs_sel = DataFrameSchema({
        0: Column(pa.String,nullable=False),
        },
    index=pa.Index(pa.Int),coerce=True,strict=True,name="AttrsSelDF"
)

# Creating schema for dat_resp
schema_columns_dat_resp = {
    "basin_name": Column(str, nullable=False),
    "gage_id": Column(int, nullable=False),
    "comid": Column(int, nullable=False),
}
for metric in valid_metrics:
    schema_columns_dat_resp[metric] = Column(float, nullable=False)
schema_dat_resp = pa.DataFrameSchema(schema_columns_dat_resp)


def build_schema_df_pred(schema_df_pred_dict):
    return pa.DataFrameSchema(
        schema_df_pred_dict,
        index=pa.Index(pa.Int),
        coerce=True,
        strict=True,
        name="DFPred"
    )

 #%% Schemas for fs_tfrm_attrs.py
schema_df_comids = DataFrameSchema({
        "featureID": Column(pa.Object, nullable=False),  # accepts int or str
        "featureSource": Column(str,checks=pa.Check.isin(["COMID", "custom_hfuid"]),nullable=False),
        "data_source": Column(str,checks=pa.Check.isin(data_source_values),nullable=False),
        "dl_timestamp": Column(pa.DateTime,nullable=False),
        "attribute": Column(str, checks=pa.Check.isin(valid_attributes), nullable=False),
        "value": Column(float,nullable=False),
        "gage_id": Column(int,nullable=False),
    },
    index=Index(int, name=None),coerce=True,strict=True,name="DFComids"
)


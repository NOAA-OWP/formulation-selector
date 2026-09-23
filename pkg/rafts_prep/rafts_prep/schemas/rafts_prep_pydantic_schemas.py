from pydantic import BaseModel, Field, model_validator, AliasChoices
from typing import List, Optional, Any, Dict

def flatten_yaml_list(v: Any) -> dict:
    """Flatten the list-of-single-key-dicts structure used throughout the
    RaFTS YAML configs (e.g. ``file_io``, ``col_schema``, ``references``)
    into a single flat dict.

    :param v: The raw value from the parsed YAML. If it is a list where
        every item is a dict, each item's key(s)/value(s) are merged into
        one flat dict. Any other type (already a dict, a scalar, etc.) is
        returned unchanged.
    :type v: Any
    :return: The flattened dict, or `v` unchanged if it wasn't a
        list-of-dicts.
    :rtype: dict
    """
    if isinstance(v, list) and all(isinstance(i, dict) for i in v):
        return {k: val for d in v for k, val in d.items()}
    return v

class FileIOConfig(BaseModel):
    # Required parameters based on config and README
    dir_save: str
    save_type: str
    save_loc: str
    path_data: str

    # Optional parameters
    home_dir: str = "~"
    # hfATLAS-only: the GPKG containing hfATLAS divides, required for mapping
    # divide_id to the standardized featureID/featureSource (see
    # rafts_agg_hfatl_basin.py). The Legacy NLDI/xSSA workflow never defines
    # this key (see CLAUDE.md section 3), so it must not be required here --
    # scripts that actually need it (e.g. rafts_agg_hfatl_basin.py) already
    # fail with a clear error when it's missing.
    path_hf_gpkg: Optional[str] = None
    data_source: Optional[str] = None
    dir_base: Optional[str] = None
    dir_std_base: Optional[str] = None
    dir_db_attrs: Optional[str] = None
    path_hf_basins_gpkg: Optional[str] = None
    gage_id_col_gpkg: Optional[str] = None
    gpkg_filename_pattern: Optional[str] = None
    hfatl_id_format: Optional[str] = None
    vpu_mapped: Optional[str] = None
    hf_fp_layer: Optional[str] = None
    hf_fp_id_col: Optional[str] = None
    vpu_id_col: Optional[str] = None
    dataset_name: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def check_legacy_reqs(cls, values):
        flat_vals = flatten_yaml_list(values)
        req_file_io = ['dir_save', 'save_type', 'save_loc']
        if not all(x in flat_vals for x in req_file_io):
            # Corrected legacy typo that previously mislabeled this as formulation_metadata
            raise ValueError(f"The input config file expects the following defined under 'file_io': {', '.join(req_file_io)}")
        return flat_vals

class ColSchemaConfig(BaseModel):
    gage_id: str
    featureID: str
    featureSource: str
    respvar_cols: str
    val_respvar: str = 'False'
    respvar_mappings: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def check_reqs(cls, values):
        flat_vals = flatten_yaml_list(values)
        req_col_schema = ['gage_id', 'respvar_cols']
        if not all(x in flat_vals for x in req_col_schema):
            raise ValueError(
                f"The input config file expects the following defined under 'col_schema': {', '.join(req_col_schema)}"
            )
        return flat_vals

    @model_validator(mode='after')
    def set_or_validate_mappings(self) -> 'ColSchemaConfig':
        # Safely evaluate the boolean intent of the string
        is_validating = str(self.val_respvar).strip().lower() == 'true'

        if is_validating and not self.respvar_mappings:
            raise ValueError(
                "When 'val_respvar' is True, 'respvar_mappings' must be explicitly provided "
                "to map response variables to standardized formats."
            )
        
        # Apply the default inheritance when validation is bypassed
        if not is_validating and not self.respvar_mappings:
            self.respvar_mappings = self.respvar_cols

        return self

class FormulationMetadata(BaseModel):
    # Required parameters
    dataset_name: str
    formulation_base: str
    target_var: str
    start_date: str
    end_date: str
    cal_status: str

    # Optional parameters
    datasets: Optional[List[str]] = None
    formulation_id: Optional[str] = None
    formulation_ver: Optional[str] = None
    temporal_res: Optional[str] = None
    modeled_notes: Optional[str] = None
    start_date_cal: Optional[str] = None
    end_date_cal: Optional[str] = None
    cal_notes: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def check_legacy_reqs(cls, values):
        flat_vals = flatten_yaml_list(values)
        req_form_meta = ['dataset_name', 'formulation_base', 'target_var', 'start_date', 'end_date', 'cal_status']
        if not all(x in flat_vals for x in req_form_meta):
            raise ValueError(f"The input config file expects the following defined under 'formulation_metadata': {', '.join(req_form_meta)}")
        return flat_vals

class PrepConfig(BaseModel):
    col_schema: ColSchemaConfig
    file_io: FileIOConfig
    formulation_metadata: FormulationMetadata
    references: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def check_std_keys(cls, values):
        std_keys = ['file_io', 'col_schema', 'formulation_metadata', 'references']
        if any(key not in std_keys for key in values.keys()):
            raise ValueError(f"Provided keys in the input config file: {dict(values).keys()} do not match the standard keys: {std_keys}")
        # Unlike col_schema/file_io/formulation_metadata, references has no
        # dedicated sub-model to flatten its list-of-single-key-dicts YAML
        # shape internally, so it must be flattened here -- otherwise it
        # reaches read_schm_ls_of_dict() as a raw list and produces one
        # DataFrame row per reference entry instead of one flattened row
        # (corrupting the single-row contract for every other column).
        if 'references' in values:
            values['references'] = flatten_yaml_list(values['references'])
        return values

class AttrSelectConfig(BaseModel):
    hfatl_id_col: str
    paths_hfatl: List[str]
    hfatl_vars: List[str]

    @model_validator(mode='before')
    @classmethod
    def flatten(cls, values):
        return flatten_yaml_list(values)

class AttrConfig(BaseModel):
    col_schema: Optional[ColSchemaConfig] = None
    file_io: FileIOConfig
    formulation_metadata: FormulationMetadata
    attr_select: AttrSelectConfig
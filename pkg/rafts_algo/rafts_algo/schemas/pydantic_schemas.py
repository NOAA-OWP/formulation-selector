from typing import Any, Dict, Optional, Tuple, List, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import numpy as np
import re

# %% ML Configuration Validation

class AlgoConfig(BaseModel):
    """Validates the algorithm training configuration YAML (algo_config).

    :param task_type: Either 'regression' or 'clustering'; selects which
        algorithms/evaluation columns are applicable. Defaults to 'regression'.
    :type task_type: str
    :param algorithms: The algorithms to train, keyed by name (e.g. 'rf',
        'mlp', 'kmeans'), with each value being that algorithm's own
        parameter dict as read from the YAML.
    :type algorithms: Dict[str, Any]
    :param test_size: Proportion of the dataset held out for testing, passed
        to :func:`sklearn.model_selection.train_test_split`. Defaults to 0.3.
    :type test_size: float
    :param seed: Random seed for reproducibility. Defaults to 32.
    :type seed: int
    :param name_attr_config: Name of the linked attribute config file,
        expected in the same directory as this algo config.
    :type name_attr_config: str
    :param name_attr_csv: Optional name of a .csv file defining the
        attributes to use for training, in lieu of the attribute config's
        own selection. Defaults to None.
    :type name_attr_csv: Optional[str]
    :param colname_attr_csv: Column name inside `name_attr_csv` holding the
        attribute names; required if `name_attr_csv` is set. Defaults to None.
    :type colname_attr_csv: Optional[str]
    :param verbose: Whether the train/test/eval steps should print progress.
        Defaults to True.
    :type verbose: bool
    :param read_type: 'all' or 'filename'; controls how attribute Parquet
        files are read (see CLAUDE.md's hfATLAS vs. legacy NLDI workflows).
        Defaults to 'all'.
    :type read_type: str
    :param make_plots: Whether to create and save diagnostic plots. Defaults
        to False.
    :type make_plots: bool
    :param same_test_ids: Whether all datasets being compared should share
        the same held-out test IDs. Defaults to True.
    :type same_test_ids: bool
    :param metrics: Response variable/metric names to process; if None, all
        metrics in the input dataset are processed. Defaults to None.
    :type metrics: Optional[List[str]]
    :param uncertainty: Uncertainty quantification configuration (forestci,
        bagging, and/or MAPIE blocks). Defaults to None.
    :type uncertainty: Optional[Dict[str, Any]]
    :param n_jobs: Number of parallel jobs for GridSearchCV. Defaults to 1.
    :type n_jobs: Optional[int]
    :param save_all_clusters: For clustering algorithms, whether to save
        every candidate cluster count rather than only the best. Defaults
        to False.
    :type save_all_clusters: bool
    """
    task_type: str = 'regression'
    algorithms: Dict[str, Any]
    test_size: float = 0.3
    seed: int = 32
    name_attr_config: str
    name_attr_csv: Optional[str] = None
    colname_attr_csv: Optional[str] = None
    verbose: bool = True
    read_type: str = 'all'
    make_plots: bool = False
    same_test_ids: bool = True
    metrics: Optional[List[str]] = None
    uncertainty: Optional[Dict[str, Any]] = None
    n_jobs: Optional[int] = 1
    save_all_clusters: bool = False

class PredConfig(BaseModel):
    """Validates the out-of-sample prediction configuration YAML (pred_config).

    :param name_attr_config: Name of the linked attribute config file.
    :type name_attr_config: str
    :param name_algo_config: Name of the linked algorithm config file.
    :type name_algo_config: str
    :param ds_type: Dataset type label used in output filenames. Defaults to
        'prediction'.
    :type ds_type: str
    :param write_type: Output file format ('parquet' or 'csv'). Defaults to
        'parquet'.
    :type write_type: str
    :param path_meta: Path to the metadata/predictor file (or directory)
        defining the prediction locations.
    :type path_meta: str
    :param pred_file_comid_colname: Column name identifying locations inside
        `path_meta`.
    :type pred_file_comid_colname: str
    :param path_gpkg_pred: Optional path to a GeoPackage of prediction
        locations. Defaults to None.
    :type path_gpkg_pred: Optional[str]
    :param pred_gpkg_lyr: Layer name inside `path_gpkg_pred`. Defaults to None.
    :type pred_gpkg_lyr: Optional[str]
    :param pred_gpkg_id_col: Identifier column inside `path_gpkg_pred`.
        Defaults to None.
    :type pred_gpkg_id_col: Optional[str]
    :param path_crosswalk_ids: Optional path to a Parquet file crosswalking
        aggregated identifiers (e.g. huc12) to the standard identifier (e.g.
        divide_id). Defaults to None.
    :type path_crosswalk_ids: Optional[str]
    :param crosswalk_target_col: The standardized identifier column name in
        `path_crosswalk_ids` (e.g. 'divide_id'). Only needed when performing
        a crosswalk/aggregation. Defaults to None.
    :type crosswalk_target_col: Optional[str]
    :param path_hf_finl_gpkg: Path to the hydrofabric GPKG containing the
        divides referenced by `path_crosswalk_ids`; required when running
        rafts_regn_params_gpkg.py. Defaults to None.
    :type path_hf_finl_gpkg: Optional[str]
    :param layr_hf_finl_gpkg: Layer to read from `path_hf_finl_gpkg`.
        Defaults to 'divides'.
    :type layr_hf_finl_gpkg: str
    :param overwrite_sql: Whether to overwrite an existing table when writing
        to the regionalization SQLite/GeoPackage. Defaults to False.
    :type overwrite_sql: bool
    :param algo_response_vars: Response variable/metric names to predict.
        Defaults to None.
    :type algo_response_vars: Optional[List[str]]
    :param algo_type: Base algorithm names to predict with (e.g. 'rf',
        'kmeans'). Defaults to None.
    :type algo_type: Optional[List[str]]
    :param algo_select: The specific trained algorithm name (e.g.
        'gower_agglomerative_k4') used for the final regionalization GPKG
        layer. Defaults to None.
    :type algo_select: Optional[str]
    :param mapie_alpha: Alpha values for MAPIE prediction interval
        estimation, read from the YAML's 'MAPIE_alpha' key. Defaults to None.
    :type mapie_alpha: Optional[List[float]]
    :param uncn_bnd_pred: Whether to apply min/max physical bounds to
        predictions. Defaults to False.
    :type uncn_bnd_pred: bool
    :param hf_fp_layer: Flowpath layer name, used by nexus mapping scripts.
        Defaults to 'flowpaths'.
    :type hf_fp_layer: str
    :param hf_fp_id_col: Flowpath identifier column name. Defaults to 'id'.
    :type hf_fp_id_col: str
    :param fp_toid_col: Flowpath downstream-id column name. Defaults to
        'toid'.
    :type fp_toid_col: str
    :param map_divide_id_col: Divide identifier column name. Defaults to
        'divide_id'.
    :type map_divide_id_col: str
    """
    name_attr_config: str
    name_algo_config: str
    ds_type: str = 'prediction'
    write_type: str = 'parquet'
    path_meta: str
    pred_file_comid_colname: str

    # Optional prediction and routing parameters
    path_gpkg_pred: Optional[str] = None
    pred_gpkg_lyr: Optional[str] = None
    pred_gpkg_id_col: Optional[str] = None
    path_crosswalk_ids: Optional[str] = None
    crosswalk_target_col: Optional[str] = None
    path_hf_finl_gpkg: Optional[str] = None
    layr_hf_finl_gpkg: str = 'divides'
    overwrite_sql: bool = False
    algo_response_vars: Optional[List[str]] = None
    algo_type: Optional[List[str]] = None
    algo_select: Optional[str] = None
    # Field name is snake_case per convention; 'MAPIE_alpha' is kept as the
    # validation alias since that's the YAML key every existing config uses.
    mapie_alpha: Optional[List[float]] = Field(default=None, alias='MAPIE_alpha')
    uncn_bnd_pred: bool = False

    # Topology and Flowpath Mappings (for nexus mapping scripts)
    hf_fp_layer: str = 'flowpaths'
    hf_fp_id_col: str = 'id'
    fp_toid_col: str = 'toid'
    map_divide_id_col: str = 'divide_id'

# %% Pydantic model pipeline validation 

class UncertaintyConfig(BaseModel):
    """
    Validates the dictionary structure of the 'Uncertainty' key 
    saved within the model joblib file.
    """
    # ForestCI keys usually follow pattern ci_95, ci_90 etc.
    forestci: Optional[Dict[str, Dict[str, Any]]] = None
    
    # Bagging keys
    bagging_confidence_interval: Optional[Dict[str, Any]] = None
    
    # MAPIE specific configurations if saved in config dict
    mapie: Optional[List[Dict[str, Any]]] = None
    
class ModelMetadata(BaseModel):
    """
    Validates the top-level dictionary loaded from the .joblib file
    in rafts_pred_algo_new.py.
    """
    pipeline: Any #BaseEstimator # Should be a sklearn object (e.g. pipeline, model_selection )
    X_train_shape: Optional[Tuple[int, int]] # Required for ForestCI
    mapie: Optional[Any] = None #Optional[MapieRegressor] = None # The MAPIE regressor object (not just config)
    Uncertainty: Optional[Dict[str, Any]] = None # The uncertainty configuration dict

    @field_validator("X_train_shape")
    def validate_shape(cls, v):
        if v is None:
            return v
        if not (isinstance(v, tuple) and len(v) == 2 and all(isinstance(i, int) for i in v)):
            raise ValueError("X_train_shape must be a tuple of two integers (n_samples, n_features)")
        return v

    @model_validator(mode="after")
    def validate_uncertainty(self) -> "ModelMetadata":
        """
        Deep validation of the Uncertainty dictionary if it exists.
        """
        unc = self.Uncertainty 
        if unc is None:
            return self

        # forestci block
        if "forestci" in unc:
            forestci = unc["forestci"]
            pattern = r"^ci_(\d{1,2}|[1-9][0-9])$"
            matched = [k for k in forestci if re.match(pattern, k)]
            if not matched:
                raise ValueError("forestci must contain at least one 'ci_zz' with zz between 1 and 99")
            for k in matched:
                ci = forestci[k]
                for bound in ["upper_bound", "lower_bound"]:
                    arr = ci.get(bound)
                    if not (isinstance(arr, np.ndarray) and np.issubdtype(arr.dtype, np.floating)):
                        raise ValueError(f"forestci -> {k} -> {bound} must be a NumPy array of floats")

        # bagging_confidence_interval block
        if "bagging_confidence_interval" in unc:
            for key in ["bagging_std_pred", "bagging_mean_pred"]:
                arr = unc.get(key)
                if not (isinstance(arr, np.ndarray) and np.issubdtype(arr.dtype, np.floating)):
                    raise ValueError(f"{key} must be a NumPy array of floats")

            confs = unc.get("bagging_confidence_intervals", {})
            pattern = r"^confidence_level_(\d{1,2}|[1-9][0-9])$"
            matched = [k for k in confs if re.match(pattern, k)]
            if not matched:
                raise ValueError("bagging_confidence_intervals must contain keys like 'confidence_level_zz'")

            for k in matched:
                for bound in ["upper_bound", "lower_bound"]:
                    arr = confs[k].get(bound)
                    if not (isinstance(arr, np.ndarray) and np.issubdtype(arr.dtype, np.floating)):
                        raise ValueError(f"bagging_confidence_intervals -> {k} -> {bound} must be a NumPy array of floats")

        return self
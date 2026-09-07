
from typing import Any, Dict, Optional, Tuple, List, Union
from pydantic import BaseModel, field_validator, model_validator
import numpy as np
import re
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
    mapie: Optional[Any] = None#Optional[MapieRegressor] = None # The MAPIE regressor object (not just config)
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
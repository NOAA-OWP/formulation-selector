
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, field_validator, model_validator
import numpy as np
import re

    # %% Pydantic model pipeline validation 

class ModelMetadata(BaseModel):
    pipeline: Any
    mapie: Any
    X_train_shape: Tuple[int, int]
    Uncertainty: Optional[Dict[str, Any]] = None

    @field_validator("X_train_shape")
    def validate_shape(cls, v):
        if not (isinstance(v, tuple) and len(v) == 2 and all(isinstance(i, int) for i in v)):
            raise ValueError("X_train_shape must be a tuple of two integers")
        return v

    @model_validator(mode="after")
    def validate_uncertainty(cls, values):
        unc = values.Uncertainty
        if unc is None:
            return values

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

        return values

# Background
Integration tests for the data processing pipeline across the RaFTS modeling framework.

The test suite covers three pathways:
1. **Legacy NLDI/CAMELS Workflow** (`test_rafts_prep_to_pred.py`, `test_rafts_tfrm_attrs.py`): Tests the `rafts_prep`, R-based `proc.attr.hydfab`, and `rafts_algo` packages.
2. **hfATLAS Full Workflow** (`test_rafts_hfatl_full_workflow.py`): A pure-Python pipeline leveraging `rafts_prep` and `rafts_algo` to perform hydrofabric attribute aggregation, model training, dynamic prediction, donor-receiver pairing, parameter regionalization, and mapping.
3. **hfATLAS Prep-to-Map Workflow** (`test_rafts_hfatl_prep_to_map.py`): A self-contained hfATLAS test that generates its own synthetic data and configs in a temp directory at run time; no external data download is required.

## Test data sources

Two different data-provisioning approaches are in use, depending on the test:

* **`test_rafts_hfatl_full_workflow.py`** is self-contained: all the data it needs (`hfv4_x30.gpkg`, `hfv4_x30_divide_attrs.parquet`, `integ_test_predictors_x300.parquet`, `rapid_test_9_locs_v4.gpkg`, `jul26_cal_hf4_predictors_9locations_final.parquet`) already lives in `tests/data/` and is used directly via the relative paths inside `tests/config/hfatl/hfatl_*.yaml`. No download is required to run it. (`hfv4_x30_divide_attrs.parquet` is a derived fixture; see `tests/config/hfatl/build_hfatl_divide_attrs.py` for how it's generated from the other two hfv4_x30 files.)
* **`test_rafts_prep_to_pred.py` and `test_rafts_tfrm_attrs.py`** (the legacy xSSA/CAMELS workflow) instead require the `testdata_20250901.zip` bundle described below.
* **`test_rafts_hfatl_prep_to_map.py`** generates its own synthetic data and configs at run time in a temp directory; it needs neither `tests/data/` nor the zip bundle.

# Steps for running the RaFTS integration tests

### 1. Download and Extract Test Data (only needed for the legacy xSSA/CAMELS tests)
Those with access to the NOAA Google Drive may download the integration test input data (`testdata_20250901.zip`) from the following link:
[https://drive.google.com/drive/folders/1JDtJKSfbmtBBp1nkBdNMwzS_EvFYkvpC?usp=drive_link](https://drive.google.com/drive/folders/1JDtJKSfbmtBBp1nkBdNMwzS_EvFYkvpC?usp=drive_link)

Extract the contents into the `tests/data/testdata_20250901/` directory so that the relative paths inside the test configuration files (e.g., `../../data/...`) resolve correctly. If you extract the data elsewhere, you must manually update the `file_io` section within the `tests/config/xssa/` YAML files.

### 2. Run the Tests via `uv`
RaFTS manages its Python environment and dependencies via `uv` centered in the `pkg/` directory. All testing commands should be executed from within `pkg/` to ensure the correct virtual environment is utilized.

Navigate to the package directory:
```bash
cd path/to/git/rafts/pkg/
```

**To run the entire integration test suite:**

```bash
uv run pytest ../tests/
```

**To run specific workflows independently:**

* **hfATLAS Full Workflow (7 Steps):**
Tests hydrofabric attribute aggregation, parallelized algorithm training, dynamic prediction, donor-receiver pairing, parameter regionalization (SQLite/GPKG), and map generation. Uses the self-contained fixtures in `tests/data/` described above; no download needed.
```bash
uv run pytest ../tests/test_rafts_hfatl_full_workflow.py -v
```

* **hfATLAS Prep-to-Map Workflow (4 Steps):**
Self-contained hfATLAS test using synthetic data generated at run time.
```bash
uv run pytest ../tests/test_rafts_hfatl_prep_to_map.py -v
```

* **Legacy xSSA Workflow (4 Steps):**
Tests the core workflow utilizing NLDI feature metadata and `proc.attr.hydfab` integrations. Requires the `testdata_20250901.zip` bundle (Step 1 above).
```bash
uv run pytest ../tests/test_rafts_prep_to_pred.py -v
```

> **Note on Debugging:** If a test fails, you can stream the standard output and standard error from the Python subprocesses directly to your terminal by running pytest with the `-s` flag (e.g., `uv run pytest ../tests/test_rafts_hfatl_full_workflow.py -v -s`).

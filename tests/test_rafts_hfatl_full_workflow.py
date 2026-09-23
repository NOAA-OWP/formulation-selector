import shutil
import subprocess
import pytest
import pandas as pd
import geopandas as gpd
import pyogrio
import xarray as xr
from pathlib import Path

# Set paths relative to the repository root (assuming pytest is run from the root)
HERE = Path(__file__).resolve().parent
DIR_REPO = HERE.parent
DIR_CONFIG = DIR_REPO / "tests" / "config" / "hfatl"
DIR_DATA = DIR_REPO / "tests" / "data"
DIR_RUN = DIR_DATA / "run_data"

# Python execution paths
DIR_PREP = DIR_REPO / "pkg" / "rafts_prep" / "rafts_prep" / "flow"
DIR_PY = DIR_REPO / "pkg" / "rafts_algo" / "rafts_algo" / "flow"

# Test configurations
PREP_CONFIG = DIR_CONFIG / "hfatl_prep_config.yaml"
ATTR_CONFIG = DIR_CONFIG / "hfatl_attr_config.yaml"
ALGO_CONFIG = DIR_CONFIG / "hfatl_algo_config.yaml"
PRED_CONFIG = DIR_CONFIG / "hfatl_pred_config.yaml"

# Dataset identity and fixture shape, per hfatl_prep_config.yaml / hfatl_attr_config.yaml
DATASET = "hfatl_test_x30"
N_X300_LOCS = 300  # rows in integ_test_predictors_x300.parquet, ingested wholesale by step 1
N_TRAIN_GAGES = 30  # of those 300, the subset with a mapping in hfv4_x30.gpkg
N_TRAIN_DIVIDES = 1797  # divide-level rows in hfv4_x30.gpkg mapping to the 30 training gages
N_TRAIN_ATTRS = 19  # len(attr_select.hfatl_vars) in hfatl_attr_config.yaml
N_PRED_DIVIDES = 280  # rows in jul26_cal_hf4_predictors_9locations_final.parquet
ALGOS = {  # algo name -> expected number of clusters (k)
    "kmeans_k3": 3,
    "kmeans_k5": 5,
    "gower_agglomerative_k4": 4,
    "gower_agglomerative_k6": 6,
}

DIR_STD_BASE = DIR_RUN / "input" / "user_data_std" / DATASET
DIR_ATTRS = DIR_RUN / "input" / "attrs_hfatl" / DATASET / "all"
DIR_ALGOS = DIR_RUN / "output" / "trained_algorithms" / DATASET
DIR_PREDS = DIR_RUN / "output" / "algorithm_predictions" / DATASET
DIR_REGN = DIR_RUN / "output" / "regionalization" / DATASET
DIR_VIZ = DIR_RUN / "output" / "data_visualizations" / DATASET
PATH_REGN_GPKG = DIR_RUN / "output" / "regionalization" / "hfatl" / "rapid_test_9_locs_v4_regn.gpkg"


@pytest.fixture(scope="class", autouse=True)
def clean_run_data():
    """Remove generated pipeline output before (and after) the test class runs.

    Without this, a stale output directory from a previous run (or a previous
    failed attempt) can make a broken step look like it passed, since later
    steps may still find usable files left over from an earlier, different
    configuration. This bit the initial version of this test: a leftover
    dataset directory from an unrelated prep script masked a broken config
    for several steps.
    """
    shutil.rmtree(DIR_RUN, ignore_errors=True)
    yield
    shutil.rmtree(DIR_RUN, ignore_errors=True)


def run_uv_command(script_path, *args):
    """Executes the pipeline script and fails the test if the subprocess fails.

    Runs with cwd=DIR_CONFIG so the relative paths inside the hfatl_*.yaml
    configs (e.g. '../../data/...') resolve consistently across flow scripts,
    some of which resolve relative paths against the config file's own
    directory and some of which resolve them against the process cwd.
    """
    cmd = [
        "uv", "run",
        "--project", str(DIR_REPO / "pkg"),
        "python", str(script_path)
    ] + list(args)

    result = subprocess.run(
        cmd,
        cwd=DIR_CONFIG,
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        pytest.fail(f"Pipeline step failed: {' '.join(cmd)}\nSTDERR: {result.stderr}")

    return result


class TestRegionalizationPipeline:
    """
    Integration test for the hfATLAS regionalization pipeline using subset data:
    - Training: 30 gages / 1797 divides (hfv4_x30.gpkg + integ_test_predictors_x300.parquet)
    - Prediction: 9 gages / 280 divides (rapid_test_9_locs_v4.gpkg + jul26_cal_hf4_predictors_9locations_final.parquet)

    Each step asserts on the actual output artifacts it should have produced,
    not just on the subprocess exit code, so a step that runs but silently
    produces wrong/empty output fails here instead of surfacing as a
    confusing failure (or a false pass) in a later step.
    """

    def test_step_1_prepare_test_dataset(self):
        """1. Ingest the gage-level predictor fixture wholesale, registering dataset metadata."""
        script = DIR_CONFIG / "prep_regn_test_agg.py"
        run_uv_command(script, str(PREP_CONFIG))

        nc_files = list(DIR_STD_BASE.glob("*.nc"))
        assert nc_files, f"No standardized .nc dataset written to {DIR_STD_BASE}"

        ds = xr.open_dataset(nc_files[0])
        assert ds.sizes.get("gage_id") == N_X300_LOCS, (
            f"Expected {N_X300_LOCS} ingested locations, got {ds.sizes.get('gage_id')}"
        )

    def test_step_2_grab_attributes(self):
        """2. Area-weight-aggregate divide-level attributes up to the 30 training gages."""
        script = DIR_PREP / "rafts_agg_hfatl_basin.py"
        run_uv_command(
            script,
            "--path_prep_config", str(PREP_CONFIG),
            "--path_attr_config", str(ATTR_CONFIG)
        )

        path_attrs = DIR_ATTRS / "attr_all.parquet"
        assert path_attrs.exists(), f"Aggregated attributes not written to {path_attrs}"

        df = pd.read_parquet(path_attrs)
        expected_cols = {"featureID", "featureSource", "data_source", "dl_timestamp", "attribute", "value"}
        assert expected_cols.issubset(df.columns), f"Missing expected columns: {expected_cols - set(df.columns)}"
        assert df["featureID"].nunique() == N_TRAIN_GAGES, (
            f"Expected {N_TRAIN_GAGES} aggregated gages, got {df['featureID'].nunique()}"
        )
        assert df["attribute"].nunique() == N_TRAIN_ATTRS, (
            f"Expected {N_TRAIN_ATTRS} aggregated attributes, got {df['attribute'].nunique()}"
        )
        assert not df["value"].isna().all(), "All aggregated attribute values are NaN"

        gpkg_files = list(DIR_STD_BASE.glob("*_loc.gpkg"))
        assert gpkg_files, f"No companion _loc.gpkg written to {DIR_STD_BASE}"
        gdf = gpd.read_file(gpkg_files[0])
        assert gdf.shape[0] == N_TRAIN_DIVIDES, (
            f"Expected {N_TRAIN_DIVIDES} divide-level rows in companion GPKG, got {gdf.shape[0]}"
        )
        assert gdf["featureID"].nunique() == N_TRAIN_GAGES, (
            f"Expected {N_TRAIN_GAGES} unique gages in companion GPKG, got {gdf['featureID'].nunique()}"
        )

    def test_step_3_train_algorithms(self):
        """3. Train the clustering algorithms (chunk size 4) on the 30 training gages."""
        script = DIR_PY / "rafts_proc_algo_pool.py"
        run_uv_command(script, str(ALGO_CONFIG), "--chunk_size", "4")

        for algo in ALGOS:
            path_joblib = DIR_ALGOS / f"algo_{algo}_cluster_labels__{DATASET}.joblib"
            assert path_joblib.exists(), f"Trained model not found: {path_joblib}"

        path_eval = DIR_ALGOS / f"algo_eval_{DATASET}.csv"
        assert path_eval.exists(), f"Algorithm evaluation summary not found: {path_eval}"
        df_eval = pd.read_csv(path_eval)
        assert df_eval.shape[0] == len(ALGOS), (
            f"Expected {len(ALGOS)} rows in algo eval summary, got {df_eval.shape[0]}"
        )

    def test_step_4_perform_prediction(self):
        """4. Perform cluster predictions directly on the 280 rapid-test divides."""
        script = DIR_PY / "rafts_pred_algo.py"
        run_uv_command(script, str(PRED_CONFIG))

        for algo, k in ALGOS.items():
            path_pred = DIR_PREDS / f"pred_{algo}_cluster_labels__{DATASET}.parquet"
            assert path_pred.exists(), f"Predictions not found: {path_pred}"

            df = pd.read_parquet(path_pred)
            assert df.shape[0] == N_PRED_DIVIDES, (
                f"{algo}: expected {N_PRED_DIVIDES} predicted divides, got {df.shape[0]}"
            )
            assert df["featureID"].nunique() == N_PRED_DIVIDES, f"{algo}: duplicate divide predictions found"
            assert not df["prediction"].isna().any(), f"{algo}: NaN cluster label predictions found"
            assert df["prediction"].nunique() <= k, (
                f"{algo}: expected at most {k} distinct cluster labels, got {df['prediction'].nunique()}"
            )

    def test_step_5_pair_donor_receivers(self):
        """5. Pair the donor-receivers for the rapid-test prediction locations."""
        script = DIR_PY / "rafts_pair_donors.py"
        run_uv_command(script, str(PRED_CONFIG))

        for algo in ALGOS:
            path_donors = DIR_REGN / f"donor_pairs_{algo}_cluster_labels__{DATASET}.csv"
            path_receivers = DIR_REGN / f"receiver_params_{algo}_cluster_labels__{DATASET}.csv"
            assert path_donors.exists(), f"Donor pairs not found: {path_donors}"
            assert path_receivers.exists(), f"Receiver params not found: {path_receivers}"

            df_donors = pd.read_csv(path_donors)
            assert df_donors.shape[0] == N_PRED_DIVIDES, (
                f"{algo}: expected {N_PRED_DIVIDES} donor pairs, got {df_donors.shape[0]}"
            )
            assert not df_donors["donor_id"].isna().any(), f"{algo}: unpaired (NaN donor_id) receivers found"

            df_receivers = pd.read_csv(path_receivers)
            assert df_receivers.shape[0] == N_PRED_DIVIDES, (
                f"{algo}: expected {N_PRED_DIVIDES} receiver rows, got {df_receivers.shape[0]}"
            )

    def test_step_6_map_predictions(self):
        """6. Map the predictions onto a static map for visual verification."""
        script = DIR_PY / "rafts_map_pred_hfatl.py"
        run_uv_command(script, str(PRED_CONFIG))

        for algo in ALGOS:
            path_png = DIR_VIZ / f"prediction_map_{DATASET}_cluster_labels_{algo}_test.png"
            assert path_png.exists(), f"Prediction map not found: {path_png}"
            assert path_png.stat().st_size > 0, f"Prediction map is empty: {path_png}"

    def test_step_7_write_params_to_gpkg(self):
        """7. Compile regionalized parameters into the rapid-test subset GPKG."""
        script = DIR_PY / "rafts_regn_params_gpkg.py"
        run_uv_command(script, str(PRED_CONFIG))

        assert PATH_REGN_GPKG.exists(), f"Regionalized GPKG not found: {PATH_REGN_GPKG}"

        layers = [lyr for lyr, _geom_type in pyogrio.list_layers(PATH_REGN_GPKG)]
        param_layers = [lyr for lyr in layers if "gower_agglomerative_k4" in lyr]
        assert param_layers, (
            f"No regionalized-parameters layer found for algo_select='gower_agglomerative_k4' "
            f"in {PATH_REGN_GPKG} (layers found: {layers}). This is exactly the failure mode "
            f"caught while writing this test: algo_select must match a trained algorithm name "
            f"exactly (e.g. 'gower_agglomerative_k4', not 'gower_agglomerative_4'), or this step "
            f"silently writes nothing new."
        )

        gdf_params = gpd.read_file(PATH_REGN_GPKG, layer=param_layers[0])
        assert gdf_params.shape[0] == N_PRED_DIVIDES, (
            f"Expected {N_PRED_DIVIDES} rows in regionalized-parameters layer, got {gdf_params.shape[0]}"
        )
        assert "donor_id" in gdf_params.columns, "Regionalized-parameters layer missing 'donor_id' column"
        assert not gdf_params["donor_id"].isna().any(), "Regionalized-parameters layer has unpaired receivers"

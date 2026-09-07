# Changelog / Contributions
# 2026-05-27 Refactored to dynamically generate configs and use tempfile for isolated integration testing

import sys
import subprocess
import unittest
import tempfile
from pathlib import Path
import yaml
import pandas as pd
import geopandas as gpd
import xarray as xr
import numpy as np
from shapely.geometry import LineString
import rafts_algo.utils as raftsutil

class TestHfAtlasRaftsWorkflow(unittest.TestCase):
    """
    Integration test for the hfATLAS-based RaFTS workflow without mocking.
    
    1) Data Ingestion: hfatlas_to_rafts_prep.py (Python-based attribute/geometry extraction)
    2) Training: rafts_proc_algo_pool.py (Parallelized multiprocessing & clustering)
    3) Prediction: rafts_pred_algo.py (Dynamic cluster discovery)
    4) Mapping: rafts_map_pred_hfatl.py (CONUS-wide cluster mapping)
    """

    @classmethod
    def setUpClass(cls):
        """Create a persistent temporary directory and dynamically generate configuration files."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.dir_base = Path(cls.temp_dir.name)
        
        # Setup internal paths
        cls.dir_std_base = cls.dir_base / "user_data_std"
        cls.dir_db_attrs = cls.dir_base / "attrs_hfatl"
        cls.dataset = "test_hfatl_ds"
        
        cls.dir_std_base.mkdir(parents=True, exist_ok=True)
        cls.dir_db_attrs.mkdir(parents=True, exist_ok=True)
        
        # Resolve script paths dynamically from repo root (assuming tests/ is 1 level down)
        cls.dir_repo = Path(__file__).resolve().parents[1] 
        cls.path_rafts_proc_algo_pool = cls.dir_repo / "pkg" / "rafts_algo" / "rafts_algo" / "flow" / "rafts_proc_algo_pool.py"
        cls.path_rafts_pred_algo = cls.dir_repo / "pkg" / "rafts_algo" / "rafts_algo" / "flow" / "rafts_pred_algo.py"
        cls.path_rafts_map_pred = cls.dir_repo / "pkg" / "rafts_algo" / "rafts_algo" / "flow" / "rafts_map_pred_hfatl.py"
        
        # 1. GENERATE DYNAMIC YAML CONFIGURATIONS
        cls.path_attr_cfg = cls.dir_base / "xssa_hfatl_attr_config.yaml"
        cls.path_algo_cfg = cls.dir_base / "xssa_hfatl_algo_config.yaml"
        cls.path_pred_cfg = cls.dir_base / "xssa_hfatl_pred_config.yaml"
        
        attr_cfg = {
            'col_schema': [
                {'featureID': '{gage_id}'},
                {'featureSource': 'hf_test_source'}
            ],
            'file_io': [
                {'dir_base': str(cls.dir_base)},
                {'dir_std_base': str(cls.dir_std_base)},
                {'dir_db_attrs': str(cls.dir_db_attrs / "{ds}")},
                {'ds_type': 'training'},
                {'write_type': 'parquet'},
                {'path_meta': "{dir_std_base}/{ds}/nldi_feat_{ds}_{ds_type}.parquet"}
            ],
            'formulation_metadata': [{'datasets': [cls.dataset]}],
            'attr_select': [
                {'hfatl_id_col': 'divide_id'},
                {'paths_hfatl': [str(cls.dir_base / "dummy_ha.parquet")]},
                {'hfatl_vars': ['pet_mm_s01', 'cly_pc_sav', 'cly_pc_uav']}
            ]
        }
        with open(cls.path_attr_cfg, 'w') as f:
            yaml.dump(attr_cfg, f)
            
        algo_cfg = {
            'algorithms': {
                'rf': [{'n_estimators': 5}], # <--- CRITICAL FIX: Scikit-learn expects an integer here, not a list!
                'kmeans': [{'n_clusters': [2, 3]}]
            },
            'task_type': 'regression',
            'test_size': 0.3,
            'seed': 42,
            'read_type': 'all',  # Forces PyArrow to recursively read VPU partitions!
            'name_attr_config': str(cls.path_attr_cfg), # Explicitly point to temp attr config!
            'metrics': ['dummy_var'],
            'uncertainty': {
                'mapie': [{'alpha': [0.1], 'method': 'plus', 'cv': 2, 'agg_function': 'median'}]
            }
        }
        with open(cls.path_algo_cfg, 'w') as f:
            yaml.dump(algo_cfg, f)
            
        pred_cfg = {
            'name_attr_config': str(cls.path_attr_cfg),
            'name_algo_config': str(cls.path_algo_cfg),
            'ds_type': 'prediction',
            'write_type': 'parquet',
            'path_meta': str(cls.dir_base / "dummy_ha.parquet"),
            'pred_file_comid_colname': 'featureID',
            'algo_response_vars': ['dummy_var'],
            'algo_type': ['rf', 'kmeans'],
            'read_type': 'all' # Matches algo_config to load directories
        }
        with open(cls.path_pred_cfg, 'w') as f:
            yaml.dump(pred_cfg, f)
            
        # Output Directories
        dirs_std_dict = raftsutil.rafts_save_algo_dir_struct(cls.dir_base)
        cls.dir_out = dirs_std_dict.get('dir_out')
        cls.dir_out_alg_ds = Path(dirs_std_dict.get('dir_out_alg_base')) / cls.dataset
        cls.dir_out_preds_ds = Path(dirs_std_dict.get('dir_out_preds_base')) / cls.dataset
        cls.dir_out_viz_ds = Path(dirs_std_dict.get('dir_out_viz_base')) / cls.dataset

    @classmethod
    def tearDownClass(cls):
        """Clean up the generated hfATLAS output directories."""
        cls.temp_dir.cleanup()

    def test_01_hfatlas_prep(self):
        """Execute the pure Python hfATLAS preparation using dynamically generated dummy data"""
        # 1. Setup standard directories
        ds_dir = self.dir_std_base / self.dataset
        ds_dir.mkdir(parents=True, exist_ok=True)
        nc_path = ds_dir / f"{self.dataset}.nc"
        gpkg_loc_path = ds_dir / f"{self.dataset}_loc.gpkg"
        
        # --- GENERATE SELF-CONTAINED DUMMY DATA ---
        div_ids = [f"div_{i}" for i in range(1, 31)] # 30 catchments ensures enough data for ML Cross-Validation splits
        
        # A. Dummy Hydrofabric GPKG
        dummy_hf_path = self.dir_base / "dummy_hf.gpkg"
        dummy_hf = gpd.GeoDataFrame({
            'divide_id': div_ids,
            'gage_id': div_ids, 
            'vpuid': ['01'] * 30
        }, geometry=[LineString([(0, i), (1, i)]) for i in range(30)], crs="EPSG:4326")
        dummy_hf.to_file(dummy_hf_path, driver="GPKG", layer="flowpaths")
        
        # B. Dummy hfATLAS Parquet (with pint-aware tuple columns)
        dummy_ha_path = self.dir_base / "dummy_ha.parquet"
        dummy_ha = pd.DataFrame({
            'divide_id': div_ids,
            'featureID': div_ids,
            'featureSource': ['hf_test_source'] * 30, 
            'data_source': ['dummy_atlas'] * 30,
            'dl_timestamp': ['2026-01-01'] * 30,
            "('pet_mm_s01', 'mm')": np.random.rand(30),
            "('cly_pc_sav', '%')": np.random.rand(30),
            "('cly_pc_uav', '%')": np.random.rand(30)
        })
        dummy_ha.to_parquet(dummy_ha_path)

        # C. Dummy .nc Response Variable file (Ensure tracking attributes exist!)
        ds_xr = xr.Dataset(
            {"dummy_var": (("gage_id",), np.random.rand(len(div_ids)))},
            coords={"gage_id": div_ids}
        )
        ds_xr.attrs['respvar_mappings'] = 'dummy_var'
        ds_xr.attrs['featureSource'] = 'hf_test_source'
        ds_xr.attrs['featureID'] = '{gage_id}'
        ds_xr.to_netcdf(nc_path)
        
        # D. NEW: Dummy Metadata Files (Required by training and prediction steps!)
        meta_df = pd.DataFrame({
            'gage_id': div_ids,
            'featureID': div_ids,
            'featureSource': ['hf_test_source'] * 30
        })
        meta_df.to_parquet(ds_dir / f"nldi_feat_{self.dataset}_training.parquet")
        meta_df.to_parquet(ds_dir / f"nldi_feat_{self.dataset}_prediction.parquet")
        # -----------------------------------------------

        # 2. Generate the loc.gpkg using the utility and our dummy HF
        print("Generating points GPKG...")
        gdf_hf_points = raftsutil.generate_algo_points_gpkg_wrap(
            div_ids=pd.Series(div_ids),
            path_hf_gpkg=dummy_hf_path, 
            path_gpkg_rafts_prep=gpkg_loc_path,
            hf_layer='flowpaths',
            map_id_col='divide_id',
            featureSource='hf_test_source'
        )

        # 3. Extract Parquet Attributes from our dummy HA
        print("Lazy-loading and merging hfATLAS attributes...")
        ha_vars = ['pet_mm_s01', 'cly_pc_sav', 'cly_pc_uav']
        df_hfatlas = raftsutil.read_hfatlas_wrap_dask([dummy_ha_path], attrs_sel=ha_vars, map_id_col='divide_id')
        
        # 4. Combine and Write to VPU-partitioned directories
        raftsutil.hfatl_hf_cmbo_wrap(
            df_hfatlas=df_hfatlas,
            gdf_hf=gdf_hf_points,
            ds=self.dataset,
            dir_db_attrs=self.dir_db_attrs, # Base attributes dir
            featureSource='hf_test_source',
            vpu_mapped=True
        )

        # 5. Assertions
        parq_files = list(self.dir_db_attrs.rglob("*.parquet"))
        self.assertGreater(len(parq_files), 0, "hfATLAS parquet files were not generated.")
        self.assertTrue(gpkg_loc_path.exists(), "The companion GPKG was not generated.")

    def test_02_rafts_proc_algo_pool(self):
        """Integration test for the parallelized rafts_proc_algo_pool.py script"""
        cmd_algo_train = [
            sys.executable, str(self.path_rafts_proc_algo_pool), 
            str(self.path_algo_cfg), 
            "--chunk_size", "2"
        ]
        print(f"Running {cmd_algo_train}")
        try:
            subprocess.run(cmd_algo_train, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_proc_algo_pool.name} failed.\nStderr: {e.stderr}\nStdout: {e.stdout}")

        self.assertTrue(self.dir_out_alg_ds.exists())
        
        # --->  Check that Random Forest specifically was trained!
        rf_joblibs = list(self.dir_out_alg_ds.glob("algo_rf_*.joblib"))
        self.assertGreater(len(rf_joblibs), 0, "Random Forest model was not saved! Did it crash during training?")
        
        # Ensure dynamic cluster sizes generated the specific joblib models (e.g., kmeans_k2)
        joblib_files = list(self.dir_out_alg_ds.glob("*.joblib"))
        self.assertGreater(len(joblib_files), 0, "No trained algorithm .joblib files found.")

    def test_03_rafts_pred_algo(self):
        """Integration test for the dynamic cluster prediction step"""
        cmd_pred = [sys.executable, str(self.path_rafts_pred_algo), str(self.path_pred_cfg)]
        print(f"Running {cmd_pred}")
        try: 
            subprocess.run(cmd_pred, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_pred_algo.name} failed.\nStderr: {e.stderr}\nStdout: {e.stdout}")

        self.assertTrue(self.dir_out_preds_ds.exists())
        
        # Verify that raftsutil.discover_dynamic_algos successfully found the models and predicted them
        pred_files = list(self.dir_out_preds_ds.glob("*.parquet"))
        self.assertGreater(len(pred_files), 0, "No prediction parquet files were generated.")

    def test_04_rafts_map_pred_hfatl(self):
        """Integration test for final visual mapping across the hfATLAS hydrofabric"""
        cmd_map = [sys.executable, str(self.path_rafts_map_pred), str(self.path_pred_cfg), "--analysis_str", "hfatl_test"]
        print(f"Running {cmd_map}")
        try: 
            subprocess.run(cmd_map, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_map_pred.name} failed.\nStderr: {e.stderr}")

        self.assertTrue(self.dir_out_viz_ds.exists())
        
        # Ensure the maps were successfully rendered for the different dynamic clusters
        map_files = list(self.dir_out_viz_ds.glob("prediction_map_*.png"))
        self.assertGreater(len(map_files), 0, "No prediction maps were generated.")
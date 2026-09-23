import subprocess
import unittest
from pathlib import Path
import pytest
import rafts_prep.proc_eval_metrics as pem
import rafts_algo.utils as raftsutil
import shutil
import pandas as pd
import geopandas as gpd

_PATH_XSSA_PREP_CONFIG = Path(__file__).parent / "config" / "xssa" / "xssa_prep_config.yaml"

def _xssa_testdata_available() -> bool:
    """Check whether the private testdata_20250901 bundle (see tests/README.md)
    has been downloaded and extracted, before running any test that depends on it.
    """
    try:
        home_dir = raftsutil._make_home_dir([])
        col_schema_df = pem.read_schm_ls_of_dict(schema_path=_PATH_XSSA_PREP_CONFIG)
        path_camels = Path(col_schema_df['path_camels'].iloc[0].format(home_dir=home_dir))
        if not path_camels.is_absolute():
            path_camels = (_PATH_XSSA_PREP_CONFIG.parent / path_camels).resolve()
        path_data = Path(col_schema_df['path_data'].iloc[0].format(home_dir=home_dir))
        if not path_data.is_absolute():
            path_data = (_PATH_XSSA_PREP_CONFIG.parent / path_data).resolve()
        return path_camels.exists() and path_data.exists()
    except Exception:
        return False

@pytest.mark.skipif(
    not _xssa_testdata_available(),
    reason="testdata_20250901 bundle not found; see tests/README.md to download and extract it"
)
class TestFsPrepProcAttrHydfabFsAlgo(unittest.TestCase):
    """
    Integration test for the non-standard RaFTS workflow where the 
    user desires to perform custom transformations on the attributes
    1) rafts_prep's standardization of a sample dataset 
               (subset from Mai et al 2022 xSSA) ->
    2) proc.attr.hydfab's rafts_attrs_grab.R script -> 
    3) rafts_algo's rafts_tfrm_attrs.py script ->
    4) rafts_algo's rafts_proc_algo_viz.py script ->
    5) rafts_algo's rafts_pred.py based on locations defined by gen_pred_locs_xssa.R &
      and associated transformations from rafts_tfrm_attrs.py

    The required input data, testdata_20250901 may be extracted from the 
    testdata_20250901.zip, shared NOAA-wide here:
    https://drive.google.com/file/d/1z0joW1TMXu9EwejiUNL_Tge5illGSIvg/view?usp=sharing
    within the following NOAA google drive directory, RaFTS_NOAA:
    https://drive.google.com/drive/folders/1JDtJKSfbmtBBp1nkBdNMwzS_EvFYkvpC?usp=drive_link

    The user must download the testdata_20250901 & edit the paths specificied
    inside rafts/tests/config/xssa/xssa_pred_config.yaml
    to wherever they store the testdata_20250901/ data directory. 

    Changelog/contributions
    2025-09-30, Originally created, GL
    2025-10-10 refactor to renamed rafts_algo modules, GL
    """
    # ----------------------------------------------------------------------- #
    # Parse the config file & run input checks:
    # ----------------------------------------------------------------------- #
    def setUp(self):
        """
        Read the config files and set up necessary paths.
        """
        self.dir_tests = Path(__file__).parent.resolve()
        self.path_cfg_prep = self.dir_tests / "config" / "xssa" / "xssa_prep_config.yaml"
        self.path_rafts_prep = self.dir_tests / "config" / "xssa" / "prep_xssa_metrics.py"

        # Parse the rafts_prep config file
        self.home_dir = raftsutil._make_home_dir([])
        self.col_schema_df = pem.read_schm_ls_of_dict(schema_path=self.path_cfg_prep)

        dir_save_raw = self.col_schema_df['dir_save'].iloc[0].format(home_dir=self.home_dir)
        self.dir_save = Path(dir_save_raw)
        if not self.dir_save.is_absolute():
            self.dir_save = (self.path_cfg_prep.parent / self.dir_save).resolve()
        self.dataset = self.col_schema_df['dataset_name'].iloc[0]
        self.formulation_id = pem.std_form_id(self.col_schema_df)
        self.dir_std_base = pem.dir_std_dataset(self.dir_save, self.dataset).parent
        self.dir_dataset = pem.dir_std_dataset(self.dir_save, self.dataset)
        # Use cls.save_path_nc to store on the class so that this can be deleted in tearDownClass
        TestFsPrepProcAttrHydfabFsAlgo.save_path_nc = pem.path_std_dataset(dir_save=self.dir_save,
                                                dataset_name=self.dataset,
                                                formulation_id=self.formulation_id,
                                                fmt='nc')
        # -------------- ATTRIBUTES ----------------------------------------- #
        # Parse the attr config file
        self.path_attr_cfig = raftsutil.build_cfig_path(self.path_cfg_prep, "xssa_attr_config.yaml") #self.dir_tests / "config" / "xssa" / "xssa_attr_config.yaml"
        self.path_rafts_attrs_grab = self.dir_tests.parent / "pkg" / "proc.attr.hydfab" / "flow" / "rafts_attrs_grab.R"
        attr_cfig = raftsutil.AttrConfigAndVars(self.path_attr_cfig)
        attr_cfig._read_attr_config()
        dir_base_raw = [x.get('dir_base') for x in attr_cfig.attr_config['file_io'] if 'dir_base' in x.keys()][0].format(home_dir=self.home_dir )
        dir_base = Path(dir_base_raw)
        if not dir_base.is_absolute():
            dir_base = (self.path_attr_cfig.parent / dir_base).resolve()
        dir_base = str(dir_base)
        self.dir_db_attrs = [x.get('dir_db_attrs') for x in attr_cfig.attr_config['file_io'] if 'dir_db_attrs' in x.keys()][0].format(dir_base=dir_base)
        self.ds_type = [x.get('ds_type') for x in attr_cfig.attr_config['file_io'] if 'ds_type' in x.keys()][0]

        vals = {'ds_type':self.ds_type,'write_type':'parquet',
                'dir_std_base':self.dir_std_base,'ds':self.dataset}
        path_meta_fstr = [x.get('path_meta') for x in attr_cfig.attr_config['file_io'] if 'path_meta' in x.keys()][0]
        # Using cls.path_meta so that this can be deleted in tearDownClass
        TestFsPrepProcAttrHydfabFsAlgo.path_meta = Path(path_meta_fstr.format(**vals))
        print(f"Metadata path: {TestFsPrepProcAttrHydfabFsAlgo.path_meta}")

        # -------------- ATTRIBUTES TRANSFORMATION -------------------------- #
        self.path_tfrm_cfig = raftsutil.build_cfig_path(self.path_cfg_prep, "xssatf_attrs_tform.yaml")
        self.path_rafts_tfrm_attrs =  self.dir_tests.parent / "pkg" / "rafts_algo" / "rafts_algo" / "flow" / "rafts_tfrm_attrs.py"
        
        
        # -------------- ALGO TRAIN/TEST ------------------------------------ #
        # Parse the algo config file:
        self.path_algo_cfg =raftsutil.build_cfig_path(self.path_cfg_prep, "xssatf_algo_config.yaml") 
        self.path_rafts_proc_algo_viz = self.dir_tests.parent / "pkg" / "rafts_algo" / "rafts_algo" / "flow" / "rafts_proc_algo_viz.py"
        self.algo_cfig = raftsutil.AlgoConfigParser(self.path_algo_cfg)
        self.algo_cfig._read_algo_config()

        # Ensure dir_save and dir_base exist
        self.dir_save.mkdir(parents=True, exist_ok=True)
        Path(dir_base).mkdir(parents=True, exist_ok=True)

        # Extract variables from dictionary created by AlgoConfigParser
        self.algo_config = self.algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["algo_config"]
        dirs_std_dict = raftsutil.rafts_save_algo_dir_struct(dir_base)
        self.dir_out = dirs_std_dict.get('dir_out')
        self.dir_out_alg_base = dirs_std_dict.get('dir_out_alg_base')
        self.dir_out_preds_base = dirs_std_dict.get('dir_out_preds_base')
        self.dir_out_anlys_base = dirs_std_dict.get('dir_out_anlys_base')
        self.dir_out_viz_base = dirs_std_dict.get('dir_out_viz_base')
        self.dir_out_alg_ds = Path(self.dir_out_alg_base/Path(self.dataset))
        self.path_all_locs = Path(self.dir_db_attrs).parent / 'gpkg' / 'all_locs.gpkg' # Refer to proc.attr.hydfab::std_path_gpkg_db if this ever changes.

        # The tear-down locations:
        TestFsPrepProcAttrHydfabFsAlgo.dir_out_viz_base = self.dir_out_viz_base
        TestFsPrepProcAttrHydfabFsAlgo.dir_out_anlys_base = self.dir_out_anlys_base
        TestFsPrepProcAttrHydfabFsAlgo.dir_out_alg_base = self.dir_out_alg_base
        TestFsPrepProcAttrHydfabFsAlgo.dir_dataset = self.dir_dataset
        TestFsPrepProcAttrHydfabFsAlgo.dir_out_preds_base = self.dir_out_preds_base
        TestFsPrepProcAttrHydfabFsAlgo.dir_db_attrs = self.dir_db_attrs
        TestFsPrepProcAttrHydfabFsAlgo.path_all_locs = Path(self.path_all_locs)
        TestFsPrepProcAttrHydfabFsAlgo.dir_std_base = Path(self.dir_std_base)
        # ------------------------------------------------------------------- #
        # Run rafts_prep first to generate the .nc as input for rafts_attrs_grab.R
        # ------------------------------------------------------------------- #
        # --- Pre-run checks and cleanup ---
        path_camels = Path(self.col_schema_df['path_camels'].iloc[0].format(home_dir=self.home_dir))
        if not path_camels.is_absolute():
            path_camels = (self.path_cfg_prep.parent / path_camels).resolve()
        path_data = Path(self.col_schema_df['path_data'].iloc[0].format(home_dir=self.home_dir))
        if not path_data.is_absolute():
            path_data = (self.path_cfg_prep.parent / path_data).resolve()
        if not path_camels.exists():
            self.fail(f"Required input {path_camels} not specified.")
        if not path_data.exists():
            self.fail(f"Required input {path_data} not specified.")

        # --- Run the subprocess ---
        cmd_prep = ["python", str(self.path_rafts_prep), str(self.path_cfg_prep)]
        try:
            rslt_prep = subprocess.run(cmd_prep, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            print(f"Completed rafts_prep's {self.path_rafts_prep.name}.py")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_prep} failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")
    
    def test_01_rafts_prep_script_run(self):
        """
        Execute the rafts_prep.py script as a subprocess and validate outputs.
        """
        # --- Pre-run checks and cleanup ---
        path_camels = Path(self.col_schema_df['path_camels'].iloc[0].format(home_dir=self.home_dir))
        if not path_camels.is_absolute():
            path_camels = (self.path_cfg_prep.parent / path_camels).resolve()
        path_data = Path(self.col_schema_df['path_data'].iloc[0].format(home_dir=self.home_dir))
        if not path_data.is_absolute():
            path_data = (self.path_cfg_prep.parent / path_data).resolve()
        if not path_camels.exists():
            self.fail(f"Required input {path_camels} not specified.")
        if not path_data.exists():
            self.fail(f"Required input {path_data} not specified.")

        if self.save_path_nc.exists():
            self.save_path_nc.unlink()

        # --- Run the subprocess ---
        cmd = ["python", str(self.path_rafts_prep), str(self.path_cfg_prep)]
        try:
            rslt = subprocess.run(cmd, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            print(f"Subprocess stdout: {rslt.stdout}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")
        print("Running rafts_prep tests")
        # --- Post-run assertions ---
        self.assertTrue(self.dir_save.exists(), "The dir_save directory was not created.")
        self.assertTrue(self.save_path_nc.exists(), "The output .nc file was not created.")
        self.assertTrue(self.dir_std_base.exists(), "The dir_std_base directory was not created.")
        self.assertTrue(self.dir_dataset.exists(), "The dir_dataset directory was not created.")

        # --- Validate the content of the .nc file ---
        xr_dat = raftsutil._open_response_data_rafts(dir_std_base=self.dir_std_base,
                                        ds=self.dataset,
                                        mtch_str="*.nc")
        
        self.assertEqual(len(xr_dat['basin_name']), 220, "Incorrect number of basins.")
        self.assertIn('KGE', xr_dat.variables, "KGE variable is missing.")
        self.assertIn('RMSE', xr_dat.variables, "RMSE variable is missing.")
        self.assertIn('NSE', xr_dat.variables, "NSE variable is missing.")
        self.assertIn('gage_id', xr_dat.attrs.keys(), "gage_id attribute is missing.")
        self.assertEqual(xr_dat.attrs.get('gage_id'), 'basin_id', "Incorrect gage_id attribute value.")
        self.assertIn('featureID', xr_dat.attrs.keys(), "featureID attribute is missing.")
        self.assertEqual(xr_dat.attrs.get('featureID'), 'USGS-{gage_id}', "Incorrect featureID attribute value.")
        self.assertEqual(xr_dat.attrs.get('featureSource'), 'nwissite', "Incorrect featureSource attribute value.")
        self.assertEqual(xr_dat.coords._names, {'gage_id'}, "Incorrect coordinates.")

    def test_02_rafts_attrs_grab_run(self):
        """Integration test for proc.attr.hydfab's rafts_attrs_grab.R script.
        """
        cmd_attrs_grab = ["Rscript", str(self.path_rafts_attrs_grab), str(self.path_attr_cfig)]
        print(f"Running {cmd_attrs_grab}")
        try: 
            rslt_grab = subprocess.run(cmd_attrs_grab, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            print(f"{self.path_rafts_attrs_grab} stdout: {rslt_grab.stdout}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_attrs_grab} failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")

        parq_files = [x for x in Path(self.dir_db_attrs).iterdir() if x.is_file()]

        xr_dat = raftsutil._open_response_data_rafts(dir_std_base=self.dir_std_base,
                                        ds=self.dataset,
                                        mtch_str="*.nc")
        
        # Run tests on attribute file generation
        self.assertEqual('.parquet', parq_files[0].suffix)
        # Parquet content testing#
        first_parq_file = pd.read_parquet(parq_files[0])
        self.assertIn('featureSource',first_parq_file.columns)
        self.assertIn('featureID',first_parq_file.columns)
        self.assertIn('attribute',first_parq_file.columns)
        self.assertIn('value',first_parq_file.columns)
        # Metadata testing
        self.assertTrue(Path(self.path_meta).exists())
        df_meta = pd.read_parquet(self.path_meta)
        self.assertEqual(df_meta['gage_id'].nunique(),xr_dat.dims['gage_id'])
        self.assertTrue(self.ds_type in str(self.path_meta))
        print("Completed test_proc_attr_hydfab.R")

        # Ensure all_locs.gpkg created
        self.assertTrue(self.path_all_locs.exists())

        # Ensure that the dataset-specific .gpkg created inside dataset dir
        path_rafts_dat_resp = raftsutil._std_rafts_prep_ds_paths(
            dir_std_base=self.dir_std_base,ds=self.dataset,mtch_str='*.nc')
        path_gpkg_ds = raftsutil._std_rafts_prep_ds_companion_gpkg_path(path_rafts_dat_resp[0])
        self.assertTrue(Path(path_gpkg_ds).exists())
        gpkg_ds = gpd.read_file(path_gpkg_ds)
        self.assertGreaterEqual(gpkg_ds.shape[0], df_meta['gage_id'].nunique()) # This should be greater b/c it's possible that the gpkg is combined training & prediction locs
        print("COMPLETED integration test for rafts_pred -> proc.attr.hydfab's rafts_attrs_grab.R")

    def test_03_rafts_tfrm_attrs(self):
        cmd_tfrm = ["python", str(self.path_rafts_tfrm_attrs), str(self.path_tfrm_cfig)]
        print(f"Running {cmd_tfrm} for the training locations.")
        try: 
            subprocess.run(cmd_tfrm, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            #print(f"{self.path_rafts_tfrm_attrs} stdout: {rslt_tfrm.stdout}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_attrs_grab} failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")

        parq_files = [x for x in Path(self.dir_db_attrs).iterdir() if x.is_file()]
        # Test to ensure that the Ratio_cly_pc_uav_sav_np.divide attributes created
        df = pd.read_parquet(parq_files)
        self.assertTrue(df['attribute'].str.contains('Fake_').any())
        print("COMPLETED integration test for attribute transformations pre-training.")
    def test_04_rafts_proc_algo_viz(self):
        """Integration test for the rafts_proc_algo_viz.py script
        """
        cmd_algo_train = ["python", str(self.path_rafts_proc_algo_viz), str(self.path_algo_cfg), "--validate"]
        print(f"Running {cmd_algo_train}")

        try:
            subprocess.run(cmd_algo_train, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            print(f"Completed {cmd_algo_train}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_proc_algo_viz} failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")

        # ----- Ensure the trained algorithms saved and test results stored
        self.assertTrue(self.dir_out_alg_base.exists())
        self.assertTrue(self.dir_out_viz_base.exists())

        # ----- Ensure the plots files exist
        path_ds_viz = self.dir_out_viz_base / self.dataset
        plot_files = list(path_ds_viz.rglob("*.png"))
        self.assertGreaterEqual(len(plot_files), 40, f"Expecting 42 .png files in {path_ds_viz}")
        self.assertTrue(Path(self.dir_out_viz_base / "cb_2018_us_state_500k.shp").exists())

        # ----- Define the .joblib paths & test that they exist
        algos = list(self.algo_config.keys())
        # Read in the standardized dataset generated by rafts_prep & grab comids/coords
        dict_resp_gdf = raftsutil.combine_resp_gdf_comid_wrap(dir_std_base=self.dir_std_base,
                        ds= self.dataset, path_attr_config=self.path_attr_cfig)
        metrics = dict_resp_gdf['dat_resp'].attrs['respvar_mappings'].split('|')
        ls_joblib_paths = [raftsutil.std_algo_path(self.dir_out_alg_ds, algo, metric, self.dataset) for algo in algos for metric in metrics]
        [self.assertTrue(jlb_path.exists(), f"Expected joblib file {jlb_path} not found.") for jlb_path in ls_joblib_paths]
        # ----- Ensure the test predictions .csv files exist inside analysis
        ls_anls_paths = [raftsutil.std_test_pred_obs_path(self.dir_out_anlys_base,self.dataset,metr) for metr in metrics]
        [self.assertTrue(anls_path.exists(), f"Expected analysis .csv file {anls_path} not found.") for anls_path in ls_anls_paths]
        print("COMPLETED rafts_proc_algo_viz integration test")

    def test_06_rafts_pred(self):
        """Integration test for the prediction step after algo training & testing
        """
         # -------------- ALGO PREDICTION ------------------------------------ #
        self.path_gen_pred_locs = self.dir_tests / "config" / "xssa" / "gen_pred_locs_xssa.R"
        self.path_rafts_pred_algo = self.dir_tests.parent / "pkg" / "rafts_algo" / "rafts_algo" / "flow" / "rafts_pred_algo.py"
        self.path_pred_cfg = raftsutil.build_cfig_path(self.path_cfg_prep, "xssatf_pred_config.yaml") #self.dir_tests / "config" / "xssa" / "xssa_pred_config.yaml"
        pred_cfg = raftsutil.PredConfigParser(self.path_pred_cfg)
        pred_cfg._read_pred_config()
        pred_config = pred_cfg.pred_cfg_dict

        # Run the gen_pred_locs
        cmd_gen_pred = ["Rscript", str(self.path_gen_pred_locs), f"{str(self.path_pred_cfg)}"]
        print(cmd_gen_pred)
        try:
            subprocess.run(cmd_gen_pred, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            print(f"Completed {self.path_gen_pred_locs.name}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_gen_pred_locs.name}.R failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")    
        # Run the transformation again
        cmd_tfrm = ["python", str(self.path_rafts_tfrm_attrs), str(self.path_tfrm_cfig)]
        print(f"Running {cmd_tfrm} for the prediction locations.")
        try: 
            subprocess.run(cmd_tfrm, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            #print(f"{self.path_rafts_tfrm_attrs} stdout: {rslt_tfrm.stdout}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_attrs_grab} failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")

        parq_files = [x for x in Path(self.dir_db_attrs).iterdir() if x.is_file()]
        print("COMPLETED attribute transformations pre-prediction.")

        # ------------------------------------------------------------------- #
        cmd_pred = ["python", str(self.path_rafts_pred_algo), str(self.path_pred_cfg), "--validate"]
        try: 
            subprocess.run(cmd_pred, cwd=self.path_cfg_prep.parent, check=True, capture_output=True, text=True)
            print(f"Completed {cmd_pred}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess {self.path_rafts_pred_algo} failed with return code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}")

        # Test contents created inside output/algorithm_predictions
        self.assertTrue(self.dir_out_preds_base.exists())
        dir_pred_ds = self.dir_out_preds_base / self.dataset
        self.assertTrue(dir_pred_ds.exists())

        files_pred_std = [raftsutil.std_pred_path(self.dir_out,algo,metr, self.dataset)
                           for metr in pred_config.get('algo_response_vars') 
                           for algo in pred_config.get('algo_type')]
        [self.assertTrue(file_pred.exists()) for file_pred in files_pred_std]
        print("COMPLETED rafts_pred integration test")
    
    # ----------------------------------------------------------------------- #
    # Final teardown:
    # ----------------------------------------------------------------------- #
    @classmethod
    def tearDownClass(cls): # clean up files created during testing
        print(f"Tearing down test environment...")
        if hasattr(cls, 'save_path_nc') and cls.save_path_nc.exists():
            cls.save_path_nc.unlink()
            print(f"Deleted {cls.save_path_nc} for integration testing relating to rafts_prep->rafts_attrs_grab")
        if hasattr(cls, 'path_meta') and cls.path_meta.exists():
            cls.path_meta.unlink()
            print(f"Deleted {cls.path_meta} for integration testing relating to rafts_attrs_grab.R")
        # TODO create argparse option to remove the tests/input/attributes/comid_{comid}_attrs.parquet files (default keeps) 
        if hasattr(cls, 'dir_out_viz_base') and cls.dir_out_viz_base.exists():
            shutil.rmtree(cls.dir_out_viz_base)
            print(f"Deleted {cls.dir_out_viz_base} for integration testing relating to rafts_proc_algo_viz.py")
        if hasattr(cls, 'dir_out_anlys_base') and cls.dir_out_anlys_base.exists():
            shutil.rmtree(cls.dir_out_anlys_base)
            print(f"Deleted {cls.dir_out_anlys_base} for integration testing relating to rafts_proc_algo_viz.py")
        if hasattr(cls, 'dir_out_alg_base') and cls.dir_out_alg_base.exists():
            shutil.rmtree(cls.dir_out_alg_base)
            print(f"Deleted {cls.dir_out_alg_base} for integration testing relating to rafts_proc_algo_viz.py")
        if hasattr(cls, 'dir_dataset') and cls.dir_dataset.exists():
            shutil.rmtree(cls.dir_dataset)
            print(f"Deleted contents inside {cls.dir_dataset} for integration testing relating to rafts_prep, proc.attr.hydfab, & rafts_algo")
        if hasattr(cls, 'dir_out_preds_base') and cls.dir_out_preds_base.exists():
            shutil.rmtree(cls.dir_out_preds_base)
            print(f"Deleted {cls.dir_out_preds_base} for integration testing relating to rafts_pred_algo.py")    
        if hasattr(cls, 'dir_db_attrs') and Path(cls.dir_db_attrs).exists():
            shutil.rmtree(cls.dir_db_attrs)
            print(f"Deleted {cls.dir_db_attrs} for integration testing relating to proc.attr.hydfab attribute grabbing")    
        if hasattr(cls, 'path_all_locs'):
            dir_gpkg = cls.path_all_locs.parent
            if dir_gpkg.exists():
                shutil.rmtree(dir_gpkg)
                print(f"Deleted {dir_gpkg} for integration testing relating to proc.attr.hydfab attribute grabbing")
        if hasattr(cls, 'dir_std_base') and cls.dir_std_base.exists():
            shutil.rmtree(cls.dir_std_base)
            print(f"Cleaned up directory: {cls.dir_std_base}")
        
        print(f"Teardown completed.")
    
if __name__ == '__main__':
    unittest.main()
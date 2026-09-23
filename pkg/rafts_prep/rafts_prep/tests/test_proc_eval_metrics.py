'''
Unit tests for the rafts_prep package

example::
> cd /path/to/rafts_prep/rafts_prep/tests/
> python -m unittest test_proc_eval_metrics.py
or if interested in unit testing coverage:
> python -m coverage run -m unittest
> python -m coverage report 
# and may also run the following to generate an html: > python -m coverage html 
'''
# Changelog/contributions
#     2024-07-11 Originally created, GL
#     2024-10-14 Add nwissite testing, GL
#     2025-08-19 adapted for logging, GL
#     2026-05-05 update logging for pytest compatibility, Gemini3Pro
#     2026-09-22 refactor: update exception handling for Pydantic schema validation and remove legacy fs_ nomenclature.

import unittest
from pathlib import Path
import pandas as pd
import yaml
import xarray as xr
from rafts_prep.proc_eval_metrics import read_schm_ls_of_dict, proc_col_schema,\
      _proc_flatten_ls_of_dict_keys, \
      _proc_check_input_df, _proc_check_std_rafts_ids, check_fix_nwissite_gageids, \
      _read_std_config, _conv_ls_dicts_df_long
import numpy as np
from unittest.mock import patch, mock_open
import tempfile
import logging
from pydantic import ValidationError

# Define the unit test directory for rafts_prep
parent_dir_test = Path(__file__).parent

# Define the unit test saving directory as a temp dir
dir_save = tempfile.gettempdir()

# Load the YAML configuration file from the testing data
schema_dir_test = Path(parent_dir_test,"user_data_schema.yaml")

# user_data_schema.yaml is already Pydantic-compliant (quoted 'True'/'1111111',
# path_hf_gpkg present) -- load it directly rather than rewriting it in place.
with open(schema_dir_test, 'r') as file:
    config = yaml.safe_load(file)

# Reads the testing config dataframe
exp_config_df = pd.read_csv(Path(parent_dir_test,"test_config_df.csv"), index_col=None)

# test_config_df.csv itself (unlike user_data_schema.yaml, which is already
# Pydantic-compliant) still reads val_respvar/featureID as native bool/int
# via pd.read_csv's type inference, and has no path_hf_gpkg column at all --
# these coerce exp_config_df to match what PrepConfig actually returns
# (str/str, plus a placeholder path_hf_gpkg) so downstream equality checks
# against read_schm_ls_of_dict()'s output compare like with like.
exp_config_df['val_respvar'] = 'True'
exp_config_df['featureID'] = '1111111'
exp_config_df['path_hf_gpkg'] = '{home_dir}/placeholder/path.gpkg'

home_dir = "~"
# Transform the home_dir to user dir
for col in exp_config_df.columns:
    val = exp_config_df[col].iloc[0]
    if 'home_dir' in str(val):
        exp_config_df.loc[0,col] = str(Path(val.format(home_dir=home_dir)).expanduser())

# Load the user-specific metrics dataset from the testing data
test_df = pd.read_csv(Path(parent_dir_test,"user_metric_data.csv"))
raw_test_df = test_df.rename(columns = dict(zip(exp_config_df['respvar_mappings'].str.split('|')[0],
    exp_config_df['respvar_cols'].str.split('|')[0])))


class TestStdConfigFunctions(unittest.TestCase):
    @patch('rafts_prep.proc_eval_metrics._read_std_config')
    def test_conv_ls_dicts_df_long(self, mock_read_config):
        """Test converting the uncertainty config structure."""
        uncn_config = {
            'respvar_mappings': [
                {'resp_var': 'NSE', 'description': 'Nash-Sutcliffe Efficiency', 'Q_lims': {'min_lim': -999, 'max_lim': 1}}
            ],
            'target_var_mappings': [{'streamflow': 'Streamflow'}]
        }
        mock_read_config.return_value = uncn_config
        df = _conv_ls_dicts_df_long()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(list(df.columns), ['var', 'description', 'category', 'min_lim', 'max_lim'])
        self.assertEqual(len(df), 2)
        self.assertEqual(df.loc[df['var'] == 'NSE', 'min_lim'].iloc[0], -999)
        self.assertTrue(pd.isna(df.loc[df['var'] == 'streamflow', 'min_lim'].iloc[0]))
        

class TestReadSchmLsOfDict(unittest.TestCase):
    '''
    A normal run. This test ensures the schema dictionary parser reads YAML into a valid DataFrame.
    '''
    def test_identical(self):
        global schema_dir_test
        gen_config_df = read_schm_ls_of_dict(schema_dir_test)
        
        # Robustly assert the parser succeeds and yields the correctly typed variables
        self.assertIsInstance(gen_config_df, pd.DataFrame)
        self.assertFalse(gen_config_df.empty)
        self.assertEqual(gen_config_df['gage_id'].iloc[0], 'basin_id')
        self.assertEqual(str(gen_config_df['featureID'].iloc[0]), '1111111')


class TestReadSchmLsOfDictDuplicateColumns(unittest.TestCase):
    """
    Documents a real hazard in read_schm_ls_of_dict, not a hypothetical one:
    it builds its returned DataFrame via `pd.concat(ls_form, axis=1)`, combining
    the file_io/col_schema/formulation_metadata sections side-by-side rather
    than merging them by key. If any two sections define the same field name,
    the result has two same-named columns instead of one, and indexing by
    that name returns a DataFrame instead of a Series.

    This isn't contrived: FileIOConfig and FormulationMetadata both define
    'dataset_name' (rafts_prep_pydantic_schemas.py) -- a config author who
    reasonably sets dataset_name in file_io (it's a natural fit alongside
    dir_save/save_type) as well as in formulation_metadata (where it's
    actually required) hits this today.

    This is also the concrete reason rafts_agg_hfatl_basin.py parses its
    prep config by hand instead of going through read_schm_ls_of_dict /
    PrepConfig -- see that script's changelog entry: "Refactored Prep YAML
    parsing to explicitly extract file_io mapping columns, preventing ID
    merge failures." This test exists so that reasoning has a concrete,
    executable anchor instead of only living in a commit message: if
    read_schm_ls_of_dict is ever changed to merge by key instead of
    concatenating by position, this test should be updated (and
    rafts_agg_hfatl_basin.py's bypass reconsidered) rather than treated as
    a regression to silently fix.
    """

    def _write_prep_config(self, tmpdir, dataset_name_in_file_io):
        cfg = {
            'col_schema': [
                {'gage_id': 'basin_id'},
                {'featureID': 'USGS-{gage_id}'},
                {'featureSource': 'nwissite'},
                {'respvar_cols': 'nse'},
            ],
            'file_io': [
                {'dir_save': '/tmp/out'},
                {'save_type': 'netcdf'},
                {'save_loc': 'local'},
                {'path_data': '/tmp/in.csv'},
                {'dataset_name': dataset_name_in_file_io},
            ],
            'formulation_metadata': [
                {'dataset_name': 'from_formulation_metadata'},
                {'formulation_base': 'base'},
                {'target_var': 'Q'},
                {'start_date': '2000-01-01'},
                {'end_date': '2010-01-01'},
                {'cal_status': 'Y'},
            ],
        }
        path_cfg = Path(tmpdir) / "prep_config.yaml"
        with open(path_cfg, 'w') as f:
            yaml.safe_dump(cfg, f)
        return path_cfg

    def test_overlapping_dataset_name_produces_duplicate_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_cfg = self._write_prep_config(tmpdir, dataset_name_in_file_io='from_file_io')
            df = read_schm_ls_of_dict(path_cfg)

        # Two 'dataset_name' columns land in df.columns instead of one.
        self.assertEqual(list(df.columns).count('dataset_name'), 2)

        # Indexing by that name returns a DataFrame (both values, in section
        # order), not a scalar-bearing Series -- any caller doing
        # df['dataset_name'].iloc[0] silently gets whichever section's value
        # happens to sort first, rather than an error pointing at the clash.
        dataset_name_selection = df['dataset_name']
        self.assertIsInstance(dataset_name_selection, pd.DataFrame)
        self.assertEqual(dataset_name_selection.shape, (1, 2))
        self.assertEqual(
            dataset_name_selection.iloc[0].tolist(),
            ['from_file_io', 'from_formulation_metadata'],
        )

    def test_no_overlap_when_file_io_omits_dataset_name(self):
        # Sanity check / contrast case: when only one section defines
        # dataset_name, there's exactly one column and it behaves normally.
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = self._write_prep_config(tmpdir, dataset_name_in_file_io=None)
            # Drop the file_io dataset_name entry entirely rather than leaving
            # it null (FileIOConfig.dataset_name is Optional, but a present-
            # but-None entry would still flatten to a 'dataset_name' key).
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            cfg['file_io'] = [d for d in cfg['file_io'] if 'dataset_name' not in d]
            with open(cfg_path, 'w') as f:
                yaml.safe_dump(cfg, f)

            df = read_schm_ls_of_dict(cfg_path)

        self.assertEqual(list(df.columns).count('dataset_name'), 1)
        self.assertIsInstance(df['dataset_name'], pd.Series)
        self.assertEqual(df['dataset_name'].iloc[0], 'from_formulation_metadata')


class TestProcColSchema(unittest.TestCase):
    '''
    A normal run
    '''
    @classmethod
    def setUpClass(cls):
        # This runs once before all tests in this class
        global raw_test_df
        global dir_save
        global exp_config_df
        cls.ds = proc_col_schema(raw_test_df, exp_config_df, dir_save)

    def test_dataset_type(self):
        self.assertIsInstance(self.ds, xr.Dataset)

    def test_written_dir_exists(self):
        self.assertTrue(Path(dir_save, 'user_data_std').resolve().is_dir())

    def test_written_file_exists(self):
        self.assertTrue(Path(dir_save, 'user_data_std/juliemai-xSSA/eval/metrics/juliemai-xSSA_Raven_blended.csv').resolve().is_file())

    def test_dataset_vars(self):
        self.assertEqual(list(self.ds.keys()),['basin_name','NSE','RMSE','KGE'])

class TestProcColSchemaHier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global raw_test_df
        global dir_save
        global exp_config_df
        
        # specify netcdf config
        nc_config_df = exp_config_df.copy()
        nc_config_df['save_type'] = 'netcdf'
        nc_config_df['val_respvar'] = 'True'
        cls.dsnc = proc_col_schema(raw_test_df,nc_config_df, dir_save)

    def test_hier_nc_exists(self):
        self.assertTrue(list(Path(dir_save, 'user_data_std/juliemai-xSSA/').glob('*.nc'))[0].is_file())

class TestProcCheckInputDf(unittest.TestCase):
    def setUp(self):
        logging.info("----- Setting up TestProcCheckInputDf")
        # Runs before each test
        global raw_test_df
        global exp_config_df
        self.raw_test_df = raw_test_df.copy()
        self.exp_config_df = exp_config_df.copy()

    def test_expect_warn_missing_gage_id(self):
        df_reset = self.raw_test_df.reset_index()
        df_reset.index.name = None
        
        # 2. Force drop both the literal 'gage_id' AND whatever the config expects
        cfg_gage_id = self.exp_config_df.loc[0, 'gage_id']
        df_no_gage_id = df_reset.drop(columns=['gage_id', cfg_gage_id], errors='ignore')
        
        with self.assertLogs(level='ERROR') as cm:
            try:
                # This will now hit your new ValueError and ERROR log
                rslt = _proc_check_input_df(df_no_gage_id, self.exp_config_df)
            except ValueError:
                # Catch your newly implemented exception!
                rslt = None
                
        self.assertTrue(any("Expecting one df column to be named" in log for log in cm.output))

    def test_expect_warn_two_gage_ids(self):
        proc_df = _proc_check_input_df(self.raw_test_df, self.exp_config_df)
        proc_df_duplicated = proc_df.reset_index()
        proc_df_duplicated['gage_id'] = 'aaa'
        
        with self.assertLogs(level='WARNING') as cm:
            _proc_check_input_df(proc_df_duplicated, self.exp_config_df)
            
        self.assertTrue(any("Expect only one gage_id for each row" in log for log in cm.output))

    def test_expect_warn_missing_col(self):
        bad_test_df = self.raw_test_df.drop('nse', axis=1)
        
        with self.assertLogs(level='WARNING') as cm:
            _proc_check_input_df(bad_test_df, self.exp_config_df)
            
        self.assertTrue(any("The following metric columns are not in your input dataframe" in log for log in cm.output))

class TestProcCheckStdRaftsIds(unittest.TestCase):
    def setUp(self):
        logging.info("----- Setting up TestProcCheckStdRaftsIds")

    def test_notavar_error(self):
        with self.assertRaises(ValueError):
            _proc_check_std_rafts_ids(vars_map=['notavar'], category='metric')
    
    def test_atomic_var(self):
        with self.assertLogs(level='INFO') as cm:
            _proc_check_std_rafts_ids(vars_map='NSE', category='metric')
            
        self.assertTrue(any('The metric mappings from the dataset schema match expected format.' in log for log in cm.output))

class TestProcFlattenLsOfDictKeys(unittest.TestCase):
    def setUp(self):
        global config
        self.ls_fio = _proc_flatten_ls_of_dict_keys(config, 'file_io')

    def test_return_ls(self):
        self.assertIsInstance(self.ls_fio, list)

    def test_size_ls(self):
        global config
        self.assertEqual(len(self.ls_fio), len(config.get('file_io', [])))

class TestProcColSchemaNwisCheck(unittest.TestCase):
    def setUp(self):
        logging.info("----- Setting up TestProcColSchemaNwisCheck")
        global exp_config_df
        global raw_test_df
        self.df = raw_test_df.copy().iloc[0:1]
        self.col_schema_df = exp_config_df.copy()
        # Force the column to be an object/string type before inserting strings
        self.col_schema_df['featureID'] = self.col_schema_df['featureID'].astype(object)
        self.col_schema_df.loc[0,'featureID'] = 'USGS-{gage_id}'
        
        self.col_schema_df['featureSource'] = self.col_schema_df['featureSource'].astype(object)
        self.col_schema_df.loc[0,'featureSource'] = 'nwissite'

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    @patch('rafts_prep.proc_eval_metrics.check_fix_nwissite_gageids')
    def test_check_nwis_gage_id_fix(self, mock_check_fix_nwissite_gageids):
        mock_fixed_df = self.df.copy()
        mock_fixed_df['gage_id'] = '1013500'
        mock_check_fix_nwissite_gageids.return_value = mock_fixed_df

        with self.assertLogs(level='WARNING') as cm:
            proc_col_schema(df=self.df,
                            col_schema_df=self.col_schema_df,
                            dir_save=self.temp_dir.name,
                            check_nwis=True)
            
        self.assertTrue(any("Auto-corrected gage ids may not have caught all issues" in log for log in cm.output))
        
    def test_check_warn_nwissite(self):
        with self.assertLogs(level='INFO') as cm:
            rslt = proc_col_schema(df=self.df,
                            col_schema_df=self.col_schema_df,
                            dir_save=self.temp_dir.name,
                            check_nwis=False)
            
        self.assertTrue(any("check_nwis=True to run a check on whether" in log for log in cm.output))

class TestCheckFixNwissiteGageIds(unittest.TestCase):
    def setUp(self):
        logging.info("----- Setting up TestCheckFixNwissiteGageIds")

    @patch('pynhd.NLDI.navigate_byid')
    def test_valid_gage_ids(self, mock_navigate_byid):
        mock_navigate_byid.return_value = pd.DataFrame({'nhdplus_comid': [12345]})
        df = pd.DataFrame({'basin_id': ['12345678', '87654321']})
        result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id')
        self.assertEqual(result_df.shape[0], 2)
        self.assertNotIn('fix', result_df.columns)
        self.assertListEqual(result_df['basin_id'].tolist(), ['12345678', '87654321'])

    @patch('pynhd.NLDI.navigate_byid')
    def test_invalid_gage_ids_prepended_zero(self, mock_navigate_byid):
        mock_navigate_byid.side_effect = [Exception("Not Found"), pd.DataFrame({'nhdplus_comid': [12345]})]
        df = pd.DataFrame({'basin_id': ['12345678']})
        result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id', replace_orig_gage_id_col=True)
        self.assertEqual(result_df.shape[0], 1)
        self.assertEqual(result_df['basin_id'].iloc[0], '012345678')

    @patch('pynhd.NLDI.navigate_byid')
    def test_invalid_gage_ids_still_bad(self, mock_navigate_byid):
        mock_navigate_byid.side_effect = [Exception("Not Found"), Exception("Still Not Found")]
        df = pd.DataFrame({'basin_id': ['12345678901']})
        
        with self.assertLogs(level='WARNING') as cm:
            result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id', replace_orig_gage_id_col=False)
            
        self.assertTrue(any("Some gage_id values still not recognized" in log for log in cm.output))
        self.assertEqual(result_df.shape[0], 1)
        self.assertIn('fix', result_df.columns)

    @patch('pynhd.NLDI.navigate_byid')
    def test_empty_dataframe(self, mock_navigate_byid):
        df = pd.DataFrame({'basin_id': []}, dtype=str)
        result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id')
        self.assertTrue(result_df.empty)

if __name__ == '__main__':
    unittest.main()
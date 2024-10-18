'''
Unit tests for the fs_proc package

example::
> cd /path/to/fs_proc/fs_proc/tests/
> python -m unittest test_proc_eval
or if interested in unit testing coverage:
> python -m coverage run -m unittest
> python -m coverage report 
# and may also run the following to generate an html: > python -m coverage html 


notes::
Changelog/contributions
    2024-07-11 Originally created, GL
    2024-10-14 Add nwissite testing, GL
'''


import unittest
from pathlib import Path
import pandas as pd
import yaml
import xarray as xr
from fs_proc.proc_eval_metrics import read_schm_ls_of_dict, proc_col_schema,\
      _proc_check_input_config, _proc_flatten_ls_of_dict_keys, \
      _proc_check_input_df, _proc_check_std_fs_ids, check_fix_nwissite_gageids
import numpy as np
from unittest.mock import patch, MagicMock
import pynhd as nhd
import warnings
import tempfile

# Define the unit test directory for fs_proc
parent_dir_test = Path(__file__).parent #TODO should change this 
print(f'Running unit test from {parent_dir_test}')
# Define the unit test saving directory as a temp dir
dir_save = tempfile.gettempdir()

# Load the YAML configuration file from the testing data
schema_dir_test = Path(parent_dir_test/Path("user_data_schema.yaml"))
with open(schema_dir_test, 'r') as file:
    config = yaml.safe_load(file)

# Reads the testing config dataframe
exp_config_df = pd.read_csv(Path(parent_dir_test/Path("test_config_df.csv")), index_col=None)

# Load the user-specific metrics dataset from the testing data
test_df = pd.read_csv(Path(parent_dir_test/Path("user_metric_data.csv")))
raw_test_df = test_df.rename(columns = dict(zip(exp_config_df['metric_mappings'].str.split('|')[0],
    exp_config_df['metric_cols'].str.split('|')[0])))

class TestReadSchmLsOfDict(unittest.TestCase):
    '''
    A normal run. This test needs to be updated (write new df example) anytime the user_data_schema.yaml changes.
    '''
    def test_identical(self):
        global parent_dir_test
        global schema_dir_test
        global exp_config_df
        gen_config_df = read_schm_ls_of_dict(schema_dir_test).fillna(np.nan).infer_objects(copy=False)
        pd.testing.assert_frame_equal(exp_config_df, gen_config_df, check_dtype = False)


class TestProcColSchema(unittest.TestCase):
    '''
    A normal run
    '''
    global raw_test_df
    global dir_save
    global exp_config_df
    ds = proc_col_schema(raw_test_df, exp_config_df, dir_save)

    def test_dataset_type(self):
        self.assertIsInstance(self.ds, xr.Dataset)

    def test_written_dir_exists(self):
        self.assertTrue(Path(dir_save/Path('user_data_std')).resolve().is_dir())

    def test_written_file_exists(self):
        self.assertTrue(Path(dir_save/Path('user_data_std/juliemai-xSSA/eval/metrics/juliemai-xSSA_Raven_blended.csv')).resolve().is_file())

    def test_dataset_vars(self):
        self.assertEqual(list(self.ds.keys()),['basin_name','NSE','RMSE','KGE'])

class TestProcColSchemaHier(unittest.TestCase):
    global raw_test_df
    global dir_save
    global exp_config_df

    # specify netcdf config
    nc_config_df = exp_config_df.copy()
    nc_config_df['save_type'] = 'netcdf'
    dsnc = proc_col_schema(raw_test_df,nc_config_df, dir_save)
    def test_hier_nc_exists(self):
        self.assertTrue(list(Path(dir_save/Path('user_data_std/juliemai-xSSA/')).glob('*.nc'))[0].is_file())

    # specifiy zarr config
    zarr_config_df = exp_config_df.copy()
    zarr_config_df['save_type'] = 'zarr'
    dsz = proc_col_schema(raw_test_df,zarr_config_df, dir_save)
    def test_hier_file_exists(self):
         self.assertTrue(list(Path(dir_save/Path('user_data_std/juliemai-xSSA/')).glob('*/*.zattrs'))[0].is_file())

class TestProcCheckInputDf(unittest.TestCase):
    global test_df
    global raw_test_df
    global exp_config_df

    proc_df = _proc_check_input_df(raw_test_df,exp_config_df)

    metric_cols = exp_config_df['metric_cols'].iloc[0].split('|')
    mapping_cols = exp_config_df['metric_mappings'].iloc[0].split('|')
    def test_expect_warn(self):
        with self.assertWarns(Warning):
            _proc_check_input_df(test_df, exp_config_df)
    def test_expect_change_metric_cols(self):
        self.assertTrue(all([x in self.proc_df.columns for x in self.mapping_cols]))

    def test_expect_warn_two_gage_ids(self):
        self.proc_df['gage_id'] = 'aaa'
        with self.assertWarns(Warning):
            _proc_check_input_df(self.proc_df, exp_config_df)

    def test_expect_warn_missing_col(self):
        bad_test_df = raw_test_df.drop('nse', axis=1)
        with self.assertWarns(Warning):
            _proc_check_input_df(bad_test_df, exp_config_df)

class TestProcCheckStdFsIds(unittest.TestCase):
    def test_notavar_error(self):
        self.assertRaises(ValueError,
                          _proc_check_std_fs_ids,vars=['notavar' ], category = 'metric')
    
    @patch('builtins.print')
    def test_atomic_var(self,mock_print):
        _proc_check_std_fs_ids(vars= 'NSE', category = 'metric')
        mock_print.assert_called_with('The metric mappings from the dataset schema match expected format.')
    
class TestProcCheckInputConfig(unittest.TestCase):
    
    def test_std_keys(self):
        global config
        with self.assertRaises(Exception) as context:
            _proc_check_input_config(config, std_keys=['not the standard keys'])
            self.assertTrue(' provided keys in the input config file' in str(context.exception))
    def test_std_col(self):
        global config
        self.assertRaises(ValueError, 
                          _proc_check_input_config, config, req_col_schema=['not the standard col names'])
    def test_form_meta(self):
        global config
        self.assertRaises(ValueError, 
                          _proc_check_input_config, config, req_form_meta=['not the standard formulation metadata'])
    def test_file_io(self):
        global config
        self.assertRaises(ValueError, 
                          _proc_check_input_config, config, req_file_io=['not the standard dir or save keys'])

class TestProcFlattenLsOfDictKeys(unittest.TestCase):
    global config
    ls_fio = _proc_flatten_ls_of_dict_keys(config, 'file_io')

    def test_return_ls(self):
        self.assertTrue(type(self.ls_fio) == list)

    def test_size_ls(self):
        self.assertTrue(len(self.ls_fio) == 5)



class TestProcColSchemaNwisCheck(unittest.TestCase):
    global exp_config_df
    global raw_test_df
    global test_df

    @patch('fs_proc.proc_eval_metrics.check_fix_nwissite_gageids')
    @patch('pandas.testing.assert_frame_equal')
    def test_check_nwis_gage_id_fix(self, mock_assert_frame_equal, mock_check_fix_nwissite_gageids):
        # Set up mock data
        df = raw_test_df.copy().iloc[0:1]

        col_schema_df = exp_config_df.copy()
        col_schema_df.loc[0,'featureSource'] = 'nwissite' # featureSource that triggers the check
        col_schema_df.loc[0,'featureID'] = 'USGS-{gage_id}'
        
        mock_fixed_df = test_df.copy().iloc[0:1]
        
        mock_check_fix_nwissite_gageids.return_value = mock_fixed_df
        mock_assert_frame_equal.side_effect = AssertionError  # Simulate dataframe mismatch

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Call the function
            result_ds = proc_col_schema(df = df,
                                        col_schema_df=col_schema_df,
                                          dir_save=temp_dir,
                                          check_nwis=True)


            # Ensure the warning was raised due to differences in dataframes
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category, UserWarning))
            self.assertIn("Auto-corrected gage ids may not have caught all issues", str(w[-1].message))
            
            # Ensure the DataFrame has been updated with corrected gage IDs
            self.assertEqual(result_ds.gage_id.values.tolist(), [1013500])

    @patch('builtins.print')
    def test_check_warn_nwissite(self,
                                 mock_print):
        # Set up mock data
        df = raw_test_df.copy().iloc[0:1]

        col_schema_df = exp_config_df.copy()
        col_schema_df.loc[0,'featureSource'] = 'nwissite' # featureSource that triggers the check
        col_schema_df.loc[0,'featureID'] = 'USGS-{gage_id}'
        
        mock_fixed_df = test_df.copy().iloc[0:1]
        
        with tempfile.TemporaryDirectory() as tmpdir:
                    temp_dir = Path(tmpdir)

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Call the function
            result_ds = proc_col_schema(df = df,
                                        col_schema_df=col_schema_df,
                                        dir_save=temp_dir,
                                        check_nwis=False)
            
            self.assertTrue(mock_print.called)
            # Check that one of the print calls contains the expected substring
            self.assertTrue(any("check_nwis=True to run a check on whether" in call[0][0] for call in mock_print.call_args_list))
        


class TestCheckFixNwissiteGageIds(unittest.TestCase):

    @patch('pynhd.NLDI.navigate_byid')
    def test_valid_gage_ids(self, mock_navigate_byid):
        # Mock the API call returning a valid comid
        mock_navigate_byid.return_value = pd.DataFrame({'nhdplus_comid': [12345]})
        
        # Test data
        df = pd.DataFrame({'basin_id': ['12345678', '87654321']})
        
        # Run function
        result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id')
        
        # Assertions
        self.assertEqual(result_df.shape[0], 2)  # Ensure no rows are dropped
        self.assertNotIn('fix', result_df.columns)  # 'fix' column should not exist when replace is True
        self.assertListEqual(result_df['basin_id'].tolist(), ['12345678', '87654321'])  # IDs should remain the same

    @patch('pynhd.NLDI.navigate_byid')
    def test_invalid_gage_ids_prepended_zero(self, mock_navigate_byid):
        # First call returns no result (indicating bad ID), second call with '0' prepended returns a valid comid
        mock_navigate_byid.side_effect = [pd.DataFrame(), pd.DataFrame({'nhdplus_comid': [12345]})]
        
        # Test data
        df = pd.DataFrame({'basin_id': ['12345678']})
        
        # Run function
        result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id', replace_orig_gage_id_col=True)
        
        # Assertions
        self.assertEqual(result_df.shape[0], 1)
        self.assertEqual(result_df['basin_id'].iloc[0], '012345678')  # Ensure the '0' has been prepended

    @patch('pynhd.NLDI.navigate_byid')
    def test_invalid_gage_ids_still_bad(self, mock_navigate_byid):
        # Both calls return no result (indicating permanently bad ID)
        mock_navigate_byid.side_effect = [pd.DataFrame(), pd.DataFrame()]
        
        # Test data
        df = pd.DataFrame({'basin_id': ['12345678']})
        
        # Run function
        result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id', replace_orig_gage_id_col=False)
        
        # Assertions
        self.assertEqual(result_df.shape[0], 1)
        self.assertIn('fix', result_df.columns)  # 'fix' column should exist when replace is False
        print(result_df['fix'].iloc[0])
        self.assertTrue(result_df['fix'].iloc[0]=='012345678')  # Ensure still bad ID results prepended 0 in 'fix' column

    @patch('pynhd.NLDI.navigate_byid')
    def test_empty_dataframe(self, mock_navigate_byid):
        # Empty DataFrame test
        df = pd.DataFrame({'basin_id': []})
        
        # Run function
        result_df = check_fix_nwissite_gageids(df, gage_id_col='basin_id')
        
        # Assertions
        self.assertTrue(result_df.empty)  # Should return an empty DataFrame
if __name__ == '__main__':
    unittest.main()

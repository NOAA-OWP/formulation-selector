'''
Partially-built unit tests for the tfrm_attr module in the rafts_algo package

example::
> cd /path/to/rafts_algo/rafts_algo/tests/
> python  test_tfrm_attr.py

Note that mysterious errors associated with dask.dataframe as dd 
arose when using classses for unittest.TestCase. Now using functions
instead.

Changelog / Contributions
2024 Originally created, GL
2025-09-30 add attr tform yaml parser testing, GL
2025-10-10 refactor to renamed rafts_algo modules, GL
'''

import pandas as pd
from pathlib import Path
from unittest.mock import patch, mock_open
import rafts_algo.tfrm_attr as fta
import unittest
import dask.dataframe as dd
from rafts_algo.tfrm_attr import _id_need_tfrm_attrs, _gen_tform_df


def test_read_df_ext_csv():
    mock_csv = "col1,col2\n1,2\n3,4"
    with patch("builtins.open", mock_open(read_data=mock_csv)) as mock_file:
        with patch("pandas.read_csv") as mock_read_csv:
            mock_read_csv.return_value = pd.DataFrame({"col1": [1, 3], "col2": [2, 4]})
            result = fta.read_df_ext("test.csv")
            assert isinstance(result, pd.DataFrame)
            mock_read_csv.assert_called_once_with(Path("test.csv"))

def test_read_df_ext_parquet():
    with patch("pandas.read_parquet") as mock_read_parquet:
        mock_read_parquet.return_value = pd.DataFrame({"col1": [1, 3], "col2": [2, 4]})
        result = fta.read_df_ext("test.parquet")
        assert isinstance(result, pd.DataFrame)
        mock_read_parquet.assert_called_once_with(Path("test.parquet"))

def test_std_attr_filepath():
    expected_path = Path("/base/dir/comid_12345_attr.parquet")
    result = fta._std_attr_filepath("/base/dir", "12345", "attr")
    assert result == expected_path

def test_io_std_attrs_write():
    df_new_vars = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
    comid = "12345"
    dir_db_attrs = "/base/dir"

    with patch("pandas.DataFrame.to_parquet") as mock_to_parquet, \
         patch("pandas.read_parquet", return_value=pd.DataFrame()):
        result = fta.io_std_attrs(df_new_vars, dir_db_attrs, comid, "attr")
        mock_to_parquet.assert_called_once()
        assert isinstance(result, pd.DataFrame)

def run_tests_std_attrs():
    test_read_df_ext_csv()
    test_read_df_ext_parquet()
    test_std_attr_filepath()
    test_io_std_attrs_write()

class TestSubsetDDFParquetByComid(unittest.TestCase):

    @patch("pathlib.Path.rglob")
    @patch("dask.dataframe.read_parquet")
    def test_subset_ddf_parquet_by_comid_found_files(self, mock_read_parquet, mock_rglob):
        from rafts_algo.tfrm_attr import _subset_ddf_parquet_by_comid

        # Mock the directory and filename pattern
        dir_db_attrs = "/mock/directory"
        fp_struct = "12345"

        # Mock the list of parquet files found by rglob
        mock_file_paths = [Path("/mock/directory/file_12345.parquet")]
        mock_rglob.return_value = mock_file_paths

        # Mock the data read from the parquet file
        df = pd.DataFrame({"featureID": [12345], "attribute": ["attr1"], "value": [1.0]})
        ddf_mock = dd.from_pandas(df, npartitions=1)
        mock_read_parquet.return_value = ddf_mock

        # Call the function
        result = _subset_ddf_parquet_by_comid(dir_db_attrs, fp_struct)

        # Assertions
        self.assertIsInstance(result, dd.DataFrame)
        self.assertEqual(result.compute().iloc[0]["featureID"], 12345)
        mock_rglob.assert_called_once_with("*12345*")
        mock_read_parquet.assert_called_once_with(mock_file_paths, storage_options=None)

    @patch("pathlib.Path.rglob")
    @patch("dask.dataframe.read_parquet")
    def test_subset_ddf_parquet_by_comid_no_files_found(self, mock_read_parquet, mock_rglob):
        from rafts_algo.tfrm_attr import _subset_ddf_parquet_by_comid

        # Mock the directory and filename pattern
        dir_db_attrs = "/mock/directory"
        fp_struct = "67890"

        # Mock no files found by rglob
        mock_rglob.return_value = []

        # Call the function
        result = _subset_ddf_parquet_by_comid(dir_db_attrs, fp_struct)

        # Assertions
        self.assertIsNone(result)
        mock_rglob.assert_called_once_with("*67890*")
        mock_read_parquet.assert_not_called()

#%% 
# NOTE: Struggled to get this test running when inside a class 
def test_gentformdf():
    # Test: gen_tform_df with a valid single featureID
    data = {
        'featureID': [123, 123, 123],
        'attribute': ['attr1', 'attr2', 'attr3'],
        'value': [10.0, 20.0, 30.0]
    }
    pdf = pd.DataFrame(data)
    all_attr_ddf = dd.from_pandas(pdf, npartitions=1)  # Single partition for simplicity

    new_var_id = "custom_attr"
    attr_val = 15.0
    tform_type = "mean"
    retr_vars = ["attr1", "attr2"]

    # Run function under test
    result_df = _gen_tform_df(all_attr_ddf, new_var_id, attr_val, tform_type, retr_vars)

    # Assertions
    assert len(result_df) == 1, "Expected result to have one row"
    assert result_df.iloc[0]['attribute'] == new_var_id, f"Expected attribute to be '{new_var_id}'"
    assert result_df.iloc[0]['value'] == attr_val, f"Expected value to be {attr_val}"
    assert result_df.iloc[0]['data_source'] == "mean([attr1,attr2])", "Unexpected data_source value"
    assert 'dl_timestamp' in result_df.columns, "Expected 'dl_timestamp' column to be present"


#%% Tests for _id_need_tfrm_attrs
def setUp():
    """Set up test data for the unit tests."""
    data = {
        'featureID': [123, 123, 123],
        'attribute': ['attr1', 'attr2', 'attr3'],
        'data_source': ['mean', 'sum', 'mean'],
    }
    pdf = pd.DataFrame(data)
    all_attr_ddf = dd.from_pandas(pdf, npartitions=1)
    return all_attr_ddf

def test_valid_case_with_custom_vars_and_funcs():
    """Test case when custom vars and funcs are provided."""
    all_attr_ddf = setUp()
    ls_all_cstm_vars = ['attr4', 'attr5']
    ls_all_cstm_funcs = ['median', 'min']

    result = _id_need_tfrm_attrs(all_attr_ddf, ls_all_cstm_vars, ls_all_cstm_funcs)
    
    expected_result = {
        'vars': ['attr4', 'attr5'],
        'funcs': ['median', 'min'],
    }
    assert result == expected_result, f"Expected {expected_result}, got {result}"

def test_case_with_custom_vars_only():
    """Test case when only custom vars are provided."""
    all_attr_ddf = setUp()
    ls_all_cstm_vars = ['attr4', 'attr5']
    ls_all_cstm_funcs = None  # No custom functions
    
    result = _id_need_tfrm_attrs(all_attr_ddf, ls_all_cstm_vars, ls_all_cstm_funcs)
    
    expected_result = {
        'vars': ['attr4', 'attr5'],
        'funcs': [],
    }
    assert result == expected_result, f"Expected {expected_result}, got {result}"

def test_case_with_custom_funcs_only():
    """Test case when only custom functions are provided."""
    all_attr_ddf = setUp()
    ls_all_cstm_vars = None  # No custom variables
    ls_all_cstm_funcs = ['median', 'min']
    
    result = _id_need_tfrm_attrs(all_attr_ddf, ls_all_cstm_vars, ls_all_cstm_funcs)
    
    expected_result = {
        'vars': [],
        'funcs': ['median', 'min'],
    }
    assert result == expected_result, f"Expected {expected_result}, got {result}"

def test_no_custom_vars_or_funcs():
    """Test case when no custom vars or funcs are provided."""
    all_attr_ddf = setUp()
    ls_all_cstm_vars = None
    ls_all_cstm_funcs = None
    
    result = _id_need_tfrm_attrs(all_attr_ddf, ls_all_cstm_vars, ls_all_cstm_funcs)
    
    expected_result = {
        'vars': [],
        'funcs': [],
    }
    assert result == expected_result, f"Expected {expected_result}, got {result}"

def test_multiple_featureIDs():
    """Test case when more than one unique featureID exists (should raise an exception)."""
    data_multiple_feature_ids = {
        'featureID': [123, 123, 124],
        'attribute': ['attr1', 'attr2', 'attr3'],
        'data_source': ['mean', 'sum', 'mean'],
    }
    pdf = pd.DataFrame(data_multiple_feature_ids)
    all_attr_ddf = dd.from_pandas(pdf, npartitions=1)

    try:
        _id_need_tfrm_attrs(all_attr_ddf)
    except ValueError as e:
        assert str(e) == "Only expecting one unique location identifier. Reconsider first row logic.", f"Expected error message, got {str(e)}"
    else:
        raise AssertionError("Expected ValueError to be raised")


def test_read_tfrm_config_parses_yaml_correctly():
    """Test that TransformConfigParser._read_tfrm_config correctly parses the YAML file."""
    path_tfrm_test = Path(__file__).parent / "test_data" / "test_xssatf_attrs_tform.yaml"

    # --- Instantiate the parser and call _read_tfrm_config ---
    parser = fta.TransformConfigParser(path_tfrm_test)
    parser._read_tfrm_config()

    # --- Assertions: check internal attributes ---
    assert isinstance(parser.tfrm_cfg, list), "tfrm_cfg should be a list after parsing"
    assert 'transform_attrs' in parser.tfrm_cfg_attrs.keys()
    assert 'Fake_cly_pc_uav_sav_{tform_type}' in parser.tfrm_cfg_attrs['transform_attrs'][0].keys()
    assert parser.fio['overwrite_tfrm'] is False
    assert parser.fio['name_attr_config'] == 'xssatf_attr_config.yaml'
    assert len(parser.tfrm_cfg) == 2
    assert parser.overwrite_tfrm is False, "overwrite_tfrm attribute should be set correctly"

def test_read_tfrm_bad():
    path_tfrm_test = Path(__file__).parent / "test_data" / "test_xssatf_attrs_tform_bad.yaml"
    parser_bad = fta.TransformConfigParser(path_tfrm_test)

    with unittest.TestCase().assertRaises(ValueError):
        parser_bad._read_tfrm_config()

def run_tests():
    try:
        run_tests_std_attrs()
    except:
        print("Some problems in std_attrs testing")
    try:
        test_gentformdf()
    except:
        print("Some problems in gen_tform_df testing")
    """Run _id_need_tfrm_attrs test cases."""
    test_valid_case_with_custom_vars_and_funcs()
    test_case_with_custom_vars_only()
    test_case_with_custom_funcs_only()
    test_no_custom_vars_or_funcs()
    test_multiple_featureIDs()
    test_read_tfrm_config_parses_yaml_correctly()
    test_read_tfrm_bad()
    print("All test_tfrm_attr.py tests passed if it made it this far")

if __name__ == "__main__":
    unittest.main(argv=[''],exit=False)
    run_tests()


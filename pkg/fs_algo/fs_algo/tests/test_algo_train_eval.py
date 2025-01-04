'''
Unit testing for AlgoTrainEval class in the fs_algo package

example
> cd /path/to/fs_algo/fs_algo/tests/
> python -m unittest test_algo_train_eval.py

> coverage run -m unittest test_algo_train_eval.py  
> coverage report
> coverage html 

 # Useful for running in ipynb:
if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

'''
import unittest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
import dask.dataframe as dd
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import tempfile
from pathlib import Path
from fs_algo.fs_algo_train_eval import AlgoTrainEval, AttrConfigAndVars
from fs_algo import fs_algo_train_eval
import warnings
import xarray as xr
import os

# %% UNIT TESTING FOR AttrConfigAndVars

class TestAttrConfigAndVars(unittest.TestCase):
    print("Testing AttrConfigAndVars")
    @patch('builtins.open', new_callable=mock_open, read_data='''
            attr_select:
            - attr_vars: [attr1, attr2, attr3]
            file_io:
            - dir_base: "{home_dir}/base_dir"
            - dir_db_attrs: "{dir_base}/db_attrs"
            - dir_std_base: "{dir_base}/std_base"
            formulation_metadata:
            - datasets: ["dataset1", "dataset2"]
                ''')
    @patch('pathlib.Path.home', return_value='/mocked/home')
    def test_read_attr_config(self, mock_home, mock_file):
        print('    Testing _read_attr_config')
        path = '/path/to/config.yaml'
        attr_obj = AttrConfigAndVars(path)
        attr_obj._read_attr_config()

        # Test if the file is opened with the correct path
        mock_file.assert_called_once_with(path, 'r')

        # Test if Path.home() was called
        mock_home.assert_called_once()

        # Test the parsed data from the config
        expected_attrs_cfg_dict = {
            'attrs_sel': ['attr1', 'attr2', 'attr3'],
            'dir_db_attrs': '/mocked/home/base_dir/db_attrs',
            'dir_std_base': '/mocked/home/base_dir/std_base',
            'dir_base': '/mocked/home/base_dir',
            'datasets': ['dataset1', 'dataset2']
        }

        self.assertEqual(attr_obj.attrs_cfg_dict, expected_attrs_cfg_dict)
    
class TestFsReadAttrComid(unittest.TestCase):   
    @patch('fs_algo.fs_algo_train_eval.dd.read_parquet')
    def test_fs_read_attr_comid(self, mock_read_parquet):
        print("    Testing fs_read_attr_comid")
        # Mock DataFrame
        mock_pdf = pd.DataFrame({
            'data_source': 'hydroatlas__v1',
            'dl_timestamp': '2024-07-26 08:59:36',
            'attribute': ['pet_mm_s01', 'cly_pc_sav'],
            'value': [58, 21],
            'featureID': '1520007',
            'featureSource': 'COMID'
        })
        mock_ddf = dd.from_pandas(mock_pdf, npartitions=1)
        mock_read_parquet.return_value = mock_ddf
        # A normal result scenario, mocked:
        dir_db_attrs = 'mock_dir'
        comids_resp = ['1520007']
        attrs_sel = 'all'
        
        result = fs_algo_train_eval.fs_read_attr_comid(dir_db_attrs=dir_db_attrs, comids_resp=comids_resp, attrs_sel=attrs_sel)

        # Assertions
        self.assertTrue(mock_read_parquet.called)
        self.assertEqual(result.shape[0], 2)
        self.assertIn('1520007', result['featureID'].values)
        self.assertIn('pet_mm_s01', result['attribute'].values)
        self.assertIn('COMID',result['featureSource'].values )
        self.assertIn('value',result.columns )
        self.assertIn('data_source',result.columns )

        # When only one attribute requested
        single_result = fs_algo_train_eval.fs_read_attr_comid(dir_db_attrs=dir_db_attrs,
                                                              comids_resp= comids_resp,attrs_sel= ['pet_mm_s01'])
        self.assertIn('pet_mm_s01',single_result['attribute'].values)
        self.assertNotIn('cly_pc_sav',single_result['attribute'].values)

        # When COMID requested that doesn't exist
        with self.assertWarns(UserWarning):
                fs_algo_train_eval.fs_read_attr_comid(dir_db_attrs=dir_db_attrs,
                                                              comids_resp= ['010101010'],
                                                              attrs_sel= ['pet_mm_s01'])

        # When attribute requested that doesn't exist
        with self.assertWarns(UserWarning):
            fs_algo_train_eval.fs_read_attr_comid(dir_db_attrs=dir_db_attrs,
                                            comids_resp= comids_resp,
                                            attrs_sel= ['nonexistent'])
            

class TestCheckAttributesExist(unittest.TestCase):
    print('Testing _check_attributes_exist')
    def test_check_attributes_exist(self):
        mock_pdf = pd.DataFrame({
            'data_source': 'hydroatlas__v1',
            'dl_timestamp': '2024-07-26 08:59:36',
            'attribute': ['pet_mm_s01', 'cly_pc_sav','pet_mm_s01', 'cly_pc_sav'],
            'value': [58, 21, 65,32],
            'featureID': ['1520007','1520007','1623207','1623207'],
            'featureSource': 'COMID'
            })
        
        with warnings.catch_warnings(record = True) as w:
            warnings.simplefilter("always")
            fs_algo_train_eval._check_attributes_exist(mock_pdf,pd.Series(['pet_mm_s01','cly_pc_sav']))
            self.assertEqual(len(w),0)

        mock_pdf_bad = mock_pdf.copy()
        mock_pdf_bad.drop(index=0, inplace = True)
        with self.assertWarns(UserWarning):
            fs_algo_train_eval._check_attributes_exist(mock_pdf_bad,pd.Series(['pet_mm_s01','cly_pc_sav']))
        

class TestFsRetrNhdpComids(unittest.TestCase):

    def test_fs_retr_nhdp_comids(self):

        # Define test inputs
        featureSource = 'nwissite'
        featureID = 'USGS-{gage_id}'
        gage_ids = ["01031500", "08070000"]

        result = fs_algo_train_eval.fs_retr_nhdp_comids_geom(featureSource, featureID, gage_ids)

        # Assertions
        self.assertListEqual(result['comid'].tolist(), ['1722317', '1520007'])
        self.assertEqual(result.columns.tolist(), ['comid', 'geometry'])

class TestFindFeatSrceId(unittest.TestCase):

    def test_find_feat_srce_id(self):
        attr_config = {'col_schema': [{'featureID': 'USGS-{gage_id}'},
                        {'featureSource': 'nwissite'}],
                        'loc_id_read': [{'gage_id': 'gage_id'},
                        {'loc_id_filepath': '{dir_std_base}/juliemai-xSSA/eval/metrics/juliemai-xSSA_Raven_blended.csv'},
                        {'featureID_loc': 'USGS-{gage_id}'},
                        {'featureSource_loc': 'nwissite'}],
                        }
        rslt = fs_algo_train_eval._find_feat_srce_id(attr_config = attr_config)
        self.assertEqual(rslt,['nwissite','USGS-{gage_id}'])

    # Raise error when featureSource not provided:
    def test_missing_feat_srce(self):
        attr_config_miss = {'col_schema': [{'featureID': 'USGS-{gage_id}'},
                                            {'fe0a0ur0eS0ou0r0ce': 'nwissite'}],
                            'loc_id_read': {'gage_id': 'gage_id'}}
        with self.assertRaises(ValueError):
            fs_algo_train_eval._find_feat_srce_id(attr_config = attr_config_miss, dat_resp=None)

    def test_netcdf_attributes(self):
         # Create a mock xarray.Dataset object w/ attributes
        mock_xr = MagicMock(spec=xr.Dataset)
        mock_xr.attrs = {'featureSource': 'nwissite',
                         'featureID': 'USGS-{gage_id}'}

        rslt = fs_algo_train_eval._find_feat_srce_id(mock_xr)
        self.assertEqual(rslt,['nwissite','USGS-{gage_id}'])


    # Raise error when featureID not provided:
    def test_missing_feat_id(self):
         # Create a mock xarray.Dataset object
        mock_xr = MagicMock(spec=xr.Dataset)
        mock_xr.attrs = {'featureSource': 'nwissite',
                         'f0e1a0tu1reID': 'USGS-{gage_id}'}

        with self.assertRaises(ValueError):
            fs_algo_train_eval._find_feat_srce_id(mock_xr)

    # Test when dataset does not have any attributes but does have config:
    def test_missing_attrs(self):
        mock_xr = MagicMock(spec=xr.Dataset)
        mock_xr.attrs = {'notit': 'blah',
                         'alsonotit': 'bleh'}
        attr_config = {'col_schema': [{'featureID': 'USGS-{gage_id}'},
                {'featureSource': 'nwissite'}],
                'loc_id_read': [{'gage_id': 'gage_id'},
                {'loc_id_filepath': '{dir_std_base}/juliemai-xSSA/eval/metrics/juliemai-xSSA_Raven_blended.csv'},
                {'featureID_loc': 'USGS-{gage_id}'},
                {'featureSource_loc': 'nwissite'}],
                }
        rslt = fs_algo_train_eval._find_feat_srce_id(dat_resp = mock_xr, attr_config = attr_config)
        self.assertEqual(rslt,['nwissite','USGS-{gage_id}'])

class build_cfig_path(unittest.TestCase):
    def test_build_cfig_path(self):
        dir_base = tempfile.gettempdir()
        dir_new = Path(dir_base)/Path('testingitout')
        dir_new.mkdir(exist_ok=True)
        with self.assertRaises(FileNotFoundError):
            path_cfig = fs_algo_train_eval.build_cfig_path(dir_new,'test.yaml')

        with self.assertRaises(FileNotFoundError):
            fs_algo_train_eval.build_cfig_path('this_dir/doesnt/exist','test.yaml')

        with self.assertWarns(UserWarning):
            fs_algo_train_eval.build_cfig_path(dir_new,'')

    @patch('pathlib.Path.exists')
    def test_file_exists(self, mock_exists):
        dir_base = tempfile.gettempdir()
        dir_new = Path(dir_base)/Path('testingitout')
        path_known_config = Path(dir_new)/Path('test.yaml')
        path_or_name_cfig = Path(dir_new)/Path('a_nother_config.yaml')

        # Mock the existence of the directories and files, side_effect attr of mock object allws specifying a function or iterable called e/ time mock is called
        mock_exists.side_effect = lambda: True # Tells the mock object to return True everytime the path.exists method called
        rslt = fs_algo_train_eval.build_cfig_path(path_known_config, path_or_name_cfig)
        # Assert
        self.assertEqual(rslt, path_or_name_cfig)
        self.assertEqual(mock_exists.call_count, 2)

class TestFsSaveAlgoDirStruct(unittest.TestCase):
    def test_fs_save_algo_dir_struct(self):
        dir_base = tempfile.gettempdir()
        rslt = fs_algo_train_eval.fs_save_algo_dir_struct(dir_base)
        self.assertIn('dir_out', rslt.keys())
        self.assertIn('dir_out_alg_base', rslt.keys())
        self.assertTrue(Path(rslt['dir_out_alg_base']).exists)

        with self.assertRaises(ValueError):
            fs_algo_train_eval.fs_save_algo_dir_struct(dir_base + '/not_a_dir/')

class TestOpenResponseDataFs(unittest.TestCase):
    dir_std_base = tempfile.gettempdir()

    def test_open_response_data_fs(self):

        with self.assertRaisesRegex(ValueError, 'Could not identify an approach to read in dataset'):
            fs_algo_train_eval._open_response_data_fs(self.dir_std_base,ds='not_a_ds')
#%% ALGO TRAIN & EVAL
class TestStdAlgoPath(unittest.TestCase):

    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.exists')
    def test_std_algo_path(self, mock_exists, mock_mkdir):
        dir_out_alg_ds = tempfile.gettempdir()
        algo = 'test_algo'
        metric = 'test_metric'
        dataset_id = 'test_dataset'
        expected_path = Path(dir_out_alg_ds) / 'algo_test_algo_test_metric__test_dataset.joblib'

        # Mock the existence of the directory
        mock_exists.return_value = True

        result = fs_algo_train_eval.std_algo_path(dir_out_alg_ds, algo, metric, dataset_id)
        mock_mkdir.assert_called_once_with(exist_ok=True, parents=True)
        self.assertEqual(result, expected_path)

class TestStdPredPath(unittest.TestCase):
    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.exists')
    def test_std_pred_path(self, mock_exists, mock_mkdir):
        dir_out = '/some/directory'
        algo = 'test_algo'
        metric = 'test_metric'
        dataset_id = 'test_dataset'
        expected_path = Path(dir_out) / 'algorithm_predictions' / dataset_id / 'pred_test_algo_test_metric__test_dataset.parquet'

        # Mock the existence of the directory
        mock_exists.return_value = True
        result = fs_algo_train_eval.std_pred_path(dir_out, algo, metric, dataset_id)

        mock_mkdir.assert_called_once_with(exist_ok=True, parents=True)
        self.assertEqual(result, expected_path)

class TestReadPredComid(unittest.TestCase):
    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    def test_read_pred_comid(self, mock_read_csv, mock_exists):
        # Arrange
        path_pred_locs = '/some/directory/predictions.csv'
        comid_pred_col = 'comid'
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame({comid_pred_col: [1, 2, 3]})

        result = fs_algo_train_eval._read_pred_comid(path_pred_locs, comid_pred_col)
        mock_exists.assert_called_once_with()
        mock_read_csv.assert_called_once_with(path_pred_locs)
        self.assertEqual(result, ['1', '2', '3'])

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    def test_read_csv_error(self, mock_read_csv, mock_exists):
        path_pred_locs = '/some/directory/predictions.csv'
        comid_pred_col = 'comid'
        mock_exists.return_value = True
        mock_read_csv.side_effect = Exception("Read CSV error")
        with self.assertRaises(ValueError):
            fs_algo_train_eval._read_pred_comid(path_pred_locs, comid_pred_col)

    @patch('pathlib.Path.exists')
    def test_unsupported_file_extension(self, mock_exists):
        path_pred_locs = '/some/directory/predictions.txt'
        comid_pred_col = 'comid'
        mock_exists.return_value = True
        with self.assertRaises(ValueError):
            fs_algo_train_eval._read_pred_comid(path_pred_locs, comid_pred_col)


# %% UNIT TEST FOR AlgoTrainEval class
class TestAlgoTrainEval(unittest.TestCase):
    print("Testing AlgoTrainEval")
    def setUp(self):
        # Create a simple DataFrame for testing
        data = {
            'attr1': [1, 2, 3, 4, 5],
            'attr2': [5, 4, 3, 2, 1],
            'metric1': [0.1, 0.9, 0.3, 0.1, 0.8]
        }
        self.df = pd.DataFrame(data)

        # Variables and configurations for algorithms
        self.attrs = ['attr1', 'attr2']
        self.algo_config = {
            'rf': {'n_estimators': 10},
            'mlp': {'hidden_layer_sizes': (10,), 'max_iter': 2000}
        }
        self.dataset_id = 'test_dataset'
        self.metric = 'metric1'
        self.verbose = False
        # Output directory
        self.dir_out_alg_ds = tempfile.gettempdir()

        # Instantiate AlgoTrainEval class
        self.train_eval = AlgoTrainEval(df=self.df, attrs=self.attrs, algo_config=self.algo_config,
                                 dir_out_alg_ds=self.dir_out_alg_ds, dataset_id=self.dataset_id,
                                 metr=self.metric, test_size=0.4, rs=42)

    def test_split_data(self):
        # Test data splitting
        self.train_eval.split_data()
        self.assertEqual(len(self.train_eval.X_train), 3)
        self.assertEqual(len(self.train_eval.X_test), 2)
        self.assertEqual(len(self.train_eval.y_train), 3)
        self.assertEqual(len(self.train_eval.y_test), 2)

    def test_train_algos(self):
        # Test algorithm training
        self.train_eval.split_data()
        self.train_eval.train_algos()

        self.assertIn('rf', self.train_eval.algs_dict)
        self.assertIsInstance(self.train_eval.algs_dict['rf']['algo'], RandomForestRegressor)

        self.assertIn('mlp', self.train_eval.algs_dict)
        self.assertIsInstance(self.train_eval.algs_dict['mlp']['algo'], MLPRegressor)

        #self.assertEqual(len(self.algo_config), len(self.train_eval))

    def test_predict_algos(self):
        # Test algorithm predictions
        self.train_eval.split_data()
        self.train_eval.train_algos()

        preds = self.train_eval.predict_algos()

        self.assertIn('rf', preds)
        self.assertIn('mlp', preds)
        self.assertEqual(len(preds['rf']['y_pred']), 2)  # Number of test samples
        self.assertEqual(len(preds['mlp']['y_pred']), 2)

    def test_evaluate_algos(self):
        # Test evaluation of algorithms
        self.train_eval.split_data()
        self.train_eval.train_algos()
        self.train_eval.predict_algos()

        eval_dict = self.train_eval.evaluate_algos()

        self.assertIn('rf', eval_dict)
        self.assertIn('mlp', eval_dict)
        self.assertIn('mse', eval_dict['rf'])
        self.assertIn('r2', eval_dict['mlp'])

    @patch('joblib.dump')
    def test_save_algos(self, mock_dump):
        # Test saving algorithms to disk
        self.train_eval.split_data()
        self.train_eval.train_algos()

        # Mock joblib.dump to avoid file operations
        self.train_eval.save_algos()
        self.assertTrue(mock_dump.called)

        for algo in self.train_eval.algs_dict.keys():
            self.assertIn('file_pipe', self.train_eval.algs_dict[algo])

    def test_org_metadata_alg(self):
        # Test organizing metadata
        self.train_eval.split_data()
        self.train_eval.train_algos()
        self.train_eval.predict_algos()
        self.train_eval.evaluate_algos()

        # Mock saving algorithms and call organization
        with patch('joblib.dump'):
            self.train_eval.save_algos()

        self.train_eval.org_metadata_alg()

        # Check eval_df is correctly populated
        self.assertFalse(self.train_eval.eval_df.empty)
        self.assertIn('dataset', self.train_eval.eval_df.columns)
        self.assertIn('file_pipe', self.train_eval.eval_df.columns)
        self.assertIn('algo', self.train_eval.eval_df.columns)
        self.assertEqual(self.train_eval.eval_df['dataset'].iloc[0], self.dataset_id)

class TestAlgoTrainEvalMlti(unittest.TestCase):

    def setUp(self):
        # Sample data for testing
        data = {
            #'comid':['1', '2', '3', '4', '5,1', '2', '3', '4', '5','1', '2', '3', '4', '5'],
            'attr1': [1, 2, 3, 4, 5,1, 2, 3, 4, 5,1, 2, 3, 4, 5],
            'attr2': [5, 4, 3, 2, 1,5, 4, 3, 2, 1,5, 4, 3, 2, 1],
            'metric': [0.1, 0.9, 0.3, 0.1, 0.8,0.1, 0.9, 0.3, 0.1, 0.8,0.1, 0.9, 0.3, 0.1, 0.8]
        }
        self.df = pd.DataFrame(data)
        self.attrs = ['attr1', 'attr2']
        self.algo_config = {
            'rf': [{'n_estimators': [10, 50]}],
            'mlp': [{'hidden_layer_sizes': [(10,), (5, 5)], 'max_iter': [2000]}]
        }
        self.dir_out_alg_ds = './'
        self.dataset_id = 'test_dataset'
        self.metric = 'metric'
        self.test_size = 0.3
        self.test_id_col = 'comid'
        self.rs = 32
        self.verbose = False

        self.algo_train_eval = AlgoTrainEval(df=self.df, attrs=self.attrs, algo_config=self.algo_config,
                                              dir_out_alg_ds=self.dir_out_alg_ds,dataset_id=self.dataset_id,
                                              metr=self.metric, test_size=self.test_size, rs=self.rs,
                                              verbose=self.verbose)

    def test_initialization(self):
        self.assertEqual(self.algo_train_eval.df.shape, self.df.shape)
        self.assertEqual(self.algo_train_eval.attrs, self.attrs)
        self.assertEqual(self.algo_train_eval.algo_config, self.algo_config)
        self.assertEqual(self.algo_train_eval.dir_out_alg_ds, self.dir_out_alg_ds)
        self.assertEqual(self.algo_train_eval.metric, self.metric)
        self.assertEqual(self.algo_train_eval.test_size, self.test_size)
        self.assertEqual(self.algo_train_eval.rs, self.rs)
        self.assertEqual(self.algo_train_eval.dataset_id, self.dataset_id)
        self.assertEqual(self.algo_train_eval.verbose, self.verbose)

    def test_split_data(self):
        self.algo_train_eval.split_data()
        self.assertFalse(self.algo_train_eval.X_train.empty)
        self.assertFalse(self.algo_train_eval.X_test.empty)
        self.assertFalse(self.algo_train_eval.y_train.empty)
        self.assertFalse(self.algo_train_eval.y_test.empty)
        self.assertEqual(len(self.algo_train_eval.X_train) + len(self.algo_train_eval.X_test), len(self.df.dropna()))

    def test_select_algs_grid_search(self):
        self.algo_train_eval.select_algs_grid_search()
        self.assertIn('mlp', self.algo_train_eval.grid_search_algs)
        self.assertNotIn('mlp', self.algo_train_eval.algo_config)
        self.assertIn('mlp', self.algo_train_eval.algo_config_grid)


    def test_train_algos(self):
        self.algo_train_eval.split_data()
        self.algo_train_eval.select_algs_grid_search()
        self.algo_train_eval.train_algos_grid_search()
        self.assertTrue('rf' in  self.algo_train_eval.algo_config_grid)
        self.assertIn('mlp', self.algo_train_eval.algs_dict)



    def test_empty_dict(self):
        d = {}
        self.algo_train_eval.convert_to_list(d)
        self.assertEqual(d, {})

    def test_single_level_dict(self):
        d = {'a': 1, 'b': 2}
        self.algo_train_eval.convert_to_list(d)
        self.assertEqual(d, {'a': [1], 'b': [2]})

    def test_nested_dict(self):
        d = {'a': {'sub1': 1, 'sub2': 2}, 'b': {'sub1': 3, 'sub2': {'subsub1': 4}}, 'c': 5}
        self.algo_train_eval.convert_to_list(d)
        self.assertEqual(d, {'a': {'sub1': [1], 'sub2': [2]}, 'b': {'sub1': [3], 'sub2': {'subsub1': [4]}}, 'c': [5]})

    def test_already_list(self):
        d = {'a': [1, 2], 'b': {'sub1': [3, 4]}}
        self.algo_train_eval.convert_to_list(d)
        self.assertEqual(d, {'a': [1, 2], 'b': {'sub1': [3, 4]}})


class TestAlgoTrainEvalSngl(unittest.TestCase):
    # An algo_config with singular hyperparameter value
    def setUp(self):
        # Sample data for testing
        self.df = pd.DataFrame({
            'attr1': [1, 2, 3, 4, 5],
            'attr2': [5, 4, 3, 2, 1],
            'metric': [1, 0, 1, 0, 1]
        })
        self.attrs = ['attr1', 'attr2']
        self.algo_config = {'some_algo': {'param1': 1}}
        self.dir_out_alg_ds = 'some/dir'
        self.dataset_id = 'dataset_1'
        self.metr = 'metric'
        self.test_size = 0.3
        self.rs = 32
        self.verbose = False
        self.algo_config_grid = dict()
        self.grid_search_algs=list()

        self.algo_train_eval = AlgoTrainEval(
            df=self.df, attrs=self.attrs, algo_config=self.algo_config, dir_out_alg_ds=self.dir_out_alg_ds,
            dataset_id=self.dataset_id, metr=self.metr, test_size=self.test_size, rs=self.rs, verbose=self.verbose
        )

    @patch.object(AlgoTrainEval, 'split_data')
    @patch.object(AlgoTrainEval, 'select_algs_grid_search')
    @patch.object(AlgoTrainEval, 'train_algos_grid_search')
    @patch.object(AlgoTrainEval, 'train_algos')
    def test_train_eval(self, mock_train_algos, mock_train_algos_grid_search, mock_select_algs_grid_search, mock_split_data):
        # Mock the methods to avoid actual execution
        mock_split_data.return_value = None
        mock_select_algs_grid_search.return_value = None
        mock_train_algos_grid_search.return_value = None
        mock_train_algos.return_value = None

        # Call the method
        self.algo_train_eval.train_eval()

        # Assert that the methods were or were not called
        mock_split_data.assert_called_once()
        mock_select_algs_grid_search.assert_called_once()
        mock_train_algos_grid_search.assert_not_called()
        mock_train_algos.assert_called_once()

class TestAlgoTrainEvalBasic(unittest.TestCase):

    def setUp(self):
        # Set up a small test dataframe
        self.df = pd.DataFrame({
            'attr1': [1, 2, 3, 4, 5,1, 2, 3, 4, 5,1, 2, 3, 4, 5],
            'attr2': [5, 4, 3, 2, 1,5, 4, 3, 2, 1,5, 4, 3, 2, 1],
            'target': [10, 15, 20, 25, 30,10, 15, 20, 25, 30,10, 15, 20, 25, 30]
        })
        self.attrs = ['attr1', 'attr2']
        self.algo_config = {
            'rf': [{'n_estimators': [10,30,40]}],
            'mlp': [{'hidden_layer_sizes': (50,)}]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)

        self.dir_out_alg_ds = temp_dir
        self.dataset_id = 'test_ds'
        self.metric = 'target'
        self.test_size = 0.2
        self.rs = 42
        self.verbose = False
        self.algo_config_grid = dict()
        self.algo = AlgoTrainEval(df=self.df, attrs=self.attrs, algo_config=self.algo_config,
                                  dir_out_alg_ds=self.dir_out_alg_ds, dataset_id=self.dataset_id, 
                                  metr=self.metric, test_size=self.test_size, rs=self.rs, 
                                  verbose=self.verbose)

    @patch('joblib.dump')  # Mock saving the model to disk
    @patch('sklearn.model_selection.train_test_split', return_value=(pd.DataFrame(), pd.DataFrame(), pd.Series(), pd.Series()))
    @patch('sklearn.ensemble.RandomForestRegressor')
    @patch('sklearn.neural_network.MLPRegressor')
    def test_train_eval(self, MockMLP, MockRF, mock_train_test_split, mock_joblib_dump):
        # Mocking train algorithms
        mock_rf_model = MagicMock()
        mock_mlp_model = MagicMock()

        # Assign these mock models to the mock class
        MockRF.return_value = mock_rf_model
        MockMLP.return_value = mock_mlp_model

        # Mock the predictions
        mock_rf_model.predict.return_value = [10, 20, 30]
        mock_mlp_model.predict.return_value = [15, 25, 35]

        # Run the method
        self.algo.train_eval()

        # Check if the train_test_split was called correctly
        #mock_train_test_split.assert_called()

        # Check that the RandomForest and MLP models were trained
        # MockRF.assert_called_once()
        # MockMLP.assert_called_once()
        # self.assertIn('rf',self.algo_config_grid)
        # self.assertIn('mlp',self.algo_config)

        # Check predictions and evaluations were made
        self.assertIn('rf', self.algo.preds_dict)
        self.assertIn('mlp', self.algo.preds_dict)



        self.assertIn('rf', self.algo.eval_dict)
        self.assertIn('mlp', self.algo.eval_dict)

        # Check if models were saved
        mock_joblib_dump.assert_called()

        # Check eval dataframe was created
        self.assertIsInstance(self.algo.eval_df, pd.DataFrame)
        self.assertFalse(self.algo.eval_df.empty)


if __name__ == '__main__':
    unittest.main()

# %%
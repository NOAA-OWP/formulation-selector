# Generated using Gemini3Pro
import unittest
import tempfile
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Import the module to test (adjust the import path as necessary for your project structure)
from pkg.rafts_prep.rafts_prep.archive import prep_gpkg as gpkg_io 


class TestGpkgIO(unittest.TestCase):
    
    def setUp(self):
        """Set up a temporary directory for file I/O operations before each test."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.test_dir.name)
        
        # Suppress FutureWarnings from Pandas/Geopandas during tests for cleaner output
        warnings.simplefilter(action='ignore', category=FutureWarning)

    def tearDown(self):
        """Clean up the temporary directory after each test."""
        self.test_dir.cleanup()

    def _create_dummy_gdf(self, gage_ids, crs="EPSG:4326", include_na=False):
        """Helper function to create a basic GeoDataFrame for testing."""
        data = {
            'gage_id': gage_ids,
            'geometry': [Point(i, i) for i in range(len(gage_ids))]
        }
        if include_na:
            # Add a column with some NAs
            data['attr_col'] = [None if i % 2 == 0 else i for i in range(len(gage_ids))]
            
        return gpd.GeoDataFrame(data, crs=crs)

    def test_std_path_gpkg_db(self):
        """Test that the global database path is standardized and directory is created."""
        target_dir = self.base_path / "new_db_dir"
        
        # Directory shouldn't exist yet
        self.assertFalse(target_dir.exists())
        
        db_path = gpkg_io.std_path_gpkg_db(target_dir)
        
        # Directory should now exist, and filename should be all_locs.gpkg
        self.assertTrue(target_dir.exists())
        self.assertEqual(db_path.name, "all_locs.gpkg")
        self.assertEqual(db_path.parent, target_dir)

    def test_std_write_geom_map_gpkg_removes_duplicates(self):
        """Test that writing the GeoPackage correctly drops duplicates, keeping the one with least NAs."""
        save_path = self.base_path / "test_write.gpkg"
        
        # Create a GDF with duplicate gage_id 'A'. 
        # Row 0 has an NA, Row 1 does not. So Row 1 should be kept.
        data = {
            'gage_id': ['A', 'A', 'B'],
            'val1': [None, 10, 20],
            'geometry': [Point(0, 0), Point(1, 1), Point(2, 2)]
        }
        gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
        
        gpkg_io.std_write_geom_map_gpkg(gdf, save_path, epsg=4326)
        
        # Read back and verify
        self.assertTrue(save_path.exists())
        gdf_read = gpd.read_file(save_path)
        
        self.assertEqual(len(gdf_read), 2)
        # Verify the 'A' kept was the one with val1 = 10 (the one without NA)
        val_for_a = gdf_read.loc[gdf_read['gage_id'] == 'A', 'val1'].iloc[0]
        self.assertEqual(val_for_a, 10.0)

    def test_std_write_geom_map_gpkg_crs_conversion(self):
        """Test that writing the GeoPackage correctly converts CRS if needed."""
        save_path = self.base_path / "test_crs.gpkg"
        gdf = self._create_dummy_gdf(["A", "B"], crs="EPSG:3857") # Input is Web Mercator
        
        # Force write to EPSG:4326
        gpkg_io.std_write_geom_map_gpkg(gdf, save_path, epsg=4326)
        
        gdf_read = gpd.read_file(save_path)
        self.assertEqual(gdf_read.crs.to_epsg(), 4326)

    def test_load_reference_gpkgs(self):
        """Test loading reference geopackages from a directory."""
        ref_dir = self.base_path / "refs"
        ref_dir.mkdir()
        
        # Create two dummy gpkgs
        gdf1 = self._create_dummy_gdf(["1", "2"])
        gdf2 = self._create_dummy_gdf(["3", "4"])
        
        gdf1.to_file(ref_dir / "ref1.gpkg", driver="GPKG", layer="outlet")
        gdf2.to_file(ref_dir / "ref2.gpkg", driver="GPKG", layer="outlet")
        
        # Read them back
        loaded_gdfs = gpkg_io._load_reference_gpkgs(ref_dir)
        self.assertEqual(len(loaded_gdfs), 2)
        
        # Verify single file read works too
        loaded_single = gpkg_io._load_reference_gpkgs(ref_dir / "ref1.gpkg")
        self.assertEqual(len(loaded_single), 1)

    def test_gen_ds_gpkg(self):
        """Test that the dataset GPKG is correctly generated from reference pools."""
        dir_db_gpkg = self.base_path / "global_db"
        ref_dir = self.base_path / "ref_db"
        ref_dir.mkdir()
        path_save_gpkg = self.base_path / "ds.gpkg"
        
        # 1. Create a mock global database with locations A, B
        global_gdf = self._create_dummy_gdf(["A", "B"])
        gpkg_io.std_write_geom_map_gpkg(global_gdf, gpkg_io.std_path_gpkg_db(dir_db_gpkg))
        
        # 2. Create a mock reference database with locations C, D
        ref_gdf = self._create_dummy_gdf(["C", "D"])
        ref_gdf.to_file(ref_dir / "my_ref.gpkg", driver="GPKG", layer="outlet")
        
        # 3. Request generation for gage_ids A, C, and E (E doesn't exist anywhere)
        gpkg_io.gen_ds_gpkg(
            dir_db_gpkg=dir_db_gpkg,
            path_save_gpkg=path_save_gpkg,
            gage_ids=["A", "C", "E"],
            epsg=4326,
            reference_gpkg_path=ref_dir
        )
        
        # 4. Verify the resulting dataset gpkg
        self.assertTrue(path_save_gpkg.exists())
        ds_gdf = gpd.read_file(path_save_gpkg)
        
        # It should only contain A and C
        self.assertEqual(len(ds_gdf), 2)
        self.assertCountEqual(ds_gdf['gage_id'].tolist(), ["A", "C"])

    def test_update_gpkg_db(self):
        """Test updating the global database with new locations."""
        dir_db_gpkg = self.base_path / "global_db"
        ds_gpkg_1 = self.base_path / "ds1.gpkg"
        ds_gpkg_2 = self.base_path / "ds2.gpkg"
        
        # Create first dataset and update global db (which doesn't exist yet)
        gdf1 = self._create_dummy_gdf(["A", "B"])
        gdf1.to_file(ds_gpkg_1, driver="GPKG")
        
        gpkg_io.update_gpkg_db(dir_db_gpkg, ds_gpkg_1)
        
        global_db_path = gpkg_io.std_path_gpkg_db(dir_db_gpkg)
        self.assertTrue(global_db_path.exists())
        global_gdf = gpd.read_file(global_db_path)
        self.assertCountEqual(global_gdf['gage_id'].tolist(), ["A", "B"])
        
        # Create second dataset and update global db (append)
        gdf2 = self._create_dummy_gdf(["C"])
        gdf2.to_file(ds_gpkg_2, driver="GPKG")
        
        gpkg_io.update_gpkg_db(dir_db_gpkg, ds_gpkg_2)
        
        global_gdf_updated = gpd.read_file(global_db_path)
        self.assertCountEqual(global_gdf_updated['gage_id'].tolist(), ["A", "B", "C"])


if __name__ == '__main__':
    unittest.main()
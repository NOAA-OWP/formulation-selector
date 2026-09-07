#' @title Unit test hydrofabric processing
#' @author Guy Litt \email{guy.litt@noaa.gov}
#' @note When running this script, be sure to also source tests/testthat/setup.R first
# Changelog / Contributions
#.  2025-02-12 Originally created, GL
#.  2025-08-14 Adapted for logr, GL

suppressPackageStartupMessages(library(proc.attr.hydfab,quietly=TRUE))
suppressPackageStartupMessages(library(testthat,quietly=TRUE))
suppressPackageStartupMessages(library(dplyr,quietly=TRUE))
suppressPackageStartupMessages(library(hydrofabric,quietly=TRUE))
suppressPackageStartupMessages(library(data.table,quietly=TRUE))
suppressPackageStartupMessages(library(pkgcond,quietly=TRUE))
suppressPackageStartupMessages(library(yaml,quietly=TRUE))
suppressPackageStartupMessages(library(glue,quietly=TRUE))
suppressPackageStartupMessages(library(sf,quietly=TRUE))
suppressPackageStartupMessages(library(mockery,quietly=TRUE))
suppressPackageStartupMessages(library(hfsubsetR,quietly=TRUE))
options(arrow.unsafe_metadata = TRUE)

# ------ Define paths that may be used for testing:

# Define data directories to a package-specific data path
dir_base <- system.file("extdata",package="proc.attr.hydfab")
# Refer to temp_dir <- tempdir() in setup.R
temp_dir <- local_temp_dir() # If running this on your own, source 'setup.R' first.
path_meta <- paste0(temp_dir,"/{ds}/nldi_feat_{ds}_{ds_type}.parquet")
dir_db_attrs <- file.path(temp_dir,'attrs') # used for temporary attr retrieval
dir_db_attrs_pkg <- system.file("extdata","attributes_pah",package="proc.attr.hydfab")# permanent package location

# TODO CHANGE THIS!
path_oconus_hfab_config <- glue::glue("{dir_base}/test_config/oconus_config.yaml")
#dir_user <- system.file("extdata","user_data_std", package="proc.attr.hydfab") # dir_user <- "~/git/fsds/pkg/proc.attr.hydfab/inst/extdata/user_data_std/"

# Generate objects used in multiple tests:
dt_hads <- proc.attr.hydfab::read_noaa_hads_sites() %>% suppress_messages()

path_oconus_yaml <- base::file.path(dir_base,"test_config","oconus_config.yaml")

hf_version <- formals(hfsubsetR::get_subset)$hf_version
if(hf_version != "2.2"){
  warning("Hydrofabric unit tests have been designed for v2.2 and may need updating now that the hydrofabric has updated.")
}



testthat::test_that("read_noaa_hads_sites",{

  testthat::expect_true(base::nrow(dt_hads)>10000)
  testthat::expect_true(base::ncol(dt_hads) == 8)
  testthat::expect_true("lid" %in% names(dt_hads))
  testthat::expect_true("usgsId" %in% names(dt_hads))
  testthat::expect_true("latitude" %in% names(dt_hads))
  testthat::expect_true("longitude" %in% names(dt_hads))

})

testthat::test_that("std_feat_id",{
  dt_hads_sub <-dt_hads[c(3,333,408,1200,1333),]
  comids_fake <- c(1111,2222,3333,4444,5555)

  dt_meta <- proc.attr.hydfab::std_feat_id(df=dt_hads_sub,
              name_featureSource ="COMID",
              vals_featureID = comids_fake)

  # standardized form throughout RaFTS are featureID and featureSource columns
  testthat::expect_true("featureID" %in% names(dt_meta))
  testthat::expect_true("featureSource" %in% names(dt_meta))
  testthat::expect_true(base::all(dt_meta$featureSource == "COMID")) # standardized
  testthat::expect_identical(dt_meta$featureID,comids_fake)
})

# TODO add NWPS api unit test: retr_noaa_gauges_meta

# TODO create a mock object for path_oconus_hfab_config and reading hydrofabric oconus gpkg data
# testthat::test_that("retr_hfab_id_wrap",{
#   # Retrieve the hydrofabric IDs wrapper
#   usgs_ids_oconus <- c("15056210","16704000","50147800") # AK, HI, PR
#   dt_need_hf <- dt_hads %>% dplyr::filter(usgsId %in% usgs_ids_oconus)
#
#   dt_hfuid <- proc.attr.hydfab::retr_hfab_id_wrap(dt_need_hf,path_oconus_hfab_config = ) %>%
#     pkgcond::suppress_warnings() %>% pkgcond::suppress_messages()
#
#
#   testthat::expect_true(base::nrow(dt_hfuid) == nrow(dt_need_hf))
#   expect_new_cols <- c("featureID","featureSource","crs_hfab")
#   testthat::expect_true(base::all(expect_new_cols %in% base::names(dt_hfuid)))
#
#   # columns using wb ids:
#   idxs_cstm_hfab <- grep("-wb-",dt_hfuid$featureID)
#   testthat::expect_true(all(dt_hfuid$featureSource[idxs_cstm_hfab] == "custom_hfuid"))
#
#   testthat::expect_true(all(names(dt_need_hf) %in% names(dt_hfuid)))
#
# })

testthat::test_that("parse_hfab_oconus_config",{
  # Create a temporary YAML configuration file for testing
  df_map_hfab <- proc.attr.hydfab::parse_hfab_oconus_config(path_oconus_yaml)

  testthat::expect_true(base::all(c("path","domain","crs_hfab") %in%
                                    base::colnames(df_map_hfab)) )
  testthat::expect_true(grepl("proc.attr.hydfab/inst/extdata/gpkg_dat/ak_nextgen_subtest.gpkg",df_map_hfab$path[1]))
})

testthat::test_that("retr_state_terr_postal",{
  usgs_ids_oconus <- c("15056210","16704000","50147800") # AK, HI, PR
  dt_need_hf <- dt_hads %>% dplyr::filter(usgsId %in% usgs_ids_oconus)
  # AK should return AK
  ak_rslt <- proc.attr.hydfab::retr_state_terr_postal(lat=dt_need_hf$latitude[1],
                                           lon=dt_need_hf$longitude[1])
  testthat::expect_identical(ak_rslt, "AK")
  pr_rslt <- proc.attr.hydfab::retr_state_terr_postal(lat=dt_need_hf$latitude[3],
                                                      lon=dt_need_hf$longitude[3])
  testthat::expect_identical(pr_rslt, "PR")

  # Test US virgin island
  vi_rslt <- proc.attr.hydfab::retr_state_terr_postal(lat=18.335765,
                                                      lon=-64.896335)
  testthat::expect_identical(vi_rslt,"VI")

})



testthat::test_that("map_hfab_oconus_sources_wrap",{

  usgs_ids_oconus <- c("15056210","50147800","16704000") # AK, PR, HI
  dt_need_hf <- dt_hads %>% dplyr::filter(usgsId %in% usgs_ids_oconus)

  hfab_srce_map <- proc.attr.hydfab::parse_hfab_oconus_config(path_oconus_yaml)
  dt_rslt <- proc.attr.hydfab::map_hfab_oconus_sources_wrap(dt_need_hf,
                                                hfab_srce_map,
                                           col_lat = 'latitude',
                                           col_lon= 'longitude')

  testthat::expect_true(base::nrow(dt_rslt) == base::nrow(dt_need_hf))
  #testthat::expect_true(base::all(dt_rslt$path %in% hfab_srce_map$path))
  testthat::expect_true(base::all(base::names(dt_need_hf) %in%
                                    base::names(dt_rslt)))
  testthat::expect_true(base::all(base::names(hfab_srce_map) %in%
                                      base::names(dt_rslt)))

  # Expect error when lat and lon are not columns
  testthat::expect_error(
    proc.attr.hydfab::map_hfab_oconus_sources_wrap(dt_need_hf,
                                                  hfab_srce_map,
                                                  col_lat = 'lat',
                                                  col_lon= 'lon'))
})

testthat::test_that("read_hfab_layer",{
  # Create a temporary GeoPackage for testing
  temp_gpkg <- tempfile(pattern = "test_hi", fileext = ".gpkg")

  # Create a mock spatial dataset with a vpu column
  mock_data <- sf::st_sf(
    geometry = sf::st_sfc(sf::st_point(c(0, 0)), sf::st_point(c(1, 1))),
    vpu = c("hi", "hi")
  )

  # Write the dataset to the temporary GeoPackage
  sf::st_write(mock_data, temp_gpkg, layer = "divides", driver = "GPKG", quiet = TRUE)

  # Unit test for read_hfab_layer
  result <- proc.attr.hydfab::read_hfab_layer(temp_gpkg, "divides")

  # Check that result is an sf object
  testthat::expect_s3_class(result, "sf")

  # Check that expected columns exist
  testthat::expect_true("vpu" %in% colnames(result))

  # Check that vpu correction works
  testthat::expect_equal(unique(result$vpu), "hi")

  # Now expect a warning when there is a pattern mismatch specific to ak:
  temp_gpkg_ak <- tempfile(pattern = "test_ak", fileext = ".gpkg")
  # Create a mock spatial dataset with a vpu column
  mock_data_ak <- sf::st_sf(
    geometry = sf::st_sfc(sf::st_point(c(0, 0)), sf::st_point(c(1, 1))),
    vpu = c("hi", "hi")
  )

  # Write the dataset to the temporary GeoPackage
  sf::st_write(mock_data_ak, temp_gpkg_ak, layer = "divides",
               driver = "GPKG", quiet = TRUE,append=FALSE) %>% suppress_messages()

  out <- testthat::capture_output( proc.attr.hydfab::read_hfab_layer(temp_gpkg_ak, "divides"))
  testthat::expect_true(base::grepl("EDITING the vpu!!",out)) # Note GL: This should be fixed with hydrofabric v3.0
})
#
# test_that("retr_hf_id_xy returns correct hf_id values with mocked get_subset", {
#
#   # Create dummy sf POINT object with EPSG 4326
#   coords <- data.frame(
#     id = c("A", "B"),
#     lon = c(-98.2, -97.5),
#     lat = c(30.0, 29.5)
#   )
#
#   points_sf <- st_as_sf(coords, coords = c("lon", "lat"), crs = 4326)
#
#   # Add NA geometry row to test geometry filtering
#   points_sf$geometry[2] <- NA
#
#   # Dummy path to geopackage
#   path_gpkg <- "dummy/path/to.gpkg"
#
#   # Create mock network layer return values
#   dummy_network_1 <- data.frame(
#     hf_id = c(103, 101),
#     hf_hydroseq = c(20, 25)
#   )
#
#   dummy_return <- list(network = dummy_network_1)
#
#   # Mock function to return dummy network based on input coordinates
#   mock_get_subset <- mock(
#     dummy_return,
#     cycle = TRUE
#   )
#
#   # Stub the namespaced call to hfsubsetR::get_subset inside retr_hf_id_xy
#   stub(
#     where = retr_hf_id_xy,
#     what = "hfsubsetR::get_subset",
#     how = mock_get_subset
#   )
#
#   # Run function
#   result <- retr_hf_id_xy(points_sf, path_gpkg)
#   print(result)
#   # Expected: first point gets hf_id 101 (lowest hydroseq), second is NA
#   expect_equal(result, c(101, 101))
#
#   # Check that get_subset was called only once (only 1 non-NA point)
#   # expect_called(mock_get_subset, 1)
# })

testthat::test_that("retr_hf_id_xy errors on missing geometry column", {
  df_missing_geom <- data.frame(id = 1)
  err <- testthat::capture_error(
    retr_hf_id_xy(df_missing_geom, "path.gpkg", geom_col = "geometry")) %>%
    testthat::capture_output() %>% pkgcond::suppress_messages()
    testthat::expect_true(
      base::grepl("The expected geometry column geometry is not present", err))

})

testthat::test_that("retr_hf_id_xy errors if geometry is not POINT", {
  line <- sf::st_sfc(sf::st_linestring(matrix(c(0,0, 1,1), ncol=2, byrow=TRUE)), crs=4326)
  df <- data.frame(id = 1)
  df_sf <- sf::st_sf(df, geometry = line)
  err <- testthat::capture_error(
    proc.attr.hydfab::retr_hf_id_xy(df_sf, "path.gpkg")
  ) %>% testthat::capture_output()
  testthat::expect_true(
    base::grepl( "Must convert df_sf geometry column to POINT", err))
})

testthat::test_that("retr_hf_id_xy warns if CRS is missing", {
  pt <- st_sfc(st_point(c(-98.2, 30.0)))
  df <- st_sf(id = 1, geometry = pt)
  err <- testthat::capture_error(
      proc.attr.hydfab::retr_hf_id_xy(df, "path.gpkg")) %>%
    testthat::capture_output() %>% pkgcond::suppress_messages()
  testthat::expect_true(base::grepl("EPSG not specified. Assuming EPSG=4326",err))
})

testthat::test_that("retr_hf_id_xy errors if CRS is not 4326", {
  pt <- sf::st_sfc(sf::st_point(c(-98.2, 30.0))) %>% sf::st_set_crs(3857)
  df <- st_sf(id = 1, geometry = pt)
  err <- testthat::expect_error(
    proc.attr.hydfab::retr_hf_id_xy(df, "path.gpkg")) %>% testthat::capture_output()
  testthat::expect_true(base::grepl("Problem with EPSG not being 4326", err))
})


# ##### Building up mock data for retr_hfab_id_wrap unit testing
# # Create a temporary GeoPackage for testing
# temp_gpkg <- tempfile(pattern = "test_ak", fileext = ".gpkg")
# mock_network <- sf::st_sf(
#   geometry = sf::st_sfc(sf::st_point(c(0, 0)), sf::st_point(c(1, 1))),
#   vpu = c("hi", "hi"),
#   hf_id = c(1001, 1002)
# )
# mock_flowpaths <- mock_network
#
# # Write datasets to the temporary GeoPackage
# sf::st_write(mock_network, temp_gpkg, layer = "network", driver = "GPKG", quiet = TRUE)
# sf::st_write(mock_flowpaths, temp_gpkg, layer = "flowpaths", driver = "GPKG", quiet = TRUE)
# sf::st_write(mock_flowpaths, temp_gpkg, layer = "divides", driver = "GPKG", quiet = TRUE)
# # Create a mock input data.table
# dt_need_hf <- data.table::data.table(
#   usgsId = c("001", "002"),
#   longitude = c(0, 1),
#   latitude = c(0, 1),
#   path = temp_gpkg
# )
# temp_dir <- tempdir()
# test_yaml2 <- base::tempfile(fileext = ".yaml")
# fn_ak <- base::gsub(pattern=".gpkg",replacement="",x= base::basename(temp_gpkg) )
# base::writeLines(
# glue::glue(
# 'dir_base_hfab: ""
# source_map_ak:
#   path: "{temp_dir}/{fn_ak}.gpkg"
#   domain: "AK"
#   crs_hfab: "TBD"'),
#   con = test_yaml2)
#
# # Unit test for retr_hfab_id_wrap
# testthat::test_that("retr_hfab_id_wrap correctly retrieves hydrofabric IDs", {
#   usgs_ids_oconus <- c("15056210","50147800","16704000") # AK, PR, HI
#   dt_need_hf <- dt_hads %>% dplyr::filter(usgsId %in% usgs_ids_oconus)
#
#
#   # TODO why does hf_uid/featureID return as NA during testing?
#   result <- proc.attr.hydfab::retr_hfab_id_wrap(dt_need_hf = dt_need_hf,
#                               path_oconus_hfab_config = path_oconus_hfab_config,#path_oconus_yaml,
#                               col_usgsId="usgsId") %>%
#     pkgcond::suppress_warnings()
#
#   # Check that result is a data.table
#   testthat::expect_s3_class(result, "data.table")
#
#   # Check that hydrofabric IDs are correctly assigned
#   testthat::expect_equal(dt_need_hf$usgsId,result$usgsId)
#
#   testthat::expect_true(base::nrow(result) == nrow(dt_need_hf))
#   expect_new_cols <- c("featureID","featureSource","crs_hfab")
#   testthat::expect_true(base::all(expect_new_cols %in% base::names(result)))
#
#   # columns using wb ids:
#   testthat::expect_true(!base::all(base::is.na(result$featureID)))
#   idxs_cstm_hfab <- base::grep("-wb-",result$featureID)
#   testthat::expect_true(base::all(result$featureSource[idxs_cstm_hfab] == "custom_hfuid"))
#
#   testthat::expect_true(base::all(base::names(dt_need_hf) %in% base::names(result)))
# })

###########
# Expected return from hydrofabric v2.2:
dt_hfuid <- data.table::data.table(identifier=c("15056210","50147800","16704000"),
                                   domain=c("AK","HI","PR"),
                                   latitude=c(59.51194, 19.71214, 18.36174),
                                   longitude=c(-135.34444, -155.15075, -67.09254),
                                   name=c("TAIYA R NR SKAGWAY AK",
                                   "WAILUKU RIVER AT PIIHONUA HI",
                                   "RIO CULEBRINAS AT HWY 404 NR MOCA PR"),
                                   crs="EPSG:4326",
                                   path=c(file.path(dir_base,"gpkg_dat","ak_nextgen_subtest.gpkg"),
                                          file.path(dir_base,"gpkg_dat","hi_nextgen_subtest.gpkg"),
                                          file.path(dir_base,"gpkg_dat","prvi_nextgen_subtest.gpkg")),
                                   crs_hfab=c("EPSG:3338","ESRI:102007","EPSG:6566" ),
                                   hf_uid=c(NA,"hi-cat-1365","prvi-cat-777"),
                                   featureID=c(NA,"hi-cat-1365","prvi-cat-777"),
                                   featureSource=c(NA,"custom_hfuid","custom_hfuid")
                                  )

##############
testthat::test_that("retr_hfuid",{
  loc_ids_for_ak_hi_prvi <- base::c("15056210","50147800","16704000")
  rslt_msg <-testthat::capture_output(
    proc.attr.hydfab::retr_hfuids(loc_ids=loc_ids_for_ak_hi_prvi,
                                  path_oconus_hfab_config = path_oconus_yaml,
                                  featureSource = 'nwissite')) %>%
    testthat::expect_warning()

    testthat::expect_true(base::grepl("lon/lat does not exist", rslt_msg))
  rslt <- proc.attr.hydfab::retr_hfuids(loc_ids=loc_ids_for_ak_hi_prvi,
                                        path_oconus_hfab_config = path_oconus_yaml,
                                        featureSource = 'nwissite'
  ) %>% pkgcond::suppress_warnings()
  testthat::expect_true(all(lapply(loc_ids_for_ak_hi_prvi, function(x)
    any(base::grepl(x, rslt$identifier))))) %>% base::suppressWarnings()
  testthat::expect_true(any(base::grepl("custom_hfuid", rslt$featureSource)))
  testthat::expect_true(base::any("hi-cat-1365" %in% rslt$featureID))
  testthat::expect_true(base::any("prvi-cat-776" %in% rslt$featureID))
  testthat::expect_true("latitude" %in% names(rslt))
  testthat::expect_true("longitude" %in% names(rslt))
  testthat::expect_identical(dt_hfuid$path, rslt$path)
  testthat::expect_identical(dt_hfuid$crs_hfab, rslt$crs_hfab)

  # ----- test for comid from a CONUS location (TX)
  rslt_out <- testthat::capture_output(proc.attr.hydfab::retr_hfuids(loc_ids= c(1520007),
                                path_oconus_hfab_config = path_oconus_yaml,
                                featureSource = 'comid'))
  testthat::expect_true(base::grepl(" following domains/postal codes",rslt_out))
  rslt_comid <- proc.attr.hydfab::retr_hfuids(loc_ids= c(1520007),
                                              path_oconus_hfab_config = path_oconus_yaml,
                                              featureSource = 'comid') %>%
    pkgcond::suppress_messages()

  testthat::expect_equal(rslt_comid$featureSource, "COMID")
  testthat::expect_equal(rslt_comid$featureID,"1520007")
  testthat::expect_true(base::is.na(rslt_comid$path))
})

testthat::test_that("retr_comid_coord",{

  df <- base::data.frame(latitude = c(37.02058,64.90197), #Joplin MO, Fairbanks AK
                   longitude = c(-94.51375,-146.3613),
                   name=c("Joplin,MO","Fairbanks,AK"),
                   crs=c(4326,4326))
  rslt <- proc.attr.hydfab::retr_comids_coords(df=df,col_lat = 'latitude',col_lon='longitude',
                                               col_crs = 'crs')
  # Don't expect comid for Fairbanks, AK
  testthat::expect_true(is.na(rslt[2]))
  testthat::expect_equal(rslt[1],7590701)
  testthat::expect_equal(base::length(rslt),base::nrow(df))
})



# ------------
# Create a dummy namespace and function for proc.attr.hydfab::retr_hfab_id_wrap
# This is essential for isolating the unit tests.
proc.attr.hydfab <- new.env()
proc.attr.hydfab$retr_hfab_id_wrap <- function(dt_need_hf, path_oconus_hfab_config, col_usgsId, col_lon, col_lat, epsg_coords) {
  # A simple mock: adds a dummy hf_uid column
  # Handle cases where dt_need_hf might not have col_usgsId if it's an empty data frame from earlier steps
  if (nrow(dt_need_hf) > 0 && col_usgsId %in% names(dt_need_hf)) {
    dt_need_hf$hf_uid <- paste0("hf_", dt_need_hf[[col_usgsId]])
  } else {
    # If input is empty or col_usgsId is missing, add an empty or NA hf_uid column
    dt_need_hf$hf_uid <- character(nrow(dt_need_hf))
  }
  return(as.data.table(dt_need_hf)) # Ensure it returns a data.table or data.frame as expected
}

# Path to a dummy config file (content doesn't matter for these tests)
dummy_config_path <- tempfile(fileext = "_dummy_oconus_config.yaml")
file.create(dummy_config_path)

# Teardown: Remove the dummy file after tests are done
base::on.exit(base::unlink(dummy_config_path, force = TRUE), add = TRUE)

testthat::test_that("retr_hfuids works with featureSource = 'wqp'", {
  loc_ids_wqp <- c("USGS-01010502", "USGS-01010503")

  # Create proper sf objects with EPSG:4326
  loc1_sf <- sf::st_sf(
    sourceName = "Water Quality Portal",
    identifier = "USGS-01010502",
    comid = "12347",
    name = "WQP Site 2",
    X = -115.0,
    Y = 40.0,
    geometry = sf::st_sfc(sf::st_point(c(-115.0, 40.0)), crs = sf::st_crs(4326))
  )

  loc2_sf <- sf::st_sf(
    sourceName = "Water Quality Portal",
    identifier = "USGS-01010503",
    comid = "12348",
    name = "Fake Site 3",
    X = -116.0,
    Y = 41.0,
    geometry = sf::st_sfc(sf::st_point(c(-116.0, 41.0)), crs = sf::st_crs(4326))
  )

  # Mock findNLDI to return expected origin elements
  mock_wqp_calls <- mockery::mock(
    list(origin = loc1_sf),
    list(origin = loc2_sf)
  )

  stub(proc.attr.hydfab::retr_hfuids, "dataRetrieval::findNLDI", function(wqp, ...) mock_wqp_calls(wqp = wqp, ...))
  stub(proc.attr.hydfab::retr_hfuids, "proc.attr.hydfab::retr_hfab_id_wrap", proc.attr.hydfab$retr_hfab_id_wrap)

  result <- proc.attr.hydfab::retr_hfuids(
    loc_ids = loc_ids_wqp,
    path_oconus_hfab_config = dummy_config_path,
    featureSource = "wqp"
  )

  expect_true(is.data.frame(result))
  expect_equal(nrow(result), 2)
  expect_equal(result$identifier, c("USGS-01010502", "USGS-01010503"))
  expect_equal(result$hf_uid, c("hf_USGS-01010502", "hf_USGS-01010503"))
})

test_that("retr_hfuids works with featureSource = 'location' (assuming string loc_ids)", {
  # Based on implementation, featureSource='location' calls findNLDI(nwis=x).
  # Thus, loc_ids are expected to be string identifiers.
  loc_ids_loc <- c("myloc1", "myloc2")

  # Create proper sf objects with EPSG:4326
  loc1_sf <- sf::st_sf(
    sourceName = "NHDPlus comid",
    identifier = "myloc1",
    comid = "777",
    name = "My Location 1",
    X = -115.0,
    Y = 40.0,
    geometry = sf::st_sfc(sf::st_point(c(-115.0, 40.0)), crs = sf::st_crs(4326))
  )

  loc2_sf <- sf::st_sf(
    sourceName = "NHDPlus comid",
    identifier = "myloc2",
    comid = "888",
    name = "My Location 2",
    X = -116.0,
    Y = 41.0,
    geometry = sf::st_sfc(sf::st_point(c(-116.0, 41.0)), crs = sf::st_crs(4326))
  )

  # Mock findNLDI to return expected origin elements
  mock_loc_calls <- mockery::mock(
    list(origin = loc1_sf),
    list(origin = loc2_sf)
  )


  stub(retr_hfuids, "dataRetrieval::findNLDI", function(nwis, ...) mock_loc_calls(nwis = nwis, ...))
  stub(retr_hfuids, "proc.attr.hydfab::retr_hfab_id_wrap", proc.attr.hydfab$retr_hfab_id_wrap)

  result <- retr_hfuids(loc_ids = loc_ids_loc,
                        path_oconus_hfab_config = dummy_config_path,
                        featureSource = "location")

  expect_true(is.data.frame(result))
  expect_equal(nrow(result), 2)
  expect_equal(result$identifier, c("myloc1", "myloc2"))
  expect_equal(result$longitude, c(-115.0, -116.0))
  expect_equal(result$hf_uid, c("hf_myloc1", "hf_myloc2"))
})


test_that("retr_hfuids stops with unknown featureSource", {
  stub(retr_hfuids, "proc.attr.hydfab::retr_hfab_id_wrap", proc.attr.hydfab$retr_hfab_id_wrap)
  err <- testthat::expect_error(
    retr_hfuids(loc_ids = c("1"),
                path_oconus_hfab_config = dummy_config_path,
                featureSource = "invalid_source")) %>% testthat::capture_output()
  testthat::expect_true(
    base::grepl("Add another type of featureSource retrieval option here.", err)
  )
})
testthat::test_that("Coordinate extraction with all NA geometries returns NA coordinates", {
  # Create a valid sfc object with NA geometry and CRS
  na_geom_sfc <- sf::st_sfc(sf::st_point(), crs = 4326)
  na_geom_sfc[[1]] <- NA  # Explicitly set the geometry to NA

  # Create an sf object with NA geometry
  mock_sf <- sf::st_sf(
    sourceName = "NWIS Surface Water Sites",
    identifier = "na_geom_id",
    comid = NA_character_,
    name = NA_character_,
    X = NA_real_,
    Y = NA_real_,
    geometry = na_geom_sfc
  )

  # Mock findNLDI return
  mock_findNLDI_na_geom <- function(nwis, ...) {
    list(origin = mock_sf)
  }

  # Stub required functions
  stub(retr_hfuids, "dataRetrieval::findNLDI", mock_findNLDI_na_geom)
  stub(retr_hfuids, "proc.attr.hydfab::retr_hfab_id_wrap", proc.attr.hydfab$retr_hfab_id_wrap)

  result <- retr_hfuids(
    loc_ids = "na_geom_id",
    path_oconus_hfab_config = dummy_config_path,
    featureSource = "nwissite"
  )

  expect_true(is.data.frame(result))
  expect_equal(nrow(result), 1)
  expect_true(is.na(result$longitude))
  expect_true(is.na(result$latitude))
  expect_equal(result$identifier, "na_geom_id")
  expect_equal(result$hf_uid, "hf_na_geom_id")
})

# Example of how to run the tests if this file is sourced:
# if (interactive()) {
#   test_file("path/to/this/test_retr_hfuids.R")
# }

# Delete the temp files
if(base::exists("test_yaml")){
  rm(test_yaml)
}
if(base::exists("test_yaml2")){
  rm(test_yaml2)
}
if(base::exists("temp_gpkg")){
  rm(temp_gpkg)
}


# ---------------------------------------------------------------------------- #
# GENERATE unit testing OCONUS hydrofabric gpkg as subsets of actual gpkg
# ---------------------------------------------------------------------------- #
if(FALSE){ #ONLY RUN THIS ONCE TO GENERATE TEST DATA. ONCE IN PACKAGE,
  # NO LONGER NEEDED. THIS DOCUMENTS HOW TEST DATA GENERATED.
  # The locations of interest - will need to delete gpkg and re-write if this changes
  ak_locs <- c("wb-15164","wb-1003","wb-15164")
  prvi_locs <- base::c("wb-752","wb-777")
  hi_locs <- base::c("wb-2629","wb-1365","wb-1366")
  # ^^ include downstream wb-1366 to ensure full coverage for spatial query in unit test

  # If more locations desired for unit testing, add them above.
  def_iter_layrs_write <- function(locs, path_gpkg_read, path_gpkg_write,overwrite=FALSE){
    #' @title generate the gpkg datasets used for unit testing based on identifiers
    gpkg_sub_ls <- base::lapply(locs, function(x)
      hfsubsetR::get_subset(id=x,gpkg=path_gpkg_read,
      lyrs=c("divides","flowpaths","network","nexus","pois","hydrolocations")))

    if(overwrite){
      file.remove(path_gpkg_write)
    }
    all_layers <- base::lapply(gpkg_sub_ls, function(x) names(x)) %>% unlist() %>% unique()

    for(layr in all_layers){
      ls_layr <- list()
      ctr <- 0
      for(sub_div in gpkg_sub_ls){
        ctr <- ctr+1
        ls_layr[[ctr]] <- sub_div[[layr]]
      }
      if("data.frame" %in% class(ls_layr[[1]])){
        cmbo <- ls_layr %>% data.table::rbindlist(use.names=TRUE,fill=TRUE,ignore.attr = TRUE)
      } else {
        cmbo <- ls_layr %>% unlist()
      }
      # Now we have the layer, and can write it:
      try(
        sf::write_sf(cmbo,path_gpkg_write,layer = layr,append=TRUE))
    }
  }

  if(FALSE){ # Alaska subset
    def_iter_layrs_write(locs=ak_locs,
                         path_gpkg_read = "~/noaa/hydrofabric/v2.2/ak_nextgen.gpkg",
                         path_gpkg_write = file.path(dir_base,"gpkg_dat","ak_nextgen_subtest.gpkg"),
                         overwrite = TRUE)
  }
  if(FALSE){ # Hawaii
    def_iter_layrs_write(locs=hi_locs,
                         path_gpkg_read="~/noaa/hydrofabric/v2.2/hi_nextgen.gpkg",
                         path_gpkg_write=file.path(dir_base,"gpkg_dat","hi_nextgen_subtest.gpkg"),
                         overwrite=TRUE)
  }
  if(FALSE){ # Puerto Rico/Virgin Islands
    def_iter_layrs_write(locs=prvi_locs,
                         path_gpkg_read="~/noaa/hydrofabric/v2.2/prvi_nextgen.gpkg",
                         path_gpkg_write=file.path(dir_base,"gpkg_dat","prvi_nextgen_subtest.gpkg"),
                         overwrite=TRUE)
  }
}


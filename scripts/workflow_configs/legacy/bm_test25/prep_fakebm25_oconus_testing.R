#' @title Script to work through FY25 NWM v4 benchmarking locations (first stage, small # of catchments)
#' @description This is just a placeholder to get a mix of CONUS and OCONUS
#' locations in the same dataset for testing out the OCONUS refactor
#' @seealso prep_oconus_hydroatlas.R for preparation of hydroatlas attributes
#' corresponding to AK and PRVI hydrofabric VPU domains.

# Benchmarking exercises:
library(proc.attr.hydfab)
library(janitor)
library(readr)
library(hydrofabric)
library(hfsubsetR)
library(maps)
library(mapdata)
library(yaml)
library(glue)
# Function to get state name



# Example usage
# lat <- 41.8781
# lon <- -87.6298
# usvi <- c(17.725496,-64.845511)
# pr <- c(-66.992208,18.122422,4326)
# lon <- pr[1]
# lat <- pr[2]
# lon <- usvi[2]
# lat <- usvi[1]
# get_state_or_territory(pr[2],pr[1])
# state_name <- get_state_or_territory(latitude, longitude)
#
# print(state_name)


home_dir <- Sys.getenv("HOME")
path_prep_yml <- "~/git/rafts/scripts/workflow_configs/legacy/bm_test25/bm25test_prep_config.yml"
dat_rfc_prep <- yaml::read_yaml(file=path_prep_yml)
dir_std_base <- file.path(glue::glue(unlist(dat_rfc_prep$file_io)[['dir_save']]),
                          "user_data_std")
ds <- dat_rfc_prep$formulation_metadata[[1]]$dataset_name
dir_dataset <- proc.attr.hydfab::std_dir_dataset(dir_std_base,ds,mkdir=TRUE )
path_save_fake_file <- glue::glue(unlist(dat_rfc_prep$file_io)[['path_data']])
dir_data_in <- dirname(path_save_fake_file)
if(!dir.exists(dir_data_in)){
  dir.create(dir_data_in,recursive = TRUE)
}
#path_save_fake_file <- file.path(dir_data_in,"bm25test_fake_data.csv")


path_oconus_hfab_config <- "~/git/rafts/scripts/workflow_configs/legacy/bm_test25/bm_oconus_config.yaml"
path_nwps_rpt  <- 'https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv'
path_hads_sites <- 'https://hads.ncep.noaa.gov/USGS/ALL_USGS-HADS_SITES.txt'
path_nwps_api <- "https://api.water.noaa.gov/nwps/v1/gauges"

gauge_ids <- c("JOPM7","RNDO2","CSNC2",
               "UCHA2","TYAA2","WLWA2",
               "ALEC2","BERU1","OAKA3",
               "CREC1","HPIC1","PRBC1",
               "WDVA1","BDCL1","PLAM6",
               "CRTN6","FDKM2","LODN4",
               "BLRM7","DUBW4","PGEN8",
               "KALI4","HWYM5","HHTM4",
               "NRWM3","CENV1","CHRN6",
               "FSSO3","DRSW1","WGCM8",
               "DLYW2","DEPI3","LARO1",
               "VDSG1","CATA1","MKHF1",
               "KLGT2","ATIT2","SDAT2",
               "COMP4","MOCP4","NGKP4",
               "HLEH1","WLUH1","WHSH1")

data_source <- c("nwps","hads")[2] # Recommended to use HADS over NWPS
# ----- grab comids using a method proposed by Mike Johnson

#### NWPS data
# NOTE: NWPS gauges not comprehensive
if(data_source == "nwps"){
  d_nwps <- proc.attr.hydfab::read_noaa_nwps_gauges(
    path_nwps_rpt =path_nwps_rpt)

  d_nwps_sub <- base::lapply(gauge_ids,
                             function(gid) dplyr::filter(d_nwps, nws_shef_id == gid)) %>%
    data.table::rbindlist()
  d_nwps_sub <- d_nwps_sub %>% sf::st_as_sf(coords = c('longitude', 'latitude'), crs = 4326)

  comids_nwps <- proc.attr.hydfab::retr_comids_coords(df=d_nwps_sub, col_lat ='latitude',
                                                      col_lon='longitude',crs=4326)
  d_nwps_sub$comid <- comids_nwps
  dt_sub <- data.table::data.table(d_nwps_sub)
} else if(data_source == 'hads'){
  #### HADS DATA RETRIEVAL/FILTERING
  # NOTE: HADS data are comprehensive. Read all data.
  dt_hads <- proc.attr.hydfab::read_noaa_hads_sites(
    path_hads_sites=path_hads_sites)

  # Subset HADS to NOAA gauge_ids of interest
  dt_hads_sub <- base::lapply(gauge_ids,
                              function(gid) dt_hads %>% dplyr::filter(lid==gid)) %>%
    data.table::rbindlist()

  comids_hads <- proc.attr.hydfab::retr_comids_coords(df=dt_hads_sub, col_lat ='latitude',
                                                      col_lon='longitude',col_crs='crs')

  if(base::all(base::is.na(comids_hads))){
    warning("POTENTIAL PROBLEM WITH nhdplusTools::discover_nhdplus_id():
    No comids returned. This may relate to database connection limits or a bad connection.")

    # Now try to acquire comids via USGS gage Ids
    comids_hads <- base::lapply(dt_hads_sub$usgsId,function(gid)
      nhdplusTools::discover_nhdplus_id(nldi_feature =
                                          base::c(featureSource='nwissite',
                                                  featureID=paste0("USGS-",gid))))
    if(base::any(!base::is.na(comids_hads))){
      base::message("comids successfully discovered using USGS gage IDs")
    }
  }
  dt_hads_sub$comid <- comids_hads
  dt_sub <-dt_hads_sub
}
dt_sub$false_data <- 0.5
dt_sub <- dt_sub %>% dplyr::select(dplyr::all_of(c("lid","usgsId","name","false_data")))
write.csv(dt_sub,file = path_save_fake_file,row.names = FALSE)

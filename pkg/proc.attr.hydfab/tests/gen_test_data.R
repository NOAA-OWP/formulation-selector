# Functions to generate the data used in unit tests for proc.attr.hydfab
# @seealso test_rafts_utils.R and test_proc_attr_grabber.R for the unit tests
# Changelog / Contributions
#.   2025-05-23 Originally created, LB


library(sf)
library(glue)
library(tidyverse)

# sub_hf_huc_conus test data ----------
gen_sub_hf_huc_conus <- function(){
  home_dir <- Sys.getenv('HOME')
  pkg_dir <- glue::glue('{home_dir}/Lauren/FSDS/formulation-selector/pkg/proc.attr.hydfab')
  Retr_Params <- glue::glue('{home_dir}/Lauren/FSDS/formulation-selector/scripts/eval_ingest/xssa_NWM_domain/xssanwm_attr_config.yaml') %>%
    proc.attr.hydfab::attr_cfig_parse()
  
  # TODO: it seems like the point of the cfig parser is so I don't have to do this...
  # Check with Guy
  dir_db_hydfab <- Retr_Params$paths[['dir_db_hydfab']]
  hf_path <- glue::glue(Retr_Params$paths[['hfab_path_conus']])
  
  # Get a HUC6 watershed
  wbd <- sf::st_read(glue::glue('{home_dir}/Lauren/regionalization/WBD_National_GPKG/WBD_National_GPKG.gpkg'), layer = 'WBDHU6')
  wbd <- wbd %>% filter(huc6 == '010300')
  
  # Read in hf divides
  hf_divides <- st_read(hf_path, layer = 'divides', quiet = TRUE)
  hf_divides <- hf_divides %>% filter(vpuid == '01')
  
  # Subset hf_divides for those that intersect with the huc6
  hf_divides <- st_make_valid(hf_divides)
  wbd <- st_make_valid(wbd)
  hf_divides <- st_transform(hf_divides, st_crs(wbd))
  hf_divides <- st_intersection(hf_divides, wbd)
  
  # Read in the hf network
  hf_network <- st_read(hf_path, layer = 'network', quiet = TRUE)
  
  # Extract just the numbers from the id column
  hf_network$id_no <- gsub('.*?([0-9]+).*', '\\1', hf_network$id)
  hf_divides$id_no <- gsub('.*?([0-9]+).*', '\\1', hf_divides$id)
  hf_network <- hf_network %>% filter(id_no %in% hf_divides$id_no)
  
  # Add these divides and network layers to a new geopackage
  # Create a new geopackage
  gpkg_path <- glue::glue('{pkg_dir}/inst/extdata/gpkg_dat/sub_hf_huc_conus_test.gpkg')
  st_write(hf_network, gpkg_path, layer = 'network', driver = 'GPKG')
  st_write(hf_divides, gpkg_path, layer = 'divides', driver = 'GPKG')
}  

gen_sub_hf_huc_conus()
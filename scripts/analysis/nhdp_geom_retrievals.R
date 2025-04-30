#' @title Retrieve the catchment, flowline, and outlet geometries for each comid
#' @author Guy Litt
#' @description Given the 400 queries per hour limit for NLDI database, this 
#' script makes fewer connections (e.g. 390) every 61 minutes
#' @details Originally designed to retrieve the geometries for all RFC locations
# Changelog/contributions
#. 2025-03-16 Originally created, GL
#. 2025-03-19 Converted to function calls, GL
library(nhdplusTools)
library(data.table)
library(dplyr)
library(glue)
library(proc.attr.hydfab)

path_rfc_locs <-   "~/git/formulation-selector/scripts/prediction/rfc_locs/nws_nwm_crosswalk.txt"
dir_save_nhdp <- file.path("~/noaa/regionalization/data/analyses/nhdpv2/") # Place the final output
dir_save_nhdp_chunk <- file.path(dir_save_nhdp,"chunk") # Place the geopackage chunks here
if(!dir.exists(dir_save_nhdp_chunk)){
  dir.create(dir_save_nhdp_chunk,recursive=TRUE)
}

####### Read in comids of interest for RFC locations ########
df <- read.delim(file=path_rfc_locs, # Obtained from Gautam Sood at OWP: a file of all RFC station locations
                 skip=0,sep = "|",col.names = c("nws_station_id","comid")) 
df <- df[-base::grep("-------+-----", df$nws_station_id),]
df <- df[-which(base::is.na(df$comid)),]
col_id <- 'comid'

path_gpkg_glue <- file.path(dir_save_nhdp_chunk,"nhdp_chunked_{seq_num}.gpkg")
# Download the data into chunks
proc.attr.hydfab::dl_nhdplus_geoms_wrap(df = df,col_id=col_id, 
                                        path_gpkg_glue = path_gpkg_glue, 
                                        seq_size = 390,id_type = 'comid',
                                        keep_cols = 'all',)

compile_chunks_ndplus_geoms <- function(dir_save_nhdp_chunk){
  # Compile entire dataset
  # TODO consider whether a custom layer was added (default name 'input_df')
  all_files_rds <- base::list.files(dir_save_nhdp_chunk,pattern = "rds")
  ls_nhdp_all <- base::lapply(all_files_rds, function(x) 
    base::readRDS(base::file.path(dir_save_nhdp_chunk,x)))
  sf_cats_all <- base::lapply(ls_nhdp_all, function(x) x$catchment) %>% 
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE) %>% 
    sf::st_as_sf(crs=4326)
  sf_flowlines_all <- base::lapply(ls_nhdp_all, function(x) x$flowline) %>% 
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE) %>% 
    sf::st_as_sf(crs=4326)
  sf_outlets_all <- lapply(ls_nhdp_all, function(x) x$outlet) %>% 
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE)%>% 
    sf::st_as_sf(crs=4326)
  
  # Munging: catchment may contain multipolygons. These should be singular:
  tot_polys <- lapply(sf_cats_all$geometry, function(x) length(x)) %>% unlist()
  idxs_polys <- which(tot_polys>1) # The multipolygon rows
  ls_poly <- lapply(idxs_polys, function(i) sf_cats_all$geometry[i] %>% sf::st_union() %>%
                      sf::st_cast("POLYGON") %>% unique())
  sf_cats_union <- sf_cats_all
  ctr <- 0
  for(idx_poly in idxs_polys){
    ctr <- ctr+1
    sf_cats_union$geometry[idx_poly] <- ls_poly[[ctr]]
  }
  
  # Write complete geopackage:
  path_save_gpkg_all <- file.path(dir_save_nhdp,"nhdp_cat_line_out.gpkg")
  try(sf::st_write(sf_cats_union,path_save_gpkg_all,layer="catchment"))
  try(sf::st_write(sf_flowlines_all,path_save_gpkg_all,layer="flowlines"))
  try(sf::st_write(sf_outlets_all,path_save_gpkg_all,layer="outlet"))
  if('input_df' %in% base::names(ls_nhdp_all[[1]])){
    # TODO generate input df data.table here
    # TODO add input df layer saving here
    warning("NEED TO ADD input_df SOLUTION HERE")
  }
  print("Completed chunked nhdplus dataset compiling")
}
compile_chunks_ndplus_geoms(dir_save_nhdp_chunk)






library(nhdplusTools)
library(data.table)
library(dplyr)
library(glue)

path_rfc_locs <-   "~/git/formulation-selector/scripts/prediction/rfc_locs/nws_nwm_crosswalk.txt"

dir_save_nhdp <- file.path("~/noaa/regionalization/data/analyses/nhdpv2/") # Place the final output
dir_save_nhdp_chunk <- file.path(dir_save_nhdp,"chunk") # Place the chunks 
if(!dir.exists(dir_save_nhdp_chunk)){
  dir.create(dir_save_nhdp_chunk,recursive=TRUE)
}

####### Read in comids of interest ########
df <- read.delim(file=path_rfc_locs, # Obtained from Gautam Sood at OWP: a file of all RFC station locations
                 skip=0,sep = "|",col.names = c("nws_station_id","comid")) 
df <- df[-base::grep("-------+-----", df$nws_station_id),]
df <- df[-which(base::is.na(df$comid)),]
col_comid <- 'comid'

###### 


# Perform chunking
seq_nums <- base::c(base::seq(from=1,base::nrow(df),390),base::nrow(df))[-1]
ls_nhdp_all <- list()
ctr_seq <- 0
for(seq_num in seq_nums){
  ctr_seq <- ctr_seq + 1
  print(glue::glue("Performing sequence up to {seq_num} of {base::nrow(df)}"))
  if(ctr_seq == 1){
    sub_df <- df[1:seq_num,]
  } else {
    begn_seq <- seq_nums[ctr_seq-1] + 1
    sub_df <- df[begn_seq:seq_num,]
  }
  
  
  # The unique comids for each location
  comids_sub <- base::unique(sub_df[[col_comid]])
  
  # Now acquire the attributes:
  ls_nhdp_chunk <- list()
  ctr <- 0
  for(comid in comids_sub){
    ctr <- ctr + 1
    # Retrieve the data for a comid
    nhdp_all <- try(nhdplusTools::get_nhdplus(comid = comid, realization = 'all'))
    
    if("try-error" %in% class(nhdp_all)){
      warning(glue::glue("Could not retrieve comid {comid}"))
    } else {
      ls_nhdp_chunk[[ctr]] <- nhdp_all
    }
  }
  ###### COMPILE CHUNKS AND WRITE TO FILE #######
  # combine the catchment data:
  sf_cats <- lapply(ls_nhdp_chunk, function(x) x$catchment) %>% 
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE) %>% 
    sf::st_as_sf(crs=4326)
  sf_flowlines <- lapply(ls_nhdp_chunk, function(x) x$flowline) %>% 
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE)%>% 
    sf::st_as_sf(crs=4326)
  sf_outlets <- lapply(ls_nhdp_chunk, function(x) x$ outlet) %>% 
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE)%>% 
    sf::st_as_sf(crs=4326)
   
  path_gpkg <- file.path(dir_save_nhdp_chunk,glue::glue("nhdp_chunked_{seq_num}.gpkg"))
  # Write chunked geopackage:
  try(sf::st_write(sf_cats,path_gpkg,layer="catchment"))
  try(sf::st_write(sf_flowlines,path_gpkg,layer="flowlines"))
  try(sf::st_write(sf_outlets,path_gpkg,layer="outlet"))
  
  path_rds <- base::gsub(pattern="gpkg",replacement="rds",path_gpkg)
  ls_nhdp_chunk <- list(catchment = sf_cats, 
                        flowline=sf_flowlines,outlet = sf_outlets)
  base::saveRDS(ls_nhdp_chunk,path_rds)

  print("Pausing NLDI queries for 61 minutes")
  Sys.sleep(60*61) # 400 NLDI queries per hour
} # End loop over chunks

# TODO Compile entire dataset



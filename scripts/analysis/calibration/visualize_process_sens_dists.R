"""
Assessing the xSSA (Mai et al 2022 process senstivities) across the calibration
locations from 2026 April.
Assessments include:
1) Which locations have insensitive process categories?
2) Which locations are most representative of the different clustered groupsings
and could serve as a test subset?
3) Which locations are most distinct from the different clustered groupings?
Refer to slide results in the following NOAA gdrive link:
https://docs.google.com/presentation/d/1xxE816ZbV_UhpTbwzUWlMO5HX1S51b97u5ApFzh4M9c/edit?slide=id.g3e5f1e2b8a4_0_0#slide=id.g3e5f1e2b8a4_0_0

"""


library(dplyr)
library(arrow)
library(stringr)
library(ggplot2)
library(glue)
library(sf)
library(data.table)
library(factoextra)
dir_dat <- "~/noaa/regionalization/data/output/algorithm_predictions/xSSA_proc_sens_wt_loc_sel_ngencerf"
path_gpkg <- "~/noaa/regionalization/data/input/user_data_std/xSSA_proc_sens_wt_loc_sel_ngencerf2025/xSSA_proc_sens_wt_loc_sel_Raven_blended_loc.gpkg"#"~/noaa/regionalization/data/input/user_data_std/xSSA_proc_sens_wt_loc_sel/headwaterbasins_ngen_cerf/xSSA_proc_sens_wt_loc_sel_Raven_blended_loc.gpkg"
dir_base_insens <- "~/noaa/regionalization/data/analyses/insensitivities/"
if(!dir.exists(dir_base_insens)){
  dir.create(dir_base_insens, recursive = TRUE)
}
df_gpkg <- sf::st_read(path_gpkg, layer = 'outlet')

use_pred_for_mapping <- FALSE
if(use_pred_for_mapping){
  # The dataset for mapping locations
  df_pred <- arrow::read_parquet("~/noaa/regionalization/data/input/user_data_std/xSSA_proc_sens_wt_loc_sel_ngencerf2025/nldi_feat_xSSA_proc_sens_wt_loc_sel_prediction.parquet")
  map_comid_gageid <- df_pred[,c("featureID","gage_id")] %>% unique() # The comid - gage_id mapping

}

fns <- list.files(dir_dat, pattern = 'pred_rf')

# Generate distribution plots
for(fn in fns){
  df <- arrow::read_parquet(file.path(dir_dat,fn))
  name_proc <- stringr::str_split(fn,pattern = "__")[[1]][[1]] %>%
    gsub(pattern= "pred_rf_",replacement="")
  maxval <- max(df$prediction)
  frac_pt1 <- round(length(which(df$prediction < 0.01))/nrow(df),2)
  frac_pt3 <- round(length(which(df$prediction < 0.03))/nrow(df),2)
  plot_out <- ggplot2::ggplot(df,aes(x=prediction)) +
                    geom_histogram(bins = 40) +
                    ggtitle(glue::glue("{name_proc} at ngenCERF locations \n frac below 1%: {frac_pt1} \n frac below 3%: {frac_pt3}")) +
                    xlim(0,maxval)
  print(plot_out)
}
df_gpkg_non_dupe <- df_gpkg[-which(duplicated(df_gpkg$comid)),]
sub_gpkg <- df_gpkg %>% subset(sourceName == "NHDPlus comid")

unique(df_gpkg$sourceName)
unique(df_gpkg$featureSource)
sub_gpkg_nwis <- df_gpkg %>% subset(featureSource == "nwissite")
sub_gpkg_nwis <- sub_gpkg_nwis[-which(duplicated(sub_gpkg_nwis$comid)),]
sub_gpkg_nwis <- sub_gpkg_nwis[which(sub_gpkg_nwis$comid %in% df$featureID),]
sub_gpkg_nwis <- sub_gpkg_nwis %>% rename(featID = "featureID")

#df_gpkg$sourceName %>% unique()
#
# sub_gpkg <- df_gpkg[,c("featureID","gage_id","comid")]
# sub_gpkg <- sub_gpkg[-which(is.na(sub_gpkg$comid)),]

# Locations used for calibration:
gage_ids_calib <- list.files("~/noaa/hydrofabric/hf22_apr26cal/selected_subsets_edited_geom/sites_new_ngsh_edited_geom") %>%
  base::gsub(pattern=".gpkg",replacement="") %>%
  base::gsub(pattern="gage_",replacement="")

# ============================================================================ #
# ---------------------- Identify insensitive locations ---------------------- #
# ============================================================================ #
ls_sub_calib <- list()
for(fn in fns){
  df <- arrow::read_parquet(file.path(dir_dat,fn))

  # Add in the gage_id identifer
  if(use_pred_for_mapping){ #
    df_id <- dplyr::left_join(x=df, y = map_comid_gageid, by = "featureID")
    df_id <- df_id %>% rename(comid = featureID)
    df_cmbo <- merge(df_id, df_gpkg,by.x = "featureID", by.y = "comid")
    df_join <- df_cmbo[-which(duplicated(df_cmbo)),]
  } else {
    # Perform joining and make sure to re-check for missing data
    df_join <- dplyr::left_join(x=df, y=sub_gpkg_nwis,by = dplyr::join_by(featureID == comid))
    rows_miss <- df_join[which(is.na(df_join$featID)),]
    remrge_gpkg <- df_gpkg[unlist(lapply(rows_miss$featureID, function(x) grep(x, df_gpkg$comid))),]
    remrge_gpkg <- remrge_gpkg %>% rename(featID = "featureID")
    sub_gpkg_nwis_add <- base::rbind(sub_gpkg_nwis,remrge_gpkg)
    df_join <- dplyr::left_join(x=df, y=sub_gpkg_nwis_add,by = dplyr::join_by(featureID == comid))
  }
  # Subset to the calibration locations
  sub_calib <- df_join %>% subset(gage_id %in% gage_ids_calib)
  str_metr <- sub_calib$metric[1]
  #sub_calib <- sub_calib %>% rename(!!str_metr :=  prediction)


  ls_sub_calib[[str_metr]] <- sub_calib


}
thr_sens <- 0.015

dt_calib <- data.table::rbindlist(ls_sub_calib)

insens_calib <- dt_calib[dt_calib$prediction < thr_sens]
insens_metrs <- unique(insens_calib$metric)

ls_insens <- list()
ls_sens <- list()
for(im in insens_metrs){
  dt_metr <- dt_calib %>% subset(metric == im) %>% select(c("gage_id","name","metric", "prediction"))
  insens_locs <- dt_metr %>% subset(prediction<thr_sens)
  sens_locs <- dt_metr %>% subset(prediction>=thr_sens)
  print(glue::glue("{im} num sensitive > {thr_sens}: {nrow(sens_locs)}"))
  ls_insens[[im]] <- insens_locs
  ls_sens[[im]] <- sens_locs


}

# Basic requirement: gage_id and metric column to represent the insensitive locations & process category
dt_insens <- data.table::rbindlist(ls_insens)
write.csv(dt_insens,file = file.path(dir_base_insens,glue::glue("ngencerf2025_thr{thr_sens}.csv")),row.names = FALSE)







# TODO read in parameter mapping df for each formulation
# ============================================================================ #
# ============================================================================ #
# ============================================================================ #
# Create small test dataset based on different clusters in process sensitivities
# ============================================================================ #
# From dt_calib:

sub_dt_xssa <- dt_calib[,c("gage_id","metric","prediction")] %>% as.data.table()
dt_xssa_wide <- data.table::dcast(sub_dt_xssa, gage_id ~ metric, value.var = "prediction")
dt_xssa_wide <- dt_xssa_wide[,-"S_wt_delay_ro"] # Remove one of the inconsequential convolution params

metric_cols <- setdiff(names(dt_xssa_wide), "gage_id")
cluster_data <- scale(dt_xssa_wide[, ..metric_cols]) # Every metric has mean 0 and std dev 1
rownames(cluster_data) <- dt_xssa_wide$gage_id

# Method A: Silhouette Plot
p_sil <- factoextra::fviz_nbclust(cluster_data, kmeans, method = "silhouette") +
  labs(title = "Optimal k: Silhouette Method")
print(p_sil)

# Method B: Elbow Plot
p_wss <- fviz_nbclust(cluster_data, kmeans, method = "wss") +
  labs(title = "Optimal k: Elbow Method")
print(p_wss)

library(data.table)
library(factoextra)
library(ggplot2)

# 1. Run K-means
set.seed(123)
km_result <- kmeans(cluster_data, centers = 6, nstart = 25)

# 2. Add the cluster assignments back to your data.table
# (Convert to factor so ggplot treats them as distinct categories, not a continuous gradient)
dt_xssa_wide[, cluster_group := as.factor(km_result$cluster)]



# 3. Plot the clusters using fviz_cluster
# This automatically performs PCA to squash all your metrics into 2 dimensions
p_cluster <- fviz_cluster(km_result,
                          data = cluster_data,
                          geom = "point",           # Use c("point", "text") if you want row names
                          ellipse.type = "convex",  # Draws polygons around the groups
                          palette = "Set2",         # Color scheme
                          ggtheme = theme_minimal(),
                          main = "K-Means Cluster Groupings")

# Print the plot
print(p_cluster)

# Calculate the mean of all metrics, grouped by the cluster
cluster_summary <- dt_xssa_wide[, lapply(.SD, mean, na.rm = TRUE),
                                by = cluster_group,
                                .SDcols = is.numeric]

print(cluster_summary)

#### Find the most-representative location in each cluster:
# 1. Create an empty list to store our results
rep_list <- list()

# 2. Loop through each cluster to find the closest point
# (Assuming final_k is your number of clusters, e.g., 3)
final_k <- max(km_result$cluster)

for (i in 1:final_k) {

  # A. Get the centroid coordinates for cluster i
  centroid <- km_result$centers[i, ]

  # B. Find which rows in our data belong to cluster i
  cluster_indices <- which(km_result$cluster == i)

  # C. Extract just those points from the scaled data
  cluster_points <- cluster_data[cluster_indices, , drop = FALSE]

  # D. Calculate the Euclidean distance from each point to the centroid
  # We use apply to run the distance math (sqrt of sum of squared differences) across rows
  distances <- apply(cluster_points, 1, function(row) {
    sqrt(sum((row - centroid)^2))
  })

  # E. Find the index of the absolute minimum distance
  min_dist_idx <- which.min(distances)

  # F. Map that back to the original row number to get the gage_id
  original_row_num <- cluster_indices[min_dist_idx]
  best_gage <- dt_xssa_wide$gage_id[original_row_num]

  # G. Store the result
  rep_list[[i]] <- data.table(
    cluster_group = as.factor(i),
    rep_gage_id = best_gage,
    dist_to_center = distances[min_dist_idx]
  )
}

# 3. Combine the list into a single data.table
rep_dt <- rbindlist(rep_list)

# 4. Merge this back onto your cluster_summary from the previous step
cluster_summary <- merge(cluster_summary, rep_dt, by = "cluster_group")

print(cluster_summary)

# Generate plot of each location and relative differences in the sensitivities:
library(data.table)
library(ggplot2)

# 1. Extract the representative gage IDs we found in the previous step
rep_gages <- rep_dt$rep_gage_id

# 2. Filter the wide data to ONLY include our representative gages
dt_rep_wide <- dt_xssa_wide[gage_id %in% rep_gages]

# 3. Pivot the filtered data BACK to long format
# 'id.vars' are the columns we want to keep as identifiers.
# Everything else (your metrics) will be squashed into a 'metric' column.
dt_rep_long <- melt(dt_rep_wide,
                    id.vars = c("gage_id", "cluster_group"),
                    variable.name = "metric",
                    value.name = "prediction_value")

# Note: Depending on your metrics, some might be negative (like certain KGE values).
# Stacked bar charts require positive values to represent physical proportions correctly.
# If you have negatives, you may want to take the absolute value or normalize them first:
# dt_rep_long[, prediction_value := abs(prediction_value)]

# 4. Generate the Plot
# The magic happens with `position = "fill"`.
# This automatically forces the bars to normalize so the Y-axis goes from 0 to 1 (100%).
p_bars <- ggplot(dt_rep_long, aes(x = as.factor(gage_id),
                                  y = prediction_value,
                                  fill = metric)) +
  geom_col(position = "fill", color = "white", linewidth = 0.2) +

  # Grouping the x-axis visually by cluster can be helpful
  facet_grid(~ cluster_group, scales = "free_x", space = "free_x",
             labeller = label_both) +

  scale_y_continuous(labels = scales::percent_format()) +
  theme_minimal() +
  labs(title = "Metric Proportions of Representative Cluster Gages",
       x = "Representative Gage ID",
       y = "Proportion of Total",
       fill = "Metric") +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

print(p_bars)

################################## MOST DISTANT ###############################
library(data.table)

# 1. Setup
k_groups <- sort(unique(km_result$cluster))
n_groups <- length(k_groups)

# Start by picking the first point in each cluster as our initial guesses
current_reps <- sapply(k_groups, function(i) which(km_result$cluster == i)[1])

# 2. Alternating Maximization Loop
max_iter <- 20
for(iter in 1:max_iter) {
  changed <- FALSE

  for(i in 1:n_groups) {
    # Get the row indices of all points in the current cluster
    pts_in_cluster <- which(km_result$cluster == k_groups[i])

    # Get the coordinates of the current representatives from the OTHER clusters
    other_reps_idx <- current_reps[-i]
    other_coords <- cluster_data[other_reps_idx, , drop = FALSE]

    # Calculate the sum of Euclidean distances from EVERY point in this cluster
    # to the current representatives of the other clusters.
    # (Using t() allows R's vector recycling to do this math extremely fast)
    sum_dists <- apply(cluster_data[pts_in_cluster, , drop = FALSE], 1, function(pt) {
      sum(sqrt(colSums((t(other_coords) - pt)^2)))
    })

    # Find the index of the point that maximizes this distance
    best_local_idx <- pts_in_cluster[which.max(sum_dists)]

    # Update if we found a point further away
    if(current_reps[i] != best_local_idx) {
      current_reps[i] <- best_local_idx
      changed <- TRUE
    }
  }

  # If we complete a full loop and no points moved, we found the optimal dispersed set
  if(!changed) break
}

# 3. Extract the final results
distant_dt <- data.table(
  cluster_group = as.factor(k_groups),
  distant_gage_id = dt_xssa_wide$gage_id[current_reps],
  data_row_index = current_reps
)

print(distant_dt)


pca_res <- prcomp(cluster_data)
pca_df <- as.data.frame(pca_res$x)
pca_df$gage_id <- dt_xssa_wide$gage_id
# Assuming pca_df is already created from the previous plotting step
distant_points_pca <- pca_df[distant_dt$data_row_index, ]

# Overlay on your existing cluster plot (p)
p_distant <- p +
  geom_point(data = distant_points_pca,
             aes(x = PC1, y = PC2),
             color = "red",       # Use a bright color like red
             shape = 17,          # Shape 17 is a solid triangle
             size = 6) +
  geom_label_repel(data = distant_points_pca,
                   aes(x = PC1, y = PC2, label = gage_id),
                   color = "red",
                   fontface = "bold")

print(p_distant)

#=========
library(sf)
library(ggplot2)
library(ggrepel)
library(maps)

# 1. Load the CONUS basemap (EPSG:4326)
us_basemap <- st_as_sf(maps::map("state", plot = FALSE, fill = TRUE))
us_basemap <- st_set_crs(us_basemap, 4326)

# 2. Filter and merge your spatial dataframe (gdf)
# We use 'merge' to attach the cluster_group assignments to the geometries
distant = FALSE
if(distant){
  gdf_distant <- merge(df_gpkg, distant_dt, by.x = "gage_id", by.y = "distant_gage_id")
  titl <- "CONUS Mapping: Maximally Dispersed Cluster Elements"
  subtitl <- "Gage locations representing the geometric boundary extremes of each cluster"
} else {
  #gage_ids_sel <- c("04273700","01493500","09499000","13186000","12210000","14301000","01118000", "14216500","09404343")
  #gage_ids_sel <- c("04273700","01493500","09499000","13186000","12210000","14301000",small_dt_improv$gage_id)
  gage_ids_sel <- c("04273700","01493500","09499000","13186000","12210000","14301000","08315480", "05275000", "0810464660")
  gdf_distant <- df_gpkg[df_gpkg$gage_id %in% gage_ids_sel,]
  df_sel_clst <- as.data.frame(km_result$cluster[gage_ids_sel])
  names(df_sel_clst) <- "cluster_group"
  df_sel_clst$gage_id <- names(km_result$cluster[gage_ids_sel])
  df_sel_clst$cluster_group <- as.factor(as.integer(df_sel_clst$cluster_group))
  gdf_distant <- merge(gdf_distant, df_sel_clst, by="gage_id")

}

gdf_distant <- st_as_sf(gdf_distant, sf_column_name = "geom", crs = 4326)

# 3. Create the multi-layer map
p_distant_map <- ggplot() +
  # Layer 1: Basemap
  geom_sf(data = us_basemap, fill = "#f8fafc", color = "#cbd5e1") +

  # Layer 2: The extreme boundary gages (using a bold triangle shape)
  geom_sf(data = gdf_distant,
          aes(color = cluster_group),
          size = 4,
          shape = 17) +

  # Layer 3: Dynamic labels with matching background colors
  geom_label_repel(
    data = gdf_distant,
    aes(label = gage_id, geometry = geom, fill = cluster_group),
    stat = "sf_coordinates",
    min.segment.length = 0,
    segment.color = "gray30",
    color = "white", # White text inside the colored label box
    fontface = "bold",
    box.padding = 0.8,
    point.padding = 0.5
  ) +

  # Layer 4: Albers Equal Area visual projection
  coord_sf(crs = 5070,
           xlim = c(-2500000, 2500000),
           ylim = c(200000, 3200000)) +

  # Styling (Using 'Set1' for strong, high-contrast colors)
  scale_color_brewer(palette = "Set1") +
  scale_fill_brewer(palette = "Set1") +
  theme_minimal() +
  labs(title = titl,
       subtitle = subtitl,
       x = NULL,
       y = NULL,
       color = "Cluster",
       fill = "Cluster") +
  theme(panel.grid.major = element_line(color = "gray90", linetype = "dashed"),
        legend.position = "bottom")

print(p_distant_map)

# TODO how does this tie-in with probable-winner?

df_gpkg[grep("FL",df_gpkg$name),]
###############################################################################
############# Checking the drainage area/total divides ##################
path_gpkg <- "~/noaa/regionalization/data/input/user_data_std/xSSA_proc_sens_wt_loc_sel_ngencerf2025/xSSA_proc_sens_wt_loc_sel_Raven_blended_loc.gpkg"#"~/noaa/regionalization/data/input/user_data_std/xSSA_proc_sens_wt_loc_sel/headwaterbasins_ngen_cerf/xSSA_proc_sens_wt_loc_sel_Raven_blended_loc.gpkg"

library(glue)
library(sf)
library(dplyr)
if(!dir.exists(dir_base_insens)){
  dir.create(dir_base_insens, recursive = TRUE)
}
df_gpkg <- sf::st_read(path_gpkg, layer = 'outlet')
gage_ids_sel <- c("04273700","01493500","09499000","13186000","12210000","14301000",)
# Add the extra 3 locations corresponding to poor performance (and new spatial locs)
#gage_ids_sel <- c("04273700","01493500","09499000","13186000","12210000","14301000","01118000", "14216500","09404343")
gage_ids_sel <- c("04273700","01493500","09499000","13186000","12210000","14301000","08315480", "05275000", "0810464660")
sub_df_gpkg <- df_gpkg[df_gpkg$gage_id %in% gage_ids_sel,]

dir_hf <- "~/noaa/hydrofabric/hf22_apr26cal/selected_subsets_edited_geom/sites_new_ngsh_edited_geom/"
fns_hf <- list.files(dir_hf)
sel_fns_hf <- glue::glue("gage_{gage_ids_sel}.gpkg")

ls_areas <- list()
for(selfn in sel_fns_hf){
  gpkg <- sf::st_read(file.path(dir_hf, selfn),layer='divides') %>% suppressMessages()
  print(glue::glue("{selfn} Areasqkm: {sum(gpkg$areasqkm)}"))
  ls_areas[[selfn]] <- data.frame(gpkg = selfn,
                                  areasqkm = sum(gpkg$areasqkm),
                                  n_divs = nrow(gpkg))

}



data.table::rbindlist(ls_areas)

####Add a few more locations that have corresponded to better NWMv3 performance
need_to_improve <- c("01073500",
                     "01118000",
                     "01162500",
                     "01390450",
                     "01616500",
                     "02140991",
                     "02343225",
                     "04208000",
                     "04234000",
                     "05275000",
                     "05383950",
                     "05411850",
                     "05413500",
                     "05426000",
                     "05447500",
                     "05567500",
                     "05570000",
                     "06809210",
                     "07164600",
                     "07348700",
                     "07372200",
                     "08013000",
                     "810464660",
                     "08152900",
                     "08315480",
                     "09404343",
                     "14216500"
                     ) %>% as.character()
idxs_improve <- unlist(lapply(need_to_improve, function(x) grep(x, fns_hf)))
fns_improve <- fns_hf[idxs_improve]
ls_areas_imprv <- list()
for(fnimp in fns_improve){
  gpkg <- sf::st_read(file.path(dir_hf, fnimp),layer='divides') %>% suppressMessages()
  print(glue::glue("{selfn} Areasqkm: {sum(gpkg$areasqkm)}"))
  ls_areas_imprv[[fnimp]] <- data.frame(gpkg = fnimp,
                                  areasqkm = sum(gpkg$areasqkm),
                                  n_divs = nrow(gpkg))


}
dt_improv <- data.table::rbindlist(ls_areas_imprv)
dt_improv$gage_id <- base::gsub("gage_","",dt_improv$gpkg) %>% base::gsub(pattern=".gpkg",replacement="")

small_dt_improv <- dt_improv[dt_improv$n_divs <200,]

# Now work with the clusters and pick three from different groups
km_result_sub_clst <- km_result$cluster[small_dt_improv$gage_id]
km_result_sub_clst %>% unique()
df_sub_clst <- as.data.frame(km_result_sub_clst)
df_sub_clst$gage_id <- names(km_result_sub_clst)
df_sub_clst_improv <- base::merge(small_dt_improv, df_sub_clst, by = 'gage_id')
df_sub_clst_improv[order(df_sub_clst_improv$areasqkm),]




# Choices in locations:
sel_clst_improv <- c("01118000", "14216500","09404343")
df_sub_clst_improv[df_sub_clst_improv$gage_id %in% sel_clst_improv,c("gage_id","areasqkm","n_divs","km_result_sub_clst")] %>% rename(clust_num = km_result_sub_clst)


names(km_result_sub_clst)
# REVISED choice on locations after looking at map locations:
sel_clst_improv <- c("08315480", "05275000", "0810464660")
df_sub_clst_improv[df_sub_clst_improv$gage_id %in% sel_clst_improv,c("gage_id","areasqkm","n_divs","km_result_sub_clst")] %>% rename(clust_num = km_result_sub_clst)


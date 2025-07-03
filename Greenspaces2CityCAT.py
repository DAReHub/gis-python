# -*- coding: utf-8 -*-
"""
This script processes green space vector data from Ordnance Survey MasterMap and converts it into a CityCAT-compatible .txt format.
The process includes merging multiple green space shapefiles, clipping them to the area of interest,
handling MultiPolygon geometries, and exporting the data for use in CityCAT flood modelling.
"""

import arcpy
from arcpy import env
import geopandas as gpd
import sys
import os
from citycatio.inputs import GreenAreas

arcpy.env.overwriteOutput = True  # allowed overwrite

# # For green spaces, we need to merge and clip the shapefiles first, and then convert them into citycat readable format.

input_folder = r"C:\MasterMap Greenspace_6015283\nz" # GreenSpace shapefiles are obtained from OS database - Mastermap
boundary_shp = r"C:\TyneWear.shp" # places of study interest
output_folder = r"C:\GreenSpace_output"

# Step 1：merge all the Shapefile
arcpy.env.workspace = input_folder
shp_list = arcpy.ListFeatureClasses("*.shp")

merged_shp = output_folder + r"\merged_greenspace.shp"
arcpy.management.Merge(shp_list, merged_shp)
print(f"merge finished，in total {len(shp_list)} files")

# step 2：clip
clipped_shp = output_folder + r"\greenspace_clipped.shp"
arcpy.analysis.Clip(merged_shp, boundary_shp, clipped_shp)
print("clip finished，output：", clipped_shp)


# # Convert green spaces shapefile into citycat readable format
gdf = gpd.read_file('C:\\Newcastle_TRB\\GreenSpace_output\\greenspace_clipped.shp')
print("Shapefile read successfully！")
print(gdf.geom_type.value_counts())  # number of geometry


# manually add GDAL DLL pathway
gdal_dll_path = r"C:\ProgramData\Anaconda2024\envs\myenv\Library\bin"
if sys.version_info >= (3, 8):
    os.add_dll_directory(gdal_dll_path)


# turn MultiPolygon into Polygons
gdf = gdf.explode(ignore_index=True)
print("All multipolygon processed successfully! Start to write")

# write GreenAreas
GreenAreas(gdf).write('.')

### Print the outputs of the file to check
with open('GreenAreas.txt') as f:
    print(*f.readlines()[:10])

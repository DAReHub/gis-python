# -*- coding: utf-8 -*-
"""
This script processes building vector data from Ordnance Survey (OS) and converts it into a CityCAT-compatible .txt format.
The process includes clipping the building shapefile to the area of interest, handling MultiPolygon geometries,
and exporting the data for use in CityCAT flood modelling.
"""

import arcpy
from arcpy import env
import geopandas as gpd
import sys
import os
from citycatio.inputs import Buildings

arcpy.env.overwriteOutput = True  # allowed overwrite


# # For buildings, we need to clip the shapefiles first, and then convert them into citycat readable format.
# # read input data
building_shp = r"C:\open-map-local_6015284\NZ_Building.shp" # Building shapefile is obtained from OS database - vector - open map local
boundary_shp = r"C:\TyneWear.shp" # places of study interest
output_folder = r"C:\Newcastle_TRB\Building_output"

# clip
clipped_shp = output_folder + r"\building_clipped.shp"
arcpy.analysis.Clip(building_shp, boundary_shp, clipped_shp)
print("clip finished，output：", clipped_shp)

gdf = gpd.read_file(clipped_shp)
print("Shapefile read successfully")
print(gdf.geom_type.value_counts())  # number of geometry

# manually add GDAL DLL pathway
gdal_dll_path = r"C:\ProgramData\Anaconda2024\envs\myenv\Library\bin"
if sys.version_info >= (3, 8):
    os.add_dll_directory(gdal_dll_path)


# turn MultiPolygon into Polygons
gdf = gdf.explode(ignore_index=True)
print("All multipolygon processed successfully! Start to write")

Buildings(gdf).write('.')

with open('Buildings.txt') as f:
# with open('Buildings_wholeMan.txt') as f:
    print(*f.readlines()[:10])


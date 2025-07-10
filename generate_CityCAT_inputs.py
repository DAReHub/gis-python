# -*- coding: utf-8 -*-
"""
This script processes green space vector data from Ordnance Survey MasterMap and converts it into a CityCAT-compatible .txt format.
The process includes merging multiple green space shapefiles, clipping them to the area of interest,
handling MultiPolygon geometries, and exporting the data for use in CityCAT flood modelling.
"""

import geopandas as gpd
from citycatio.inputs import GreenAreas, Buildings  # TODO: Find a way of installing without conda
from pathlib import Path
import pandas as pd
import argparse
import utils


def main(feature: str, feature_dir: str, output_dir: str,
         crs: str, boundary_path: str = None, feature_ext: str = '.shp'):

    input_path = Path(feature_dir)
    output_dir = Path(output_dir)
    filepaths = list(input_path.glob(f"*{feature_ext}"))
    print(filepaths)

    gdfs = []
    for filepath in filepaths:
        gdfs.append(utils.load_gdf(filepath, crs))

    print('processing')
    gdf = pd.concat(gdfs, axis=0, ignore_index=True)

    if boundary_path:
        mask = utils.load_gdf(Path(boundary_path), crs)
        gdf = gpd.clip(gdf, mask, keep_geom_type=False)

    gdf = gdf.explode(ignore_index=True)

    if feature == 'greenspaces':
        GreenAreas(gdf).write(output_dir)
    elif feature == 'buildings':
        Buildings(gdf).write(output_dir)

    print('Done')


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Convert OS Greenspace to CityCAT format")
    p.add_argument('--feature', choices=['buildings', 'greenspaces'])
    p.add_argument('--input_dir_feature', required=True, help='Path to directory containing Greenspace or Buildings shp/gpkg/csv/geojson files')
    p.add_argument('--feature_ext', required=False, help='(optional) Feature file extension - i.e. .shp .gpkg .csv or .geojson; default .shp')
    p.add_argument('--input_dir_boundary', required=False, help='(optional) Path to boundary shp/gpkg/csv/geojson file')
    p.add_argument('--output_dir', required=True, help='Path for .txt output')
    p.add_argument('--crs', required=True, help='CRS EPSG code without "EPSG:" e.g. "27700"')
    args = p.parse_args()

    main(
        feature=args.feature,
        feature_dir=args.input_dir_feature,
        output_dir=args.output_dir,
        crs=args.crs,
        boundary_path=args.input_dir_boundary,
        feature_ext=args.feature_ext,
    )
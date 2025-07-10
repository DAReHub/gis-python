# -*- coding: utf-8 -*-
"""
This script processes green space vector data from Ordnance Survey MasterMap and converts it into a CityCAT-compatible .txt format.
The process includes merging multiple green space shapefiles, clipping them to the area of interest,
handling MultiPolygon geometries, and exporting the data for use in CityCAT flood modelling.
"""

import geopandas as gpd
from citycatio import utils as citycat_utils
from citycatio.inputs import GreenAreas, Buildings  # TODO: Find a way of installing without conda
from pathlib import Path
import pandas as pd
import argparse
import utils
import os


def main(feature: str, feature_dir: str, output_dir: str,
         crs: str, feature_ext: str, boundary_path: str = None):

    input_path = Path(feature_dir)
    output_dir = Path(output_dir)
    filepaths = list(input_path.glob(f"*{feature_ext}"))

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
    elif feature == 'rainfall':
        with open(os.path.join(output_dir, 'Rainfall.txt'), 'w') as f:
            f.write(citycat_utils.geoseries_to_string(gdf.geometry))

    print('Done')


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Convert OS Greenspace/Buildings/Rainfall to CityCAT format")
    p.add_argument(
        '--feature',
        required=True,
        choices=['buildings', 'greenspaces', 'rainfall'],
        type=str
    )
    p.add_argument(
        '--input_dir_feature',
        required=True,
        help='Path to directory containing Greenspace or Buildings shp/gpkg/csv/geojson files',
        type=str
    )
    p.add_argument(
        '--feature_ext',
        required=False,
        help='(optional) Feature file extension - i.e. .shp .gpkg .csv or .geojson; default .shp',
        default='.shp',
        type=str
    )
    p.add_argument(
        '--input_dir_boundary',
        required=False,
        help='(optional) Path to boundary shp/gpkg/csv/geojson file',
        type=str
    )
    p.add_argument(
        '--output_dir',
        required=False,
        default='.',
        help='(optional) Path for .txt output',
        type=str
    )
    p.add_argument(
        '--crs',
        required=True,
        help='CRS EPSG code without "EPSG:" e.g. "27700"',
        type=str
    )
    args = p.parse_args()

    main(
        feature=args.feature,
        feature_dir=args.input_dir_feature,
        output_dir=args.output_dir,
        crs=args.crs,
        feature_ext=args.feature_ext,
        boundary_path=args.input_dir_boundary,
    )
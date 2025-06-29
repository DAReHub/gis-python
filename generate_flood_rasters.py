# generates .tif files from CityCAT .rsl outputs

import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from rasterio.features import rasterize
from shapely.geometry import Point
import os
from pathlib import Path


def main(input_dir: str, output_dir: str, crs: str, cellsize: int):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    filepaths = list(input_path.glob("*.rsl"))

    for filepath in filepaths:
        filename = os.path.basename(filepath).replace('.rsl', '')
        print('Processing', filename)

        print('-> Loading')
        df = pd.read_csv(filepath, sep='\s+', header=0)
        geometry = [Point(xy) for xy in zip(df['XCen'], df['YCen'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=f"EPSG:{crs}")

        print('-> Building raster')
        xmin, ymin, xmax, ymax = gdf.total_bounds
        width = int((xmax - xmin) / cellsize)
        height = int((ymax - ymin) / cellsize)
        transform = from_origin(xmin, ymax, cellsize, cellsize)
        shapes = ((geom, val) for geom, val in zip(gdf.geometry, gdf['Depth']))
        raster = rasterize(
            shapes=shapes,
            out_shape=(height, width),
            fill=0,  # background value for empty cells
            transform=transform,
            dtype='float32'  # or 'int32' if your values are integers
        )

        output_filepath = (output_path / filename).with_suffix('.tif')
        print('-> Writing to', output_filepath)
        with rasterio.open(
            output_filepath,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=raster.dtype,
            crs=gdf.crs,
            transform=transform,
        ) as dst:
            dst.write(raster, 1)

    print('Done')


if __name__ == "__main__":
    main(
        input_dir="",  # path to .rsl outputs
        output_dir="",  # path for .tif outputs
        crs="",  # str without "EPSG:" e.g. "27700"
        cellsize=5  # int (metres), the cellsize defined in CityCAT Domain_DEM.asc input
    )
# generates .tif files from CityCAT .rsl outputs

import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from rasterio.features import rasterize
from shapely.geometry import Point
from pathlib import Path
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed

def process_file(filepath: Path, output_path: Path, crs: str, cellsize: int):
    filename = filepath.stem
    print(f"Processing {filename}")

    # Load dataframe
    df = pd.read_csv(filepath, sep='\s+', header=0)
    geometry = [Point(xy) for xy in zip(df['XCen'], df['YCen'])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=f"EPSG:{crs}")

    # Build raster
    xmin, ymin, xmax, ymax = gdf.total_bounds
    width = int((xmax - xmin) / cellsize)
    height = int((ymax - ymin) / cellsize)
    transform = from_origin(xmin, ymax, cellsize, cellsize)
    shapes = ((geom, val) for geom, val in zip(gdf.geometry, gdf['Depth']))
    raster = rasterize(
        shapes=shapes,
        out_shape=(height, width),
        fill=0,
        transform=transform,
        dtype='float32'
    )

    # Write output
    output_filepath = (output_path / filename).with_suffix('.tif')
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
    print(f"Written {output_filepath}")


def main(input_dir: str, output_dir: str, crs: str, cellsize: int, multithread: bool, workers: int):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filepaths = list(input_path.glob("*.rsl"))

    if multithread:
        print(f"Running in parallel mode with {workers} workers...")
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process_file, fp, output_path, crs, cellsize) for fp in filepaths]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error processing file: {e}")
    else:
        print("Running in sequential mode...")
        for fp in filepaths:
            process_file(fp, output_path, crs, cellsize)

    print('Done')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert .rsl files to GeoTIFFs")
    parser.add_argument('--input_dir', required=True, help='Path to .rsl files')
    parser.add_argument('--output_dir', required=True, help='Path for .tif outputs')
    parser.add_argument('--crs', required=True, help='CRS EPSG code without "EPSG:" e.g. "27700"')
    parser.add_argument('--cellsize', type=int, default=5, help='Cell size in units of the CRS')
    parser.add_argument('--multithread', action='store_true', help='Enable parallel processing')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker processes if multithreading')
    args = parser.parse_args()

    main(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        crs=args.crs,
        cellsize=args.cellsize,
        multithread=args.multithread,
        workers=args.workers
    )
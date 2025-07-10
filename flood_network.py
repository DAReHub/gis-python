# This script assigns flood depths and subsequent vehicle velocities to each
# link within a network.
# Inputs - cityCAT floodmap output directory, transport network

import geopandas as gpd
from exactextract import exact_extract
from pathlib import Path
import argparse
import utils

# unreferenced but used by other packages
import pyogrio  # for faster exporting
import rasterio # for loading in rasters with exactextract

def exlude_network_modes(df, excluded_modes, mode_name):
    if not excluded_modes and not mode_name:
        print("-> not excluding any links based on mode")
        return df
    elif excluded_modes and not mode_name:
        raise Exception("-> excluded_modes provided but no network_modes_name")
    elif mode_name and not excluded_modes:
        print("-> network_modes_name provided but not any excluded_modes - not excluding any links based on mode")
        return df
    else:
        print("Excluding mode links: ", ', '.join(excluded_modes))
        return df.loc[~df[mode_name].isin(excluded_modes)]


def buffer_network(df, factor, lanes_name):
    if lanes_name:
        df["geometry"] = df.buffer(df[lanes_name] * factor)
    else:
        print("-> LANE column not provided, defaulting to a single lane width buffer")
        df["geometry"] = df.buffer(1 * factor)
    return df


def remove_false_positive_categories(df):
    # TODO: Remove bridges (and maybe connecting links)
    pass


def zonal_statistics(filepaths, network, id, statistic):
    print("calculating zonal statistics")
    ngdf = network[[id, 'geometry']].copy()
    gdf = exact_extract(
        rast=filepaths,
        vec=ngdf,
        ops=statistic,
        include_cols=[id],
        include_geom=True,
        output="pandas",
        strategy="raster-sequential",
        # progress=True
    )
    merged = network.merge(gdf.drop(columns='geometry'), on=id, how="inner")

    # if single file processed, column name will be just <statistic>. Add filename
    if statistic in merged.columns:
        merged = merged.rename(columns={statistic: filepaths[0].stem + "_" + statistic})

    return gpd.GeoDataFrame(merged, geometry=gdf.geometry)


# Method: https://doi.org/10.1016/j.trd.2017.06.020
def calculate_velocity(depth, freespeed, A, B, C, x_min):
    if depth == 0:
        return freespeed
    if depth > x_min:
        return 0
    max_v_in_flood_kmh = (A * depth**2) + (B * depth) + C
    max_v_in_flood_ms = max_v_in_flood_kmh / 3.6
    # if maximum velocity when flooded is greater than the speed limit, then
    # default to the speed limit
    if max_v_in_flood_ms > freespeed:
        return freespeed
    return max_v_in_flood_ms


def vehicle_velocity(gdf, link_depth, freespeed):
    print("calculating vehicle velocities")
    # y = Ax**2 + Bx + C
    A, B, C = 0.0009, -0.5529, 86.9448
    # Find x at min y (curve does not go beyond this). 0 speed if greater.
    x_min = -B / (2 * A)

    stat_columns = [col for col in gdf.columns if col.endswith("_" + link_depth)]
    for column in stat_columns:
        layer = column.replace("_" + link_depth, "_velocity")
        # Convert depth value from m to mm: * 1000
        gdf[layer] = gdf.apply(
            lambda row: calculate_velocity(
                row[column]*1000, row[freespeed], A, B, C, x_min
            ),
            axis=1
        )

    return gdf


def export_gpkg(gdf, filepath):
    filepath = filepath.with_suffix(".gpkg")
    print("Exporting to file: ", filepath)
    gdf.to_file(filepath, driver="GPKG", engine="pyogrio")


def export_csv(gdf, filepath):
    filepath = filepath.with_suffix(".csv")
    print("Exporting to file: ", filepath)
    # TODO: Instead of dropping geometry, turn to WKT
    # gdf['geometry'] = gdf['geometry'].apply(
    #     lambda geom: geom.wkt if geom else None)
    df = gdf.drop(columns='geometry')
    df = df.fillna("null")
    df.to_csv(filepath, index=False)


def main(
    network_filepath: str,
    floodmap_dir: str,
    output_dir: str,
    crs: str,
    network_id_name: str,
    network_freespeed_name: str,
    network_lanes_name: str,
    network_buffer_factor: float,
    depth_statistic: str = "max",
    network_modes_name: str = None,
    excluded_modes: list = None,
):

    floodmap_dir = Path(floodmap_dir)
    output_dir = Path(output_dir)

    filepaths = list(floodmap_dir.glob("*.tif"))

    print("Preparing network")
    gdf_network = utils.load_gdf(network_filepath, crs)
    gdf_network = exlude_network_modes(gdf_network, excluded_modes, network_modes_name)
    gdf_network = buffer_network(gdf_network, network_buffer_factor, network_lanes_name)

    gdf = zonal_statistics(
        filepaths, gdf_network, network_id_name, depth_statistic,
    )
    gdf = vehicle_velocity(gdf, depth_statistic, network_freespeed_name)

    output = output_dir / "flooded_network"
    export_gpkg(gdf, output)
    export_csv(gdf, output)

    print("Done")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        '--network_filepath',
        required=True,
        type=str
    )
    p.add_argument(
        '--floodmap_dir',
        required=True,
        help='Directory path to floodmap .tif files',
        type=str
    )
    p.add_argument(
        '--output_dir',
        required=False,
        default=".",
        type=str
    )
    p.add_argument(
        '--crs',
        required=True,
        help='CRS EPSG code without "EPSG:" e.g. "27700"',
        type=str
    )
    p.add_argument(
        '--network_buffer_factor',
        required=True,
        type=float
    )
    p.add_argument(
        "--excluded_modes",
        type=lambda s: [item.strip() for item in s.split(",")],
        default=None,
        help='Modes to exclude as comma-separated values e.g. rail,bus,subway',
        required=False
    )
    p.add_argument(
        '--network_id_name',
        required=False,
        default="ID",
        help='Name of the network ID field',
        type=str
    )
    p.add_argument(
        '--network_freespeed_name',
        required=True,
        default="FRSPEED",
        help='Name of the network freespeed field',
        type=str
    )
    p.add_argument(
        '--network_modes_name',
        required=False,
        default=None,
        help='(optional) Name of the network modes field',
        type=str
    )
    p.add_argument(
        '--network_lanes_name',
        required=False,
        default=None,
        help='(optional) Name of the network lanes field',
        type=str
    )
    p.add_argument(
        "--depth_statistic",
        required=False,
        default="max",
        type=str,
        help="Default=max, for options see: https://isciences.github.io/exactextract/operations.html"
    )
    args = p.parse_args()

    main(
        network_filepath=args.network_filepath,
        floodmap_dir=args.floodmap_dir,
        output_dir=args.output_dir, # TODO: make directory if doesn't exist
        crs=args.crs,
        network_id_name=args.network_id_name,
        network_freespeed_name=args.network_freespeed_name,
        network_lanes_name=args.network_lanes_name,
        network_buffer_factor= args.network_buffer_factor,
        depth_statistic=args.depth_statistic,
        network_modes_name=args.network_modes_name,
        excluded_modes=args.excluded_modes,
    )
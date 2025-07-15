# This script assigns flood depths and subsequent vehicle velocities to each
# link within a network.
# Inputs - cityCAT floodmap output directory, transport network

import geopandas as gpd
from exactextract import exact_extract
from pathlib import Path
import argparse
import utils
import xml.etree.ElementTree as ET
import pandas as pd
from shapely.geometry import LineString

# unreferenced but used by other packages
import pyogrio  # for faster exporting
import rasterio # for loading in rasters with exactextract


def read_pt2_network(filepath, crs):
    tree = ET.parse(filepath)
    root = tree.getroot()

    nodes = root.findall('.//node')
    node_id = [node.get('id') for node in nodes if node.get('id') is not None]
    node_x = [node.get('x') for node in nodes if node.get('x') is not None]
    node_y = [node.get('y') for node in nodes if node.get('y') is not None]
    df_nodes = pd.DataFrame({'node_id': node_id, 'node_x': node_x, 'node_y': node_y})

    links = root.findall('.//link')
    link_id = [link.get('id') for link in links if link.get('id') is not None]
    link_from = [link.get('from') for link in links if link.get('from') is not None]
    link_to = [link.get('to') for link in links if link.get('to') is not None]
    link_freespeed = [float(link.get('freespeed')) for link in links if link.get('freespeed') is not None]
    link_modes = [link.get('modes') for link in links if link.get('modes') is not None]
    link_lanes = [int(float(link.get('permlanes'))) for link in links if link.get('permlanes') is not None]
    df_links = pd.DataFrame({
        'ID': link_id,
        'from_node': link_from,
        'to_node': link_to,
        'FRSPEED': link_freespeed,
        'MODES': link_modes,
        'LANES': link_lanes
    })

    df = df_links.merge(
        df_nodes.rename(
            columns={'node_id': 'from_node', 'node_x': 'from_x', 'node_y': 'from_y'}
        ),
        on='from_node',
        how='left'
    )
    df = df.merge(
        df_nodes.rename(
            columns={'node_id': 'to_node', 'node_x': 'to_x', 'node_y': 'to_y'}
        ),
        on='to_node',
        how='left'
    )
    df['geometry'] = df.apply(
        lambda row: LineString([(row.from_x, row.from_y), (row.to_x, row.to_y)]),
        axis=1
    )
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=f"EPSG:{crs}")
    gdf = gdf.drop(columns=['from_x', 'from_y', 'to_x', 'to_y', 'from_node', 'to_node'])

    return gdf


def exlude_network_modes(df, excluded_modes):
    def mode_list(mode_str):
        modes = mode_str.split(',')
        return any(m in excluded_modes for m in modes)

    if not excluded_modes:
        print("-> not excluding any links based on mode")
        return df
    else:
        print("Excluding mode links: ", ', '.join(excluded_modes))
        return df.loc[~df['MODES'].apply(mode_list)]


def buffer_network(df, factor):
    df["geometry"] = df.buffer(df['LANES'] * factor)
    return df


def remove_false_positive_categories(df):
    # TODO: Remove bridges (and maybe connecting links)
    pass


def zonal_statistics(filepaths, network, statistic):
    print("calculating zonal statistics")
    ngdf = network[['ID', 'geometry']].copy()
    gdf = exact_extract(
        rast=filepaths,
        vec=ngdf,
        ops=statistic,
        include_cols=['ID'],
        include_geom=True,
        output="pandas",
        strategy="raster-sequential",
        # progress=True
    )
    merged = network.merge(gdf.drop(columns='geometry'), on='ID', how="inner")

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


def vehicle_velocity(gdf, link_depth):
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
                row[column]*1000, row['FRSPEED'], A, B, C, x_min
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
    network_from: str,
    network_buffer_factor: float,
    depth_statistic: str = "max",
    excluded_modes: list = None,
):

    floodmap_dir = Path(floodmap_dir)
    output_dir = Path(output_dir)

    filepaths = list(floodmap_dir.glob("*.tif"))

    print("Preparing network")
    if network_from == "VIA":
        gdf_network = utils.load_gdf(network_filepath, crs)
    elif network_from == "PT2":
        gdf_network = read_pt2_network(network_filepath, crs)
    gdf_network = exlude_network_modes(gdf_network, excluded_modes)
    gdf_network = buffer_network(gdf_network, network_buffer_factor)

    gdf = zonal_statistics(filepaths, gdf_network, depth_statistic)
    gdf = vehicle_velocity(gdf, depth_statistic)

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
        '--network_from',
        required=False,
        choices=['PT2', 'VIA'],
        default='PT2',
        type=str,
        help='Default=PT2, where the network file was generated - either in'
             ' PT2-matsim as an xml or in VIA as a shp/gpkg'
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
        network_from=args.network_from,
        network_buffer_factor= args.network_buffer_factor,
        depth_statistic=args.depth_statistic,
        excluded_modes=args.excluded_modes,
    )
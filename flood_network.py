# This script assigns flood depths and subsequent vehicle velocities to each
# link within a network.
# Inputs - cityCAT floodmap output directory, transport network


import os
import fiona
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from exactextract import exact_extract
import json

# unreferenced but used by other packages
import pyogrio  # for faster exporting
import rasterio # for loading in rasters with exactextract


def load_config(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)


def load_network(filepath, CRS):
    with fiona.open(filepath) as src:
        geometries = [shape(feature['geometry']) for feature in src]
        properties = [feature['properties'] for feature in src]
    gdf = gpd.GeoDataFrame(properties, geometry=geometries)
    if not 'FRSPEED' in gdf.columns:
        raise Exception('FRSPEED not found in network')
    return gdf.set_crs(CRS)


def exlude_network_modes(df, excluded_modes):
    if 'MODES' in df.columns:
        return df.loc[~df["MODES"].isin(excluded_modes)]
    print("-> MODES column not found, all links will remain")
    return df


def buffer_network(df, factor):
    if 'LANES' in df.columns:
        df["geometry"] = df.buffer(df["LANES"] * factor)
    else:
        print("-> LANE column not found, defaulting to a single lane width buffer")
        df["geometry"] = df.buffer(1 * factor)
    return df


def remove_false_positive_categories(df):
    # TODO: Remove bridges (and maybe connecting links)
    pass


def prepare_network(network_filepath, excluded_modes, network_buffer_factor, CRS):
    print("Preparing network")
    gdf = load_network(network_filepath, CRS)
    gdf = exlude_network_modes(gdf, excluded_modes)
    return buffer_network(gdf, network_buffer_factor)


def zonal_statistics(filepaths, network, id, statistic, extension):
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
        filename = filepaths[0].split("/")[-1].replace(extension, "")
        merged = merged.rename(columns={statistic: filename + "_" + statistic})

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
                row[column]*1000, row["FRSPEED"], A, B, C, x_min
            ),
            axis=1
        )

    return gdf


def export_gpkg(gdf, filepath):
    print("Exporting to file: ", filepath + ".gpkg")
    gdf.to_file(filepath + ".gpkg", driver="GPKG", engine="pyogrio")


def export_csv(gdf, filepath):
    print("Exporting to file: ", filepath + ".csv")
    # TODO: Instead of dropping geometry, turn to WKT
    # gdf['geometry'] = gdf['geometry'].apply(
    #     lambda geom: geom.wkt if geom else None)
    df = gdf.drop(columns='geometry')
    df = df.fillna("null")
    df.to_csv(filepath + ".csv", index=False)


def main(config_filepath, network_filepath, floodmap_dir, output_dir):
    if not floodmap_dir.endswith("/"):
        floodmap_dir += "/"
    if not output_dir.endswith("/"):
        output_dir += "/"

    config = load_config(config_filepath)["flood_network"]
    filepaths = [floodmap_dir + file for file in os.listdir(floodmap_dir) if
                 file.endswith(config["extension"])]

    gdf_network = prepare_network(
        network_filepath,
        config["excluded_modes"],
        config["network_buffer_factor"],
        config["CRS"]
    )
    gdf = zonal_statistics(
        filepaths,
        gdf_network,
        config["network_id_column"],
        config["link_depth"],
        config["extension"]
    )
    gdf = vehicle_velocity(gdf, config["link_depth"])

    output = output_dir + "flooded_network"
    export_gpkg(gdf, output)
    export_csv(gdf, output)

    print("Done")


if __name__ == "__main__":
    main(
        config_filepath="",
        network_filepath="",
        floodmap_dir="",
        output_dir=""
    )
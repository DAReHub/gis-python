# This script assigns flood depths and subsequent vehicle velocities to each
# link within a network.
# Inputs - cityCAT floodmap output directory, transport network


import os
import fiona
import geopandas as gpd
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
    return gdf.set_crs(CRS)


def exlude_network_modes(df, excluded_modes):
    return df.loc[~df["MODES"].isin(excluded_modes)]


def buffer_network(df, factor):
    df["geometry"] = df.buffer(df["LANES"] * factor)
    return df


def remove_false_positive_categories(df):
    # TODO: Remove bridges (and maybe connecting links)
    pass


def prepare_network(network_filepath, excluded_modes, network_buffer_factor, CRS):
    print("Preparing network")
    gdf = load_network(network_filepath, CRS)
    gdf = exlude_network_modes(gdf, excluded_modes)
    return buffer_network(gdf, network_buffer_factor)


def zonal_statistics(floodmap, network, statistic):
    print("calculating zonal statistics")
    gdf = exact_extract(
        rast=floodmap,
        vec=network,
        ops=statistic,
        include_cols=["ID"],
        include_geom=True,
        output="pandas",
        # progress=True
    )
    merged = network.merge(gdf.drop(columns='geometry'), on="ID", how="inner")
    return gpd.GeoDataFrame(merged, geometry=gdf.geometry)


# Method: https://doi.org/10.1016/j.trd.2017.06.020
def calculate_velocity(depth, freespeed, A, B, C, x_min):
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
    A = 0.0009
    B = -0.5529
    C = 86.9448
    # Find x at min y (curve does not go beyond this). 0 speed if greater.
    x_min = -B / (2 * A)
    # Convert depth value from m to mm: * 1000
    gdf["velocity"] = gdf.apply(
        lambda row: calculate_velocity(
            row[link_depth]*1000, row["FRSPEED"], A, B, C, x_min
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
    config = load_config(config_filepath)["flood_network"]

    gdf_network = prepare_network(
        network_filepath,
        config["excluded_modes"],
        config["network_buffer_factor"],
        config["CRS"]
    )

    for file in os.listdir(floodmap_dir):
        if not file.endswith(config["extension"]):
            continue

        print("Processing: ", file)

        # TODO: Standardise input and output naming
        floodmap_filepath = floodmap_dir + file
        output_filepath = output_dir + file.replace(".tif", "_flooded_network")

        gdf = zonal_statistics(floodmap_filepath, gdf_network, config["link_depth"])
        gdf = vehicle_velocity(gdf, config["link_depth"])

        export_gpkg(gdf, output_filepath)
        export_csv(gdf, output_filepath)

    print("Done")


if __name__ == "__main__":
    main(
        config_filepath="",
        floodmap_dir="",
        network_filepath="",
        output_dir=""
    )
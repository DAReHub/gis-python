# This script assigns flood depths and subsequent vehicle velocities to each
# link within a network.
# Inputs - cityCAT floodmap output directory, transport network


import os
import fiona
import pyogrio  # utilised for faster exporting
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
from rasterstats import zonal_stats


floodmap_dir = "test/data/flooding_maps_citiCAT/"
floodmap_extension = ".tif"
network_filepath = "test/data/network/Newcastle_network_VIA.shp"
output_dir = "test/flood_network_outputs/"
network_buffer_factor = 3.65 / 2
CRS = 27700
excluded_modes = ["rail", "bus", "subway"]
depths_column = "VALUE"
aggregated_depths_column = "value_agg"
link_depth = "max"  # which depth of the link to use for speed calculation - "min", "max", "mean"


def load_network(filepath):
    with fiona.open(filepath) as src:
        geometries = [shape(feature['geometry']) for feature in src]
        properties = [feature['properties'] for feature in src]
    df = gpd.GeoDataFrame(properties, geometry=geometries)
    return df.set_crs(CRS)


def exlude_network_modes(df, excluded_modes):
    return df.loc[~df["MODES"].isin(excluded_modes)]


def buffer_network(df, factor):
    df["geometry"] = df.buffer(df["LANES"] * factor)
    return df


def remove_false_positive_categories(df):
    # TODO: Remove bridges (and maybe connecting links)
    pass


def prepare_network():
    print("Preparing network")
    gdf = load_network(network_filepath)
    gdf = exlude_network_modes(gdf, excluded_modes)
    return buffer_network(gdf, network_buffer_factor)


def zonal_statistics(gdf, filepath):
    print("calculating zonal statistics")
    return gdf.join(
        pd.DataFrame(
            zonal_stats(
                vectors=gdf['geometry'],
                raster=filepath,
                stats=["count", "min", "max", "mean", "sum", "std", "median",
                       "majority", "minority", "unique", "range"],
                all_touched=True
            )
        ),
        how='left'
    )


def calculate_velocity(depth, freespeed):
    v_kmh = (0.0009 * depth**2) - (0.5529 * depth) + 86.9448
    v_ms = v_kmh / 3.6
    if v_ms > freespeed:
        return freespeed
    return v_ms


# Method: https://doi.org/10.1016/j.trd.2017.06.020
def vehicle_velocity(gdf):
    print("calculating vehicle velocities")
    # Convert depth value from m to mm: * 1000
    gdf["velocity"] = gdf.apply(
        lambda row: calculate_velocity(row[link_depth]*1000, row["FRSPEED"]),
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


def main():
    gdf_network = prepare_network()

    for file in os.listdir(floodmap_dir):
        if not file.endswith(floodmap_extension):
            continue

        print("Processing: ", file)

        # TODO: Standardise input and output naming
        floodmap_filepath = floodmap_dir + file
        output_filepath = output_dir + file.replace(".tif", "_flooded_network")

        gdf = zonal_statistics(gdf_network, floodmap_filepath)
        gdf = vehicle_velocity(gdf)

        export_gpkg(gdf, output_filepath)
        export_csv(gdf, output_filepath)

    print("Done")


if __name__ == "__main__":
    main()
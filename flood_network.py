import os
import rasterio
from rasterio.features import shapes
import numpy as np
import fiona
import pyogrio
import geopandas as gpd
from shapely.geometry import shape


floodmap_dir = "cityCAT_example_data/flooding_maps_citiCAT/"
floodmap_extension = ".tif"
network_filepath = "network/Newcastle_network_VIA.shp"
output_dir = "test_outputs/all/"
value_threshold = 0.005
depths = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
network_buffer_factor = 3.65 / 2
CRS = 27700
excluded_modes = ["rail", "bus", "subway"]
depths_column = "VALUE"
aggregated_depths_column = "value_agg"


def raster_pixels_to_polygons(tif_filepath, value_column):
    with rasterio.Env():
        with rasterio.open(tif_filepath) as src:
            image = src.read(1).astype(np.float32)
            results = (
                {"properties": {value_column: v}, "geometry": s}
                for i, (s, v) in enumerate(shapes(image, transform=src.transform))
            )
    geoms = list(results)
    df = gpd.GeoDataFrame.from_features(geoms)
    df = df.set_crs(CRS)
    return df


def filter_polygons(df, value_column, value_threshold):
    return df.loc[df[value_column] >= value_threshold]


# Checks which depth range the value is within, and raises it to the upper limit
# Returns 9999 if above the last depth value
def assign_depth(value_column, depths):
    if value_column < depths[0]:
        return depths[0]
    for i in range(1, len(depths)):
        if depths[i-1] < value_column <= depths[i]:
            return depths[i]
    return 9999


def assign_values(df, value_column, new_column, depths):
    df[new_column] = df[value_column].apply(lambda x: assign_depth(x, depths))
    return df


def dissolve_polygons(df, value_column):
    return df.dissolve(by=value_column).reset_index()


def multipart_to_singlepart(df):
    df["singleparts"] = df.apply(lambda x: [p for p in x.geometry.geoms], axis=1)
    df = df.explode("singleparts")
    df = df.set_geometry("singleparts")
    del (df["geometry"])
    return df.rename_geometry("geometry")


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


def join_attribute_by_location(df_network, df_floods):
    df_network = df_network.set_crs(CRS)
    df_floods = df_floods.set_crs(CRS)
    return df_network.sjoin(df_floods, how="left", predicate="intersects")


def remove_false_positive_categories(df):
    # TODO: Remove bridges (and maybe connecting links)
    pass


def prepare_network():
    print("Preparing network")
    df = load_network(network_filepath)
    df = exlude_network_modes(df, excluded_modes)
    return buffer_network(df, network_buffer_factor)


def process_floodmap(floodmap_filepath):
    df = raster_pixels_to_polygons(floodmap_filepath, depths_column)
    df = filter_polygons(df, depths_column, value_threshold)
    df = assign_values(df, depths_column, aggregated_depths_column, depths)
    df = dissolve_polygons(df, aggregated_depths_column)
    return multipart_to_singlepart(df)


def export_gpkg(df, filepath):
    print("Exporting to file: ", filepath + ".gpkg")
    df = df[["ID", "VALUE", "value_agg", "FRSPEED", "geometry"]]
    df.to_file(filepath + ".gpkg", driver="GPKG", engine="pyogrio")


def export_csv(df, filepath):
    print("Exporting to file: ", filepath + ".csv")
    df = df[["ID", "VALUE", "value_agg", "FRSPEED"]]
    df.to_csv(filepath + ".csv", index=False)


def main():
    df_network = prepare_network()

    for file in os.listdir(floodmap_dir):
        if not file.endswith(floodmap_extension):
            continue
        print("Processing: ", file)

        floodmap_filepath = floodmap_dir + file
        output_filepath = output_dir + file.replace(".tif", "_flooded_network")

        try:
            df_floods = process_floodmap(floodmap_filepath)
            df = join_attribute_by_location(df_network, df_floods)
        except Exception as e:
            print(f"Failed to process {file} -> {e}")
            continue

        export_gpkg(df, output_filepath)
        export_csv(df, output_filepath)

    print("Done")


if __name__ == "__main__":
    main()
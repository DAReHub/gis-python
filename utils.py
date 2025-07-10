import pandas as pd
import geopandas as gpd
import fiona
import shapely
from shapely.geometry import shape
from pathlib import Path


def load_gdf(filepath, crs: str):
    filepath = Path(filepath)
    if filepath.suffix == '.shp':
        return load_shapefile(filepath, crs)
    elif filepath.suffix == '.gpkg':
        return load_geopackage(filepath, crs)
    elif filepath.suffix == '.csv':
        return load_csv(filepath, crs)
    elif filepath.suffix == '.geojson':
        return load_geojson(filepath)


def load_shapefile(filepath, crs):
    print('loading shapefile:', filepath)
    with fiona.open(filepath) as src:
        geometries = [shape(feature['geometry']) for feature in src]
        properties = [feature['properties'] for feature in src]
    gdf = gpd.GeoDataFrame(properties, geometry=geometries)
    return gdf.set_crs(crs)


def load_geopackage(filepath, crs):
    print('loading geopackage:', filepath)
    gdf = gpd.read_file(filepath)
    return gdf.set_crs(epsg=crs)


def load_csv(filepath, crs):
    print('loading csv:', filepath)
    df = pd.read_csv(filepath)

    try:
        return gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df.lon, df.lat),
            crs=f"EPSG:{crs}"
        )
    except Exception:
        print("No 'lat' 'lon' fields found in csv, trying WKT")

    try:
        df["geometry"] = df["wkt_geom"].apply(shapely.wkt.loads)
        return gpd.GeoDataFrame(df, geometry="geometry", crs=f"EPSG:{crs}")
    except Exception:
        print("No 'lat' 'lon' fields or 'wkt_geom' fields found in csv")
        raise Exception


def load_geojson(filepath):
    return gpd.read_file(filepath)
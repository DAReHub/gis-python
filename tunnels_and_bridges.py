import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import shape, LineString
import pyogrio

# TODO:
#  Custom OSM input to go into flood_network (write another script to deal with OSM, only extracting linestrings) osm_way_os = osm_id
#  flood_network outputs to go into here

# TODO: move to utils
def load_shapefile(filepath, CRS):
    print('loading shapefile:', filepath)
    with fiona.open(filepath) as src:
        geometries = [shape(feature['geometry']) for feature in src]
        properties = [feature['properties'] for feature in src]
    gdf = gpd.GeoDataFrame(properties, geometry=geometries)
    return gdf.set_crs(CRS)


def extract_by_attributes(gdf):
    print('extracting highway and railway attributes')
    return gdf[gdf['highway'].notnull() | gdf['railway'].notnull()]


def extract_asset(gdf, asset):
    print('extracting asset:', asset)
    return gdf[gdf['other_tags'].str.contains(asset, na=False)]


def extract_by_location(gdf1, gdf2):
    print('extracting by location')
    gdf1 = gdf1.set_crs(epsg=27700)  # TODO: Remove hard coding
    gdf2 = gdf2.set_crs(epsg=27700)
    gdf = (
        gpd.sjoin(gdf1, gdf2, how="inner", predicate="crosses")
        .rename(columns=lambda c: c[:-5] if c.endswith("_left") else c)
        .loc[:, lambda df: ~df.columns.str.endswith("_right")]
    )
    return gdf[~gdf.index.duplicated(keep="first")]


def explode_linestrings(gdf):
    print('exploding')

    def segments(ls):
        pts = list(ls.coords)
        return [LineString(pts[i:i + 2]) for i in range(len(pts) - 1)]

    return (
        gdf
        .assign(segments=gdf.geometry.apply(segments))
        .explode(column='segments', index_parts=False)
        .set_geometry('segments')
        .drop(columns='geometry')
        .rename_geometry('geometry')
        .reset_index(drop=True)
    )


def add_osm_attribute(gdf):
    print('adding new OSM attribute')
    gdf = gdf.reset_index(drop=True)
    # gdf['osm_id_section'] = gdf['osm_id'] + '_' + gdf.index.astype(str)
    gdf['osm_id'] = gdf['osm_id'] + '_' + gdf.index.astype(str)
    return gdf


def remove_ids(gdf1, gdf2):
    return gdf1[~gdf1["osm_id"].isin(set(gdf2["osm_id"].unique()))]


def concatenate_ids(gdf1, gdf2):
    gdf1 = gdf1.set_crs(epsg=27700)  # TODO: Remove hard coding
    gdf2 = gdf2.set_crs(epsg=27700)
    return pd.concat([gdf1, gdf2], axis=0, ignore_index=True)


def export_gpkg(gdf, filepath):
    print("Exporting to file: ", filepath + ".gpkg")
    gdf.to_file(filepath + ".gpkg", driver="GPKG", engine="pyogrio")


def main(network_filepath):
    network = load_shapefile(network_filepath, 27700)  # TODO: Remove hard coding
    network_road_rail = extract_by_attributes(network)
    network_tunnels = extract_asset(network_road_rail, 'tunnel')
    network_bridges = extract_asset(network_road_rail, 'bridge')

    # extract sections of links (not to be flooded) which are not labelled
    # bridge but go over a tunnel (could be flooded)
    network_tunnel_cross = extract_by_location(network_road_rail, network_tunnels)
    network_tunnel_exploded = explode_linestrings(network_tunnel_cross)
    network_tunnel_exploded = add_osm_attribute(network_tunnel_exploded) # TODO: this is reduntant if a new column is created
    network_tunnel_sections = extract_by_location(network_tunnel_exploded, network_tunnels)

    # bridges can't flood and so are removed
    vulnerable_links = remove_ids(network_road_rail, network_bridges)

    # replace the whole link which crosses a tunnel with its exploded sections
    vulnerable_links = remove_ids(vulnerable_links, network_tunnel_cross)
    vulnerable_links = concatenate_ids(vulnerable_links, network_tunnel_exploded)

    # remove the sections of links which cross tunnels
    vulnerable_links = remove_ids(vulnerable_links, network_tunnel_sections)

    return vulnerable_links

    # export_gpkg(vulnerable_links, "test/tunnels_and_bridges_outputs/vulnerable_links")

    # vulnerable_links = set(vulnerable_links["osm_id"])
    # network_road_rail_set = set(network_road_rail["osm_id"])
    # immune_links = network_road_rail_set - vulnerable_links


if __name__ == '__main__':
    main(
        network_filepath='test/data/tunnels_and_bridges/network_27700/network_27700.shp'
    )
    print("Done - use GIS software to check the validity of the output for your"
          " use case and to perform manual edits")
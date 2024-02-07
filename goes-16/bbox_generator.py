import os
import argparse
import shapely
import fiona
import json
import numpy as np
from pyproj import Proj,transform
from shapely.geometry import shape
from geojson import Polygon, Feature, FeatureCollection

# from geojson import Polygon, Feature, FeatureCollection
# from geopy.distance import geodesic

def generate_bounding_box_geojson(center_point, startDate, endDate, box_size_acres=10):

    box_size_km = box_size_acres*0.00404686
    center_latitude, center_longitude = center_point

    # Calculate bounding box corners
    min_latitude = center_latitude - (box_size_km / 2) / 111.32  # 1 degree of latitude is approximately 111.32 km
    max_latitude = center_latitude + (box_size_km / 2) / 111.32
    min_longitude = center_longitude - (box_size_km / 2) / (111.32 * abs(np.cos(np.radians(center_latitude))))
    max_longitude = center_longitude + (box_size_km / 2) / (111.32 * abs(np.cos(np.radians(center_latitude))))

    # Create GeoJSON Polygon
    polygon_coordinates = [
        (min_longitude, min_latitude),
        (min_longitude, max_latitude),
        (max_longitude, max_latitude),
        (max_longitude, min_latitude),
        (min_longitude, min_latitude)
    ]
    polygon = Polygon([polygon_coordinates])

    # Create GeoJSON Feature
    feature = Feature(geometry=polygon)
    # features['properties'
    feature.properties['Start Date']=startDate
    feature.properties['End Date']=endDate

    return feature


def shapelyFile(root,files):
    try:
        for file in files:
            if file.endswith(".shp") == False:
                continue
            with fiona.open(os.path.join(root, file)) as shp:
                crs = shp.crs
                epsg_code = crs['init'].split(':')[1]
                print("EPSG Code:", epsg_code)
                for feature in shp:
                    # Extract the geometry
                    
                    geometry = feature['geometry']
                    property = feature['properties']
                    shapely_geometry = shape(geometry)
                    # Convert the geometry to a Shapely object

                    acres= property['poly_GISAc']
                    # latitude = property['']
                    fireDisoveryDateTime = property['attr_Fir_7']
                    fireControlDateTime = property['attr_Contr']
                    bounding_box = shapely_geometry.bounds
                    if acres<10.0:
                        continue
                    # for prop,val in vars(property)['_data'].items():
                    #     print(prop," : ", val)

                    print("start date: ", fireDisoveryDateTime )
                    print("End Date: ",fireControlDateTime)
                    print("Acres: ", acres)
                    print("Geometry Type:", shapely_geometry.geom_type)
                    print("Area:", shapely_geometry.area)
                    print("Bounding Box:", shapely_geometry.bounds)
                    bounding_box_geojson = generate_bounding_box_geojson([ (bounding_box[0]+bounding_box[2])/2, (bounding_box[1]+bounding_box[3])/2 ], fireDisoveryDateTime, fireControlDateTime)
                    print(bounding_box_geojson)

    except Exception as e:
        print("Exception Occurred")
        print(e)

def main(new_path: os):
    # print(new_path)
    print(os.path.isdir(new_path))
    for root, dir, files in os.walk(new_path):
        shapelyFile(root,files)
        

def read_files() -> None:
    base_path = os.getcwd()
    new_path = os.path.join(base_path,"nifc")
    # print(new_path)
    main(new_path)
    

read_files()
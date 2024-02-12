import os
import shapely
import fiona
import json
import numpy as np
from pyproj import Proj,transform
from shapely.geometry import shape
from geojson import Polygon, Feature

def generate_bounding_box_geojson(center_point, startDate, endDate, box_size_acres=10):
    box_size_km = box_size_acres*0.00404686
    box_size_km=324
    center_latitude, center_longitude = center_point

    min_latitude = center_latitude - (box_size_km / 2) / 111.111
    max_latitude = center_latitude + (box_size_km / 2) / 111.111
    min_longitude = center_longitude - (box_size_km / 2) / (111.321 * abs(np.cos(np.radians(center_latitude))))
    max_longitude = center_longitude + (box_size_km / 2) / (111.321 * abs(np.cos(np.radians(center_latitude))))

    # Create GeoJSON Polygon
    polygon_coordinates = [
        (min_longitude, max_latitude),
        (min_longitude, min_latitude),
        (max_longitude, min_latitude),
        (max_longitude, max_latitude),
        (min_longitude, max_latitude)
    ]
    polygon=Polygon()
    polygon['coordinates']=[polygon_coordinates]
    feature = Feature(geometry=polygon)
    feature.properties['Start Date']=startDate
    feature.properties['End Date']=endDate

    finalJson ={
        "type":"FeatureCollection",
        "features":[feature]
    }
    return finalJson


def dumpjson(root:os, bounding_box_geojson, filename:str):
    json_dump_dir = os.path.join(os.path.dirname(root),'geojson')
    filename+=".geojson"
    with open(os.path.join(json_dump_dir,filename),'w') as json_file:
        json.dump(bounding_box_geojson, json_file,indent=2)


#reading 
def shapelyFile(root:os,files:os):
    try:
        for file in files:
            if file.endswith(".shp") == False:
                continue
            with fiona.open(os.path.join(root, file)) as shp:

                # To see EPSG Code
                # crs = shp.crs
                # epsg_code = crs['init'].split(':')[1]
                # print("EPSG Code:", epsg_code)

                for feature in shp:
                    
                    geometry = feature['geometry']
                    property = feature['properties']
                    shapely_geometry = shape(geometry)

                    sourceOID = property["poly_Sourc"]
                    acres= property['poly_GISAc']
                    fireDisoveryDateTime = property['attr_Fir_7']
                    fireControlDateTime = property['attr_Conta']
                    bounding_box = shapely_geometry.bounds
                    if acres<10.0:
                        continue

                    # To get all attributes in property
                    # for prop,val in vars(property)['_data'].items():
                    #     print(prop," : ", val)

                    bounding_box_geojson = generate_bounding_box_geojson(( (bounding_box[1]+bounding_box[3])/2, (bounding_box[0]+bounding_box[2])/2 ), fireDisoveryDateTime, fireControlDateTime)
                    dumpjson(root, bounding_box_geojson,str(sourceOID))
    except Exception as e:
        print("Exception Occurred")
        print(e)

# Give path for script
def read_file(new_path: os):
    for root, dir, files in os.walk(new_path):
        shapelyFile(root,files)
        

def main() -> None:
    base_path = os.getcwd()
    new_path = os.path.join(base_path,"nifc")
    read_file(new_path)

main()
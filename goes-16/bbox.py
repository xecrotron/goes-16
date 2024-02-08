import json
from typing import List
import os
import datetime


class Point:
    def __init__(self, x: float, y:float) -> None:
        self.x: float = x
        self.y: float = y

    def __str__(self) -> str:
        return f"(x:{self.x}, y:{self.y})"

    @classmethod
    def from_list(cls, lis):
        return cls(lis[0], lis[1])

class Bbox:
    def __init__(self, box:List[Point], id:str, path, start_date:datetime=None, end_date:datetime=None) -> None:
        self.box = box
        self.id = id
        self.path = path
        self.start = start_date
        self.end = end_date

    def __str__(self) -> str:
        return f"{self.id}: p1: {self.box[0]}\n p2: {self.box[1]}\n p3: {self.box[2]}\n p4: {self.box[3]}\nStart & End date time: {self.start} - {self.end}"

class Bboxs:
    def __init__(self, boxes: List[Bbox]) -> None:
        self.boxes = boxes
        
    @classmethod
    def read_file(cls, read_datetime:bool=False):

        boxes = []
        for file in os.listdir("./geojson/"):
            with open(f"./geojson/{file}", 'r') as f:
                data = json.load(f)

            for b_box in data["features"]:
                points = []
                coord = b_box["geometry"]["coordinates"][0][:4]
                for p in coord:
                    points.append(Point.from_list(p))

                start_date = None
                end_date = None
                if read_datetime:
                    start_date = datetime.datetime.strptime(b_box['properties']['start_date'], '%Y-%m-%dT%H:%M:%SZ')
                    end_date = datetime.datetime.strptime(b_box['properties']['end_date'], '%Y-%m-%dT%H:%M:%SZ')
                boxes.append(Bbox(points, file.replace(".json", ""), f"./geojson/{file}", start_date, end_date))
        return cls(boxes)


if __name__ == "__main__":
    data = Bboxs.read_file()
    for box in data.boxes:
        print(box)

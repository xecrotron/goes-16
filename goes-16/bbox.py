import json
from typing import List
import os


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
    def __init__(self, box:List[Point], id:str, path) -> None:
        self.box = box
        self.id = id
        self.path = path

    def __str__(self) -> str:
        return f"{self.id}: p1: {self.box[0]}\n p2: {self.box[1]}\n p3: {self.box[2]}\n p4: {self.box[3]}\n"

class Bboxs:
    def __init__(self, boxes: List[Bbox]) -> None:
        self.boxes = boxes
        
    @classmethod
    def read_file(cls):
        boxes = []
        for file in os.listdir("./geojson/"):
            with open(f"./geojson/{file}", 'r') as f:
                data = json.load(f)

            for b_box in data["features"]:
                points = []
                coord = b_box["geometry"]["coordinates"][0][:4]
                for p in coord:
                    points.append(Point.from_list(p))
                boxes.append(Bbox(points, file.replace(".json", ""), f"./geojson/{file}"))
        return cls(boxes)


if __name__ == "__main__":
    data = Bboxs.read_file()
    for box in data.boxes:
        print(box)

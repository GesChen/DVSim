from procthor.generation import HouseGenerator

generator = HouseGenerator(split="train")

house = generator.sample()

house_dict = house.data

import json

with open("house.json", "w") as f:
    json.dump(house_dict, f, indent=2)
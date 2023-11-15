import json

with open(f'./key/config.json') as f:
    config = json.load(f)


PASSWORD = config["PASSWORD"]

print(PASSWORD)
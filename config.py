import os
import platform
import json

BASE_PATH = os.getcwd()

SECRET_KEY = ""

with open(f'{BASE_PATH}/key/config.json') as f:
    config = json.load(f)
USERNAME = config["USERNAME"]
PASSWORD = config["PASSWORD"]
api = config["API"]
Clipdrop_api = config["CLIPDROP_API"]
MESHY_API_KEY = config["MESHY_API_KEY"]

MONGO_DB = {
    "host": "",
    "port": os.environ.get("MONGO_PORT", "27017"),
    "user": os.environ.get("MONGO_APP_USER", f"{USERNAME}"),
    "password": os.environ.get("MONGO_APP_PASSWORD", f"{PASSWORD}"),
    "db": "stable",
}

MONGO_URL_ADMIN = "mongodb://%s:%s/admin" % (MONGO_DB["host"], MONGO_DB["port"])

DB_NAME = MONGO_DB["db"]

MONGO_URL = (
    "mongodb://%s:%s@%s:%s/"
    % (MONGO_DB["user"], MONGO_DB["password"], MONGO_DB["host"], MONGO_DB["port"])
    + MONGO_DB["db"]
    + "?authSource=admin"
)



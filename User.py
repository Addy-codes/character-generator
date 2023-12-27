from pymongo import MongoClient
import json
from config import (
    BASE_PATH,
    SECRET_KEY, 
    MONGO_URL, 
    DB_NAME, 
    USERNAME, 
    PASSWORD,
    api,
    Clipdrop_api,
    MESHY_API_KEY,
    REIMAGINE_API_KEY,
    )

class User:
    def __init__(self, username, password, models, permissions=[]):
        self.username = username
        self.password = password  # Plain text password (not recommended)
        self.models = models  # List of models, each with model_id and model_type
        self.permissions = permissions

    @classmethod
    def create_user(cls, username, password, model_id, model_type, permissions=[]):
        new_user = cls(username, password, model_id, model_type, permissions)
        users_collection.insert_one(vars(new_user))

    @classmethod
    def authenticate(cls, username, entered_password):
        user_data = users_collection.find_one({'username': username})
        if user_data and user_data['password'] == entered_password:
            return cls(**user_data)
        return None
    
    # Method to add a model to the user
    @staticmethod
    def add_model(username, model_id, model_type):
        users_collection.update_one(
            {'username': username},
            {'$push': {'models': {'model_id': model_id, 'model_type': model_type}}}
        )
    
    # Method to add a permission to the user
    @staticmethod
    def add_permission(username, permission):
        users_collection.update_one(
            {'username': username},
            {'$push': {'permissions': permission}}
        )

    # Method to remove a permission from the user
    @staticmethod
    def remove_permission(username, permission):
        users_collection.update_one(
            {'username': username},
            {'$pull': {'permissions': permission}}
        )

    def to_dict(self):
        return {
            "username": self.username,
            "password": self.password,
            "models": self.models,
            "permissions": self.permissions 
        }

users = [
    User(
        'user1', 
        'password1', 
        [
            {'id': '1', 'name': 'Pop Art Style', 'model_id': 'c64117c4-0010-471b-a7b9-caa5663b33a9', 'model_type': '$style'}, 
            {'id': '2', 'name': 'Indian Epic 1', 'model_id': '3c6079cb-18d7-4a23-bc4d-357299b29c54', 'model_type': '$style'},
            {'id': '3', 'name': 'Abhi Ch1', 'model_id': 'c27ba912-7fe1-4a23-bd3b-8514e99415eb', 'model_type': '$style'}
        ], 
        ['var', '3d', 'bgrem']
    ),
    User(
        'rimorindianepic', 
        'rimorai@123', 
        [
            {'id': '1', 'name': 'Pop Art Style', 'model_id': '3c6079cb-18d7-4a23-bc4d-357299b29c54', 'model_type': '$style'},
            {'id': '2', 'name': 'Abhi Ch1', 'model_id': 'c27ba912-7fe1-4a23-bd3b-8514e99415eb', 'model_type': '$style'}
        ], 
        ['var', '3d', 'bgrem']
    ),
    User(
        'ishan@glip.gg', 
        'shared@123', 
        [
            {'id': '1', 'name': 'Pop Art Style', 'model_id': 'c64117c4-0010-471b-a7b9-caa5663b33a9', 'model_type': '$style'},
        ], 
        ['var']
    ),
    # Add more users as needed
]

# Initialize MongoDB client
mongo_client = MongoClient(
    f"mongodb+srv://{USERNAME}:{PASSWORD}@stable.myeot1r.mongodb.net/"
)
db = mongo_client["image_data"]
collection = db.images
users_collection = db.users

user_dicts = [user.to_dict() for user in users]

# Export user data to a JSON file
with open('users.json', 'w') as file:
    json.dump(user_dicts, file)
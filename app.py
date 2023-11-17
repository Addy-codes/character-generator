from flask import Flask, request, jsonify, render_template, redirect, url_for
import os
import uuid
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from google.cloud import storage
from tools import (
    RestAPI, 
    controlnet, 
    test)

from config import (
    BASE_PATH,
    SECRET_KEY, 
    MONGO_URL, 
    DB_NAME, 
    USERNAME, 
    PASSWORD,
    api
    )

class User:
    def __init__(self, username, password, model_id, model_type):
        self.username = username
        self.password = password  # Plain text password
        self.model_id = model_id
        self.model_type = model_type

    def check_password(self, entered_password):
        # Check if the provided password matches the stored password
        return self.password == entered_password

    def authenticate(self, entered_password):
        # Authenticate the user by checking the password
        return self.check_password(entered_password)

current_model_id = None
current_model_type = None

users = [
    User('user1', 'password1', 'c64117c4-0010-471b-a7b9-caa5663b33a9', "$style"),
    User('rimorindianepic', 'rimorai@123', '3c6079cb-18d7-4a23-bc4d-357299b29c54', '$style'),
    # Add more users as needed
]

app = Flask(__name__)
# Initialize MongoDB client
mongo_client = MongoClient(
    f"mongodb+srv://{USERNAME}:{PASSWORD}@stable.myeot1r.mongodb.net/"
)
db = mongo_client["image_data"]
collection = db["images"]
# Initialize Google Cloud Storage client
os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = f"{BASE_PATH}/key/clever-obelisk-402805-a6790dbab289.json"
storage_client = storage.Client()
bucket_name = "rimorai_bucket1"
bucket = storage_client.get_bucket(bucket_name)


# Temporary storage for uploaded images
TEMP_STORAGE_FOLDER = "out/"
if not os.path.exists(TEMP_STORAGE_FOLDER):
    os.makedirs(TEMP_STORAGE_FOLDER)

CHARACTERNAME = None
FILENAME = None
PATH_FILE = None
PROMPT = None


# Helper function to move files to Google Cloud Storage
def move_to_cloud_storage(filename, folder_name):
    global PROMPT
    image_id = str(uuid.uuid4())
    # Store information about the image in MongoDB
    image_data = {
        "image_id": image_id,
        "character_name": folder_name,
        "prompt": PROMPT,
        }
    collection.insert_one(image_data)
    folder_name = "".join(folder_name.split())
    blob = bucket.blob(f"{folder_name}/{image_id}_{filename}")
    blob.upload_from_filename(f"{PATH_FILE}")

    return blob.public_url


# Helper function to delete files from temporary storage
def delete_from_temp_storage(filename):
    file_path = os.path.join(TEMP_STORAGE_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)


# Stores information about saved images
saved_images = {}


@app.route("/")
def home():

    return render_template("index.html", model_id = current_model_id)

@app.route('/login', methods=['POST'])
def login():
    global current_model_id, current_model_type
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = next((user for user in users if user.username == username), None)

        if user and user.authenticate(password):
            current_model_id = user.model_id
            current_model_type = user.model_type
            return render_template('index.html', filename = "./static/images/image.png", model_id = current_model_id)

    return render_template('index.html', message="Invalid username or password!", model_id = current_model_id)

@app.route('/logout', methods=['POST'])
def logout():
    global current_model_id, current_model_type
    current_model_type = None
    current_model_id = None
    return render_template('index.html', message="You have been locked out!", model_id = current_model_id)

@app.route("/generate-image", methods=["POST"])
def generate_image():
    global CHARACTERNAME, FILENAME, PATH_FILE, PROMPT, current_model_id, current_model_type
    if current_model_id == None:
        return render_template('index.html', message="Kindly login to your account!", model_id = current_model_id)
    data = request.form
    character_name = data["characterName"]
    prompt = data["description"]
    outline_image = request.files.get("imageUpload")
    print(
        f"========================================================================\nGENERATED IMAGE\n{character_name} {prompt}\n ================================================================"
    )
    # Save the generated image to temporary storage
    PROMPT = prompt
    if outline_image:
        generator = controlnet.ControlNet(api, current_model_id, current_model_type)
        outline_filename = secure_filename(outline_image.filename)

        PATH_FILE = f"{TEMP_STORAGE_FOLDER}/outline_image_{outline_filename}"

        outline_image.save(PATH_FILE)
        generator.process_request(prompt, PATH_FILE)
        filename = f"img2img.png"

    else:
        # Un-comment the below line to use gRPC
        #generator = gRPCAPI.gRPCAPI(api)

        # Un-comment the below line to use RestAPIs
        generator = RestAPI.RestAPI(api, current_model_id, current_model_type)
        PATH_FILE= generator.generate_images(prompt)
        filename = "image.png"

    CHARACTERNAME = character_name
    FILENAME = filename

    # image_url = move_to_cloud_storage(filename, character_name)
    # # # Return the generated image's URL and image ID
    # return jsonify({"image_url": image_url, "image_id": image_id})

    return render_template(
        "index.html", characterName=CHARACTERNAME, filename=FILENAME, model_id = current_model_id, description = PROMPT
    )

# Not yet implemented
@app.route("/previous-images/<character_name>", methods=["GET"])
def previous_images(character_name):
    # Query the database to find images associated with the provided character name
    image_urls = [
        move_to_cloud_storage(image["image_id"], character_name)
        for image in collection.find({"character_name": character_name})
    ]
    return jsonify({"image_urls": image_urls})


@app.route("/process", methods=["POST"])
def process():
    global FILENAME,PROMPT, CHARACTERNAME, current_model_id, current_model_type

    action = request.form.get("action")

    if action == "logout":
        current_model_type = None
        current_model_id = None
        print("Logging out")
        return render_template('index.html', message="You have been locked out!", model_id = current_model_id)

    if FILENAME == None or CHARACTERNAME == None:
        return render_template('index.html', message="Kindly generate the image first!", model_id = current_model_id)

    if action == "keep":
        image_url = move_to_cloud_storage(FILENAME, CHARACTERNAME)

    file_to_delete = PATH_FILE
    if os.path.exists(file_to_delete):
        os.remove(file_to_delete)
    temp_prompt = PROMPT
    temp_character_name = CHARACTERNAME
    # Redirect back to the main page or any other desired page
    temp_filename = FILENAME
    FILENAME = None
    CHARACTERNAME = None
    return render_template("index.html",filename = temp_filename, model_id = current_model_id, characterName = temp_character_name, description = temp_prompt)


if __name__ == "__main__":
    app.run(debug=True)

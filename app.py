from email import message
import email
from exceptiongroup import catch
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
import os
from io import BytesIO
from PIL import Image
import tempfile
import uuid
import requests
import base64
import time
import gradio_client
import shutil
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from google.cloud import storage
from test_app import login_required
from tools import (
    RestAPI, 
    controlnet, 
    test)

from tools.dashboard import Dashboard
from config import (
    BASE_PATH,
    SECRET_KEY, 
    MONGO_URL, 
    DB_NAME, 
    USERNAME, 
    PASSWORD,
    api,
    MESHY_API_KEY,
    REIMAGINE_API_KEY,
    )


class User:
    def __init__(self, username, password, models, permissions=[], email=None, _id=None):
        self.username = username
        self.password = password  # Plain text password (not recommended)
        self.models = models  # List of models, each with model_id and model_type
        self.permissions = permissions
        self.email = email

    @classmethod
    def create_user(cls, username, password, email, models=None, permissions=None):
        if models is None:
            models = []
        if permissions is None:
            permissions = []

        new_user = {
            "username": username,
            "password": password,  # This should be a hashed password
            "email": email,
            "models": models,
            "permissions": permissions
        }
        users_collection.insert_one(new_user)

    @classmethod
    def authenticate(cls, login, entered_password):
        print(f"Authenticating with: {login} and password: {entered_password}")
        
        # Searching for user by username or email
        user_data = users_collection.find_one({'$or': [{'username': login}, {'email': login}]})

        if user_data:
            print(f"User found in DB: {user_data}")
            if user_data['password'] == entered_password:  # Assuming password is stored in plain text
                print("Password match")
                return cls(**user_data)
            else:
                print("Password mismatch")
        else:
            print("User not found in DB")

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

models = None
current_model_type = None

app = Flask(__name__)
app.SECRET_KEY = SECRET_KEY

app.config['SECRET_KEY'] =  SECRET_KEY

# Initialize MongoDB client
mongo_client = MongoClient(
    f"mongodb+srv://{USERNAME}:{PASSWORD}@cluster0.ugj6asi.mongodb.net/"
)
db = mongo_client["qrksee"]
collection = db.images
users_collection = db.user_data

# Initialize Google Cloud Storage client
os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = f"{BASE_PATH}/key/qrksee-a59ab87bd174.json"
storage_client = storage.Client()



# Temporary storage for uploaded images
TEMP_STORAGE_FOLDER = "out/"
if not os.path.exists(TEMP_STORAGE_FOLDER):
    os.makedirs(TEMP_STORAGE_FOLDER)

CHARACTERNAME = None
FILENAME = None
PATH_FILE = None
PROMPT = None



@app.route('/dashboard', methods=['GET'])
def dashboard():
    bucket_name = 'qrksee_images'
    username = session.get('username')
    dashboard = Dashboard(bucket_name, username)  #Initialize with required credentials
    folders = dashboard.fetch_user_folders()
    return render_template('dashboard.html', folders=folders)

@app.route('/dashboard/<folder_name>', methods=['GET'])
def folder_thumbnails(folder_name):
    bucket_name = 'qrksee_images'
    username = session.get('username')
    dashboard = Dashboard(bucket_name, username)  #Initialize with required credentials

    all_file_pairs = dashboard.fetch_files_with_thumbnails(folder_name) #Fetch all file pairs

    print( "========================\n",all_file_pairs) #Filter pairs to only include those in the specified folder
    thumbnails = {key: value for key, value in all_file_pairs.items() 
                  if "thumbnail" in key}
    
    return render_template('folder.html', thumbnails=thumbnails, folder_name=folder_name) #print(thumbnails)

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

def v1dashboard():
    bucket_name = 'qrksee_images'
    username = session.get('username')

    # Assuming Dashboard is properly initialized and fetch_user_folders is an instance method
    dashboard = Dashboard(bucket_name, username)  # You should initialize it with required credentials
    folders = dashboard.fetch_user_folders()
    
    return render_template('dashboard.html', folders=folders)

# Helper function to move files to Google Cloud Storage for character generator
def move_to_cloud_storage(filename, character_name, image_id):
    global PROMPT

    username = session.get('username')
    bucket_name = 'qrksee_images'

    bucket = storage_client.get_bucket(bucket_name)
    # Store information about the image in MongoDB
    image_data = {
        "image_id": image_id,
        "character_name": character_name,
        "prompt": PROMPT,
    }
    collection.insert_one(image_data)
    folder_name = "".join(character_name.split())
    
    # Modify the path to include the username
    username = "".join(username.split())
    blob = bucket.blob(f"{username}/{folder_name}/{image_id}_{filename}")
    
    blob.upload_from_filename(f"./static/images/{filename}")
    return f"{username}/{folder_name}/{image_id}_{filename}"

def generate_thumbnail(image_path):
    with Image.open(image_path) as img:
        img.thumbnail((100, 100))
        thumb_io = BytesIO()
        img.save(thumb_io, 'JPEG')
        thumb_io.seek(0)
        return thumb_io
    
def upload_image_and_thumbnail(image_path, character_name):
    # Extract filename and extension
    filename, ext = os.path.splitext(os.path.basename(image_path))

    # Generate a common UUID for both original and thumbnail
    image_id = str(uuid.uuid4())

    # Define the path for static images
    static_image_path = './static/images'

    # Ensure the static images directory exists
    if not os.path.exists(static_image_path):
        os.makedirs(static_image_path)

    # Define file paths
    original_file_path = os.path.join(static_image_path, f"{filename}{ext}")
    thumbnail_file_path = os.path.join(static_image_path, f"{filename}-thumbnail{ext}")

    # Save original image to static path
    os.rename(image_path, original_file_path)

    # Upload original image
    original_url = move_to_cloud_storage(f"{filename}{ext}", character_name, image_id)

    # Generate and save thumbnail
    thumbnail_io = generate_thumbnail(original_file_path)
    with open(thumbnail_file_path, 'wb') as f:
        f.write(thumbnail_io.read())

    # Upload thumbnail
    thumbnail_url = move_to_cloud_storage(f"{filename}-thumbnail{ext}", character_name, image_id)

    return original_url, thumbnail_url

# def v1move_to_cloud_storage(filename, folder_name):
#     global PROMPT
#     username = session.get('username')
#     bucket_name = "qrksee_images"
#     bucket = storage_client.get_bucket(bucket_name)
#     image_id = str(uuid.uuid4())
#     # Store information about the image in MongoDB
#     image_data = {
#         "image_id": image_id,
#         "character_name": f"{folder_name}",
#         "prompt": PROMPT,
#         }
#     collection.insert_one(image_data)
#     folder_name = "".join(folder_name.split())
#     blob = bucket.blob(f"{folder_name}/{image_id}_{filename}")
#     blob.upload_from_filename(f"{PATH_FILE}")

#     return blob.public_url

# Helper function to move files to Google Cloud Storage for 3d model generator
def upload_to_gcs(file, folder_name):
    bucket_name = "threed_model"
    bucket = storage_client.get_bucket(bucket_name)
    filename = secure_filename(file.filename)
    folder_name = "".join(folder_name.split())
    blob = bucket.blob(f"{folder_name}/{filename}")

    # Create a temporary file
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, filename)
    file.save(temp_path)

    # Upload the file
    blob.upload_from_filename(temp_path)

    # Optionally, make the blob publicly accessible
    blob.make_public()

    # Delete the temporary file
    os.remove(temp_path)

    return blob.public_url

def remove_background(file_path):
    file_path = f"./static/images/{file_path}"
    # Get the public URL of the image
    image_url = get_public_url(file_path)

    # Initialize the Gradio client
    client = gradio_client.Client("https://eccv2022-dis-background-removal.hf.space/--replicas/l8swv/")
    
    # Call the API to remove the background
    result = client.predict(image_url, api_name="/predict")

    # Assuming the result contains the path to the processed image
    processed_image_path = result[0]

    # Replace the original file with the new file
    shutil.move(processed_image_path, file_path)

    print(file_path)

    # Optional: Clean up any temporary directories created by Gradio
    temp_dir = os.path.dirname(processed_image_path)
    if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)

def get_public_url(file_path):
    """
    Uploads a file to 0x0.st and returns the URL.

    :param file_path: Path to the file to upload
    :return: URL of the uploaded file
    """
    with open(file_path, 'rb') as f:
        response = requests.post('https://0x0.st', files={'file': f})
    
    if response.status_code == 200:
        return response.text.strip()
    else:
        raise Exception(f"Error uploading file: {response.status_code}")

# Helper function to delete files from temporary storage
def delete_from_temp_storage(filename):
    file_path = os.path.join(TEMP_STORAGE_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)


# Stores information about saved images
saved_images = {}


@app.route("/")
def home():

    return render_template("index.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')  # This should be hashed before storing

        # Check if the user already exists
        existing_user = users_collection.find_one({'$or': [{'username': username}, {'email': email}]})
        if existing_user is None:
            User.create_user(username, password, email)
            flash('Signup successful!', 'success')
            return render_template('index.html', message="Account Created")
        else:
            flash('Username or email already exists.', 'error')
            return render_template('signup.html', message="Username or email already exists.")

    return render_template('signup.html')

def v1signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        # You can add additional fields here
        permissions = None
        models = None

        # Check if the user already exists
        existing_user = users_collection.find_one({'username': username})
        if existing_user is None:
            

            # Assuming you have a method in your User class to create a user
            User.create_user(username, password, email, models, permissions)
            flash('Signup successful!', 'success')

            
            return render_template('index.html', message="Account Created")
        else:
            flash('Username already exists.', 'error')
            
            return render_template('signup.html', message="Username already exists.")

    return render_template('signup.html')

@app.route('/login', methods=['POST'])
def login():
    global models, current_model_type
    
    if request.method == 'POST':
        login = request.form['login']  # 'login' can be either username or email
        password = request.form['password']
        user = User.authenticate(login, password)

        if user:
            # Store user model information in session
            session['models'] = user.models
            session['permissions'] = user.permissions
            session['username'] = user.username
            models = user.models
            print(user.models)

            return render_template('generator.html', filename="./static/images/image.png", models=session['models'], user_permissions= session['permissions'])

        # In case of failure, reset the session variables
        session.pop('models', None)
        session.pop('current_model_type', None)
        print("User Not found")

    return render_template('index.html', message="Invalid username or password!")
@app.route('/logout', methods=['POST'])
def logout():
    global models
    session.clear()
    return render_template('index.html', message="You have been locked out!", models=session['models'], user_permissions= session['permissions'])

@app.route("/generate", methods=["GET", "POST"])
def generate():
    global CHARACTERNAME, FILENAME, PATH_FILE, PROMPT
    models = session.get('models')
    # Handling a GET request
    if request.method == 'GET':
        if models is None:
            return render_template('index.html', message="Kindly login to your account!", models=session['models'], user_permissions= session['permissions'])
        return render_template('generator.html', characterName=None, filename=None, models=session['models'], description = None, user_permissions= session['permissions'])

    if models == None:
        return render_template('index.html', message="Kindly login to your account!", models=session['models'], user_permissions= session['permissions'])
    data = request.form
    character_name = data["characterName"]
    prompt = data["description"]
    outline_image = request.files.get("imageUpload")
    model_id = data.get("model_id")
    model_type = None
    for model in models:
        if model['model_id'] == model_id:
            model_type = model['model_type']
            break
    # Save the generated image to temporary storage
    PROMPT = prompt

    if outline_image:
        
        generator = controlnet.ControlNet(api, model_id, model_type)
        outline_filename = secure_filename(outline_image.filename)

        PATH_FILE = f"{TEMP_STORAGE_FOLDER}/outline_image_{outline_filename}"

        outline_image.save(PATH_FILE)
        generator.process_request(prompt, PATH_FILE)
        filename = f"img2img.png"

    else:
        # Un-comment the below line to use gRPC
        #generator = gRPCAPI.gRPCAPI(api)

        # Un-comment the below line to use RestAPIs
        generator = RestAPI.RestAPI(api, model_id, model_type)
        PATH_FILE= generator.generate_images(prompt)
        filename = "image.png"

    CHARACTERNAME = character_name
    FILENAME = filename

    image_url = upload_image_and_thumbnail(f'./static/images/{filename}', character_name)
    # print(f"====================\n filename: {filename} charatername: {character_name}\n======================")
    # image_url = move_to_cloud_storage(filename, character_name)
    print("Image URL: ",image_url)
    # # # Return the generated image's URL and image ID
    # return jsonify({"image_url": image_url, "image_id": image_id})

    return render_template(
        "generator.html", characterName=CHARACTERNAME, filename=FILENAME, models=session['models'], user_permissions= session['permissions'], description = PROMPT
    )

# Not yet implemented
# @app.route("/previous-images/<character_name>", methods=["GET"])
# def previous_images(character_name):
#     # Query the database to find images associated with the provided character name
#     image_urls = [
#         move_to_cloud_storage(image["image_id"], character_name)
#         for image in collection.find({"character_name": character_name})
#     ]
#     return jsonify({"image_urls": image_urls})



# @app.route('/flappy_bird')
# def flappy_bird():
#     print("hello ")
#     return render_template('indexflap.html')

@app.route("/process", methods=["POST"])
def process():
    global FILENAME,PROMPT, CHARACTERNAME, models, current_model_type

    action = request.form.get("action")

    if action == "logout":
        current_model_type = None
        models = None
        session.clear()
        print("Logging out")
        return render_template('index.html', message="You have been locked out!")

    if FILENAME == None or CHARACTERNAME == None:
        return render_template('generator.html', message="Kindly generate the image first!")

    if action == "keep":
        image_url = move_to_cloud_storage(FILENAME, CHARACTERNAME)
    
    if action == "removebg":
        remove_background(FILENAME)
        return render_template(
        "generator.html", characterName=CHARACTERNAME, filename=FILENAME, models = session['models'], description = PROMPT
    )

    file_to_delete = PATH_FILE
    if os.path.exists(file_to_delete):
        os.remove(file_to_delete)
    temp_prompt = PROMPT
    temp_character_name = CHARACTERNAME
    # Redirect back to the main page or any other desired page
    temp_filename = FILENAME
    FILENAME = None
    CHARACTERNAME = None
    return render_template("generator.html",filename = temp_filename, models = session['models'], characterName = temp_character_name, description = temp_prompt)

@app.route('/modelgen')
def modelgen():
    global models
    if models is None:
        return render_template('index.html', message="Kindly login to your account!", models=session['models'], user_permissions= session['permissions'])
    return render_template('modelgen.html')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)

    if file and allowed_file(file.filename):  # Implement 'allowed_file' to check file extensions
        image_url = upload_to_gcs(file, "Uploaded_images")
        print(image_url)

        payload = {
            "image_url": image_url,
            "enable_pbr": True
        }
        headers = {
            "Authorization": f"Bearer {MESHY_API_KEY}"
        }

        print("Sending Image to API")

        # First, create the 3D task
        response = requests.post(
            "https://api.meshy.ai/v1/image-to-3d",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        task_id = response.json().get('result')

        print("Task ID: ",task_id)

        # Now, periodically check the status of the task
        while True:
            task_response = requests.get(
                f"https://api.meshy.ai/v1/image-to-3d/{task_id}",
                headers=headers
            )
            task_response.raise_for_status()
            task_data = task_response.json()

            # task_data = {'id': '018c011c-def2-7e02-80e8-6d9b3b3b71bf', 'name': '', 'art_style': '', 'object_prompt': '', 'style_prompt': '', 'negative_prompt': '', 'status': 'SUCCEEDED', 'created_at': 1700825718523, 'progress': 100, 'started_at': 1700825746216, 'finished_at': 1700825835934, 'expires_at': 1701085035934, 'task_error': None, 'model_url': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/model.glb?Expires=1701085035&Signature=lSDznXTVL9p3HeoKx5OGHhXBqyAaS~~q39uia7O829Y3WN5vzEthxO3xf7Kr9-1evfDM2DZtxDBIppnAYiLkWl5fg4uxE-t0kY97ln8M3nFGnA01vZkqn6S8peubUpK6EdgwYCtH4EnrJJC3Xs3I~MK9sS8NrpeF2FW7LpCmEIQcS5opfNCcSfCAm0uWWs2L56Z2fklmtBjHkQp~AFZNaYda0B8MEZerLn-Giy1~u0Kils6p4vXxu9wpU1SQkVMu3In-B-ZrZDL-BNDic7RC2WOfiolT7SAOTOF8p8s0Y5KLk0ibU~ZFy~uNUMRahn2YyLU5GwbMGmjRb9NaJlskNw__&Key-Pair-Id=KL5I0C8H7HX83', 'model_urls': {'glb': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/model.glb?Expires=1701085035&Signature=lSDznXTVL9p3HeoKx5OGHhXBqyAaS~~q39uia7O829Y3WN5vzEthxO3xf7Kr9-1evfDM2DZtxDBIppnAYiLkWl5fg4uxE-t0kY97ln8M3nFGnA01vZkqn6S8peubUpK6EdgwYCtH4EnrJJC3Xs3I~MK9sS8NrpeF2FW7LpCmEIQcS5opfNCcSfCAm0uWWs2L56Z2fklmtBjHkQp~AFZNaYda0B8MEZerLn-Giy1~u0Kils6p4vXxu9wpU1SQkVMu3In-B-ZrZDL-BNDic7RC2WOfiolT7SAOTOF8p8s0Y5KLk0ibU~ZFy~uNUMRahn2YyLU5GwbMGmjRb9NaJlskNw__&Key-Pair-Id=KL5I0C8H7HX83', 'fbx': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/model.fbx?Expires=1701085035&Signature=rBU6B4vtwiEbsXI6Y4SbKvmy013poW6nTLJaa0lbuJRv832zJHnXznem5i3whJC39g3gKSw4qJ19d3ojM7xBM25COH0EHbPZluNt9Bm1bPisX8K4KsWRe2VQPhoeX-fe0xkfkMUsTfhg-qiAoGrPk8z4ZWicbbIX-awE2Vq~MUsYyFwGUtgvAQDaPTW~-lo-bmocBf3o5eFb7uz3PitoEqlFJJP1WL1zF-0nCoJei-bxR9SIRaF9tFU9gAcTOfF6FQvqVSREPdy6SzsK~p5zXnyj3SxFrQevMhSCXWaNXw85i5snPHithFy13~3bVIC2TN~AjZIrhMNo1ujv3zG~YA__&Key-Pair-Id=KL5I0C8H7HX83', 'usdz': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/model.usdz?Expires=1701085035&Signature=k9nfxQoKRDP82Yrp2~acaXF~IZASnskwWLw5nU9xVM1dQpSzAE~vDRNXTz38tpDWPmGLe5ikG0UhEkW0L3ENu5eSrNrD~wI-UZxAa-vfqWLdC0iafwzAmb53738IucjKi-5hYNM2C3Q79pzGDJRHp-Lxl-BQhLlvQSwvapkAC6uvrmVx4wTNXEoiDAg0Rw0MTCtDab3Zhi6BLhlUt-8qacOZuC9KmqzijSiyyx2AA9qQ8tOhfidugWOgI-tyVFmk~~xTryHL-FhPkDyoksRKLV4xzehjzwQ0P1jMyhh5ape3ddKxwblmF9lDniiU1t9lA5h-3klP4uxUymVcpwOreA__&Key-Pair-Id=KL5I0C8H7HX83'}, 'thumbnail_url': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/preview.png?Expires=1701085035&Signature=eDMwIXHyOImXziv2HsN5~h1izxQXLl1LcJ2gmGVTyu7omxpDOs-Cmfy~cQAC~gJtUFQ4BLU7pwugRzXD0QO0~toAOT8dyJJtbZ-hGQSlCukPnsWfyEz5l4mQLTqw~-d0lpT8CKWqaXPXawKOK6vz-2nsWQdlR6gZJfTFQ88iYz4i8DjPeAo8v3vbMxbwz0ImBc3WeXsk9R22GbwLFuv1BL0u9XOQdC9vM6LIXyotXLhZE0LXtvdlSnxcdlkYzRSfgQlSzY7wP0IhPLgRFPXAS4r44Oa~4oDqWecl25sWz07-DvvbzUmcWrJ2NtvCM~u12GnQSI0KDUgsD2Zx765TSA__&Key-Pair-Id=KL5I0C8H7HX83', 'texture_urls': [{'base_color': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/texture_0.png?Expires=1701085035&Signature=hlIEMIcpiNdO8gvqWd-uPWy42cEz16lkwJrFb3YKsP6ebmwDBwCw2yislFWmdqzBMhV1vV1cPJq~c1GFCuFRB21f0uJ9HnwSw3He0gW5sKkq2vyRTJZJy76wUM-GJrVhuhmC44pmqk5FnD-dxn3z06aTwwNIMLBRf1EZNiZL7hKOSPYiljXsYNvh5MYePW5-S3n0zPPPnVOjRG4YJldrj5sK3iLBbW-A8-3x9I9MfACtxGvO7igbWv7GGRk40QrVKdG7p9nDD6PiC2ky3bKriGn5H0DDh8lyQfYtoNXKvb2bCloyGJtsqNvONWITsJwxROy7LXvuT8DV5dT-42cIoQ__&Key-Pair-Id=KL5I0C8H7HX83', 'metallic': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/texture_0_metallic.png?Expires=1701085035&Signature=UfbQzRGTnhyON5ImhMrk6ucKTYIUJGdxagBzL~~twDhkupa56-PezYc7NrpOFAk-9Q-1VI9TvE2n2ylV2bXcIZYp6aSnXHtUDl-9v6gHZ~9yIhFBwygeLh2k0BiDrcx3Pe8Y5V1GJxX8wcmD8zp-bGVg34IFFVdyiW9FbPF5YHbUQs0m~3rHZIRP9GBnAx2Hug4VrtWeZLoH7RxH~ZmHf9Qqw5gX4KJAH5itocxzQImQBmgcXu9-FrtzUFUSNL4JKhKacHvOOKCW1kAeFbzzLVS7FZJkiqvg~LO~JDoWHIDW2wXqVgAXqhaDFb5DVoeFABlUHHu2EFssZblQrDCcmQ__&Key-Pair-Id=KL5I0C8H7HX83', 'roughness': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/texture_0_roughness.png?Expires=1701085035&Signature=jAe5RHpg9ZZoXS~V~Xz~O03Q68X9XalyzRcn-x11YpAsTYYOfaRLOix1Et4~HTv2i30vtbGIVrjY-eYEChKBIy-fTQsk6CRVON3l0n3loRia7TLa39zddLVipIRrpbNpK2Vv-nW6qFVkaNop03QS0SjHo1KQWYCMRQlwhdyxPtmPc6mrd6apiShB5ZDGLeyne3Ki1an4boh1kFPnimVaxh3X5RmOs3pUEYCqa98SN5uyBVeUVBDrBrOnL688TJIlldxBgimDc-RNzLcGUIGJunPFCKSjp8qyBcB8O6b5baOmrCJHwsZQi-Xnuc2XDqYiopY5q7TXL144rEDxvJy~4Q__&Key-Pair-Id=KL5I0C8H7HX83', 'normal': 'https://assets.meshy.ai/google-oauth2%7C114462251513498782179/tasks/018c011c-def2-7e02-80e8-6d9b3b3b71bf/output/texture_0_normal.png?Expires=1701085035&Signature=mjXJICDPnnm77mKzWmilEgIazDULTuuaNtVkxE5YL9ocO4ISiMES9r-JE70~bBeeHPyu6O0mXNxiU2k-7shfkWNCnWv3vDRa3Fr45wByaZQzNLEbJGBrFGZhO~TdJgiahtZA5Di7VHb1qMJcoby~ZXPpxlL~daTr~pljNym4nks~h~BoPIak5sQ8GP8MvCXBkP6iV0UpXGHqkjWEKmQLgikMtM5hc1CeJ8WvryExRksLbd3lF991iejyUQXQu1hqVhd94Bj6RCTxAgU44wfJjTKSq3G2Xgq5wQHUhW3I0XsAnNI9cdzKXjXCmZW3adEmS84NNIwlwf0R0lfvNDb0cQ__&Key-Pair-Id=KL5I0C8H7HX83'}]}


            print("Attempting")

            if task_data['status'] == 'SUCCEEDED':
                model_url = task_data['model_urls']['glb']  # Example, using the GLB format
                print(task_data)
                return render_template('download.html', model_url=model_url)
            elif task_data['status'] == 'FAILED':
                return "3D model generation failed", 500

            time.sleep(5)  # Adjust the sleep time as needed

    return "Invalid request", 400

@app.route('/variations', methods=['GET', 'POST'])
def index():
    original_image_base64 = None
    reimagined_variations = []

    try:
        if request.method == 'POST':
            print(request.data)
            file = request.files.get('file')
            if file and file.filename != '':
                image_path = save_image(file)
                original_image_base64 = convert_to_base64(image_path)
                print("new image used")
            else:
                image_path = 'out/local/uploaded_image.png'
                print("old image used")
                if not os.path.exists(image_path):
                    print("No file chosen and saved image does not exist.")
                    return render_template('reimagine.html', 
                           original_image=original_image_base64, 
                           reimagined_variations=reimagined_variations)

                original_image_base64 = convert_to_base64(image_path)

            with open(image_path, 'rb') as file_stream:
                file_stream.seek(0)
                reimagined_variations = reimagine_image(file_stream)
            return jsonify({
                    'original_image': original_image_base64,
                    'reimagined_variations': reimagined_variations
                })


    except Exception as e:
        print("An error occurred: {}".format(str(e)))

    return render_template('reimagine.html', 
                           original_image=original_image_base64, 
                           reimagined_variations=reimagined_variations)



def save_image(file):
    """Save the uploaded file with a fixed name, creating the directory if it doesn't exist."""
    storage_dir = 'out/local/'
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)

    filename = 'uploaded_image.png'
    file_path = os.path.join(storage_dir, filename)
    file.save(file_path)
    return file_path

def convert_to_base64(image_path):
    """Convert the image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def v1index(): # NOT IN USE. old v1 index used for generating variations. 
    original_image_base64 = request.form.get('originalImage')
    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename):
            try:
                data = BytesIO()
                file.save(data)
                original_image_base64 = base64.b64encode(file.read()).decode('utf-8')
                file.stream.seek(0)  # Reset the stream position after reading
                reimagined_variations = reimagine_image(file.stream)
                return render_template('reimagine.html', style='display:none;',original_image=original_image_base64, reimagined_variations=reimagined_variations)
            except Exception as e:
                flash(str(e), 'error')
        else:
            flash('No valid file provided', 'error')

    return render_template('reimagine.html', original_image = original_image_base64)

@app.route('/removebg', methods=['GET', 'POST'])
def removebg():
    original_image = None
    final_image = None

    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename):
            # Save the original image
            filename = secure_filename(file.filename)
            file_path = os.path.join("./static/images/out/", filename)
            file.save(file_path)
            
            # Get the base64 encoded string of the original image
            original_image = get_image_base64(file_path)

            # Process the image to remove the background
            processed_file_path = remove_background(os.path.join("out/", filename))
            final_image = get_image_base64(file_path)

    return render_template('remove_background.html', original_image=original_image, final_image=final_image)

def get_image_base64(file_path):
    # Convert image to base64 for embedding in HTML
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def reimagine_image(image_stream):
    REIMAGINE_API_URL = 'https://clipdrop-api.co/reimagine/v1/reimagine'

    # Create a file-like object from the stream
    image_file = ('uploaded_image.jpg', image_stream, 'image/jpeg')

    files = {'image_file': image_file}
    headers = {'x-api-key': REIMAGINE_API_KEY}

    variations = []
    
    response = requests.post(REIMAGINE_API_URL, files=files, headers=headers)

    if response.ok:
        variations.append(base64.b64encode(response.content).decode('utf-8'))
    else:
        try:
            error_message = response.json()['error']
        except (ValueError, KeyError):
            error_message = response.text

        raise Exception(f"Reimagine API error: {response.status_code} - {error_message}")

    return variations

if __name__ == "__main__":
    app.run( debug = True)
    
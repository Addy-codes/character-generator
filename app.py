from flask import Flask, request, jsonify, render_template, redirect, url_for, flash,session
import os
import tempfile
import uuid
import requests
import base64
import time
import gradio_client
import shutil
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
    api,
    Clipdrop_api,
    MESHY_API_KEY,
    REIMAGINE_API_KEY,
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
    User('user1', 'password1', 'c64117c4-0010-471b-a7b9-caa5663b33a9', '$style'),
    User('rimorindianepic', 'rimorai@123', '3c6079cb-18d7-4a23-bc4d-357299b29c54', '$style'),
    User('abhich1', 'htshared1', 'c27ba912-7fe1-4a23-bd3b-8514e99415eb', '$style')
    # Add more users as needed
]

app = Flask(__name__)
app.SECRET_KEY = SECRET_KEY

app.config['SECRET_KEY'] =  SECRET_KEY

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


# Temporary storage for uploaded images
TEMP_STORAGE_FOLDER = "out/"
if not os.path.exists(TEMP_STORAGE_FOLDER):
    os.makedirs(TEMP_STORAGE_FOLDER)

CHARACTERNAME = None
FILENAME = None
PATH_FILE = None
PROMPT = None


# Helper function to move files to Google Cloud Storage for character generator
def move_to_cloud_storage(filename, folder_name):
    global PROMPT
    bucket_name = "rimorai_bucket1"
    bucket = storage_client.get_bucket(bucket_name)
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

# Helper function to move files to Google Cloud Storage for 3d model generator
def upload_to_gcs(file, folder_name):
    bucket_name = "threed-model"
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

@app.route('/login', methods=['POST'])
def login():
    global current_model_id, current_model_type
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = next((user for user in users if user.username == username), None)

        if user and user.authenticate(password):
            # Store user model information in session
            session['current_model_id'] = user.model_id
            session['current_model_type'] = user.model_type
            current_model_id = user.model_id
            current_model_type = user.model_type

            return render_template('generator.html', filename="./static/images/image.png", model_id=session['current_model_id'])

        # In case of failure, reset the session variables
        session.pop('current_model_id', None)
        session.pop('current_model_type', None)

    return render_template('index.html', message="Invalid username or password!")

@app.route('/logout', methods=['POST'])
def logout():
    global current_model_id, current_model_type
    current_model_type = None
    current_model_id = None
    return render_template('index.html', message="You have been locked out!", model_id = current_model_id)

@app.route("/generate", methods=["GET", "POST"])
def generate():
    global CHARACTERNAME, FILENAME, PATH_FILE, PROMPT, current_model_id, current_model_type
    # Handling a GET request
    if request.method == 'GET':
        if current_model_id is None:
            return render_template('index.html', message="Kindly login to your account!", model_id=current_model_id)
        return render_template('generator.html', characterName=CHARACTERNAME, filename=FILENAME, model_id=current_model_id, description=PROMPT)

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
        "generator.html", characterName=CHARACTERNAME, filename=FILENAME, model_id = current_model_id, description = PROMPT
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
    global FILENAME,PROMPT, CHARACTERNAME, current_model_id, current_model_type

    action = request.form.get("action")

    if action == "logout":
        current_model_type = None
        current_model_id = None
        print("Logging out")
        return render_template('index.html', message="You have been locked out!", model_id = current_model_id)

    if FILENAME == None or CHARACTERNAME == None:
        return render_template('generator.html', message="Kindly generate the image first!", model_id = current_model_id)

    if action == "keep":
        image_url = move_to_cloud_storage(FILENAME, CHARACTERNAME)
    
    if action == "removebg":
        remove_background(FILENAME)
        return render_template(
        "generator.html", characterName=CHARACTERNAME, filename=FILENAME, model_id = current_model_id, description = PROMPT
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
    return render_template("generator.html",filename = temp_filename, model_id = current_model_id, characterName = temp_character_name, description = temp_prompt)

@app.route('/modelgen')
def modelgen():
    global current_model_id
    if current_model_id is None:
        return render_template('index.html', message="Kindly login to your account!", model_id=current_model_id)
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

@app.route('/reimagine', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename):
            try:
                original_image_base64 = base64.b64encode(file.read()).decode('utf-8')
                file.stream.seek(0)  # Reset the stream position after reading
                reimagined_variations = reimagine_image(file.stream)
                return render_template('download_reimagine.html', original_image=original_image_base64, reimagined_variations=reimagined_variations)
            except Exception as e:
                flash(str(e), 'error')
        else:
            flash('No valid file provided', 'error')

    return render_template('reimagine.html')

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
    app.run(debug=True)

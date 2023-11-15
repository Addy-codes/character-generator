from google.cloud import storage
import os

from config import BASE_PATH, SECRET_KEY, MONGO_URL, DB_NAME, USERNAME, PASSWORD

os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = f"{BASE_PATH}/key/clever-obelisk-402805-a6790dbab289.json"
storage_client = storage.Client()
bucket_name = "rimorai_bucket1"
bucket = storage_client.get_bucket(bucket_name)

# Define a test folder name within your bucket
test_folder_name = "test"

# Get a reference to your bucket
bucket = storage_client.bucket(bucket_name)

# Use forward slashes in the image path to avoid escaping issues
image_path = "C:/Users/adeeb/Desktop/Projects/RimorAI/Stable-defusion-image-generator/testimage.png"

blob = bucket.blob("test/testimage.png")
blob.upload_from_filename(image_path)

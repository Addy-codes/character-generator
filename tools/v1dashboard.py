from google.cloud import storage
import sys
import os
BASE_PATH = os.getcwd()
sys.path.append(BASE_PATH)


os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = f"{BASE_PATH}/key/qrksee-a59ab87bd174.json"

class Dashboard:
    def __init__(self, bucket_name, username):
        # Initialize the Google Cloud Storage client and set the bucket name
        self.storage_client = storage.Client()
        self.bucket_name = bucket_name
        self.username = username


    def fetch_user_folders(self):
        # Fetch the username
        username = self.username
        if not username:
            return "User not logged in or session expired."

        # Access the bucket
        bucket = self.storage_client.get_bucket(self.bucket_name)

        # Ensure username is also free of spaces, if required
        username = "".join(username.split())

        # Prepare the prefix to fetch items from the folder named after the username
        prefix = f"{username}/"

        # List all 'folders' in the directory named after the username
        iterator = bucket.list_blobs(prefix=prefix, delimiter='/')
        folders = []

        # The iterator includes a 'prefixes' attribute for sub-directory names (folders)
        for page in iterator.pages:
            # Strip the username and the trailing slash from each prefix
            folders.extend([folder[len(prefix):].rstrip('/') for folder in page.prefixes])

        print(f"Folders: {folders}")

        return folders

    def fetch_files_in_folder(self, folder_name):
        # Access the bucket
        bucket = self.storage_client.get_bucket(self.bucket_name)

        # Prepare the full prefix to fetch items from the specific folder under the username
        full_prefix = f"{self.username}/{folder_name}/"

        # List all files in the specified folder
        blobs = bucket.list_blobs(prefix=full_prefix)
        files = [blob.name[len(full_prefix):] for blob in blobs if not blob.name.endswith('/')]

        return files

# Example of how to use this class
# dashboard = Dashboard("qrksee_images", 'user1')
# files = dashboard.fetch_user_folders()
# print(files)

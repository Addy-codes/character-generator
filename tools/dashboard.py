from google.cloud import storage
import sys
import re
import os
BASE_PATH = os.getcwd()
sys.path.append(BASE_PATH)


os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = f"{BASE_PATH}/key/qrksee-a59ab87bd174.json"

class Dashboard:
    def __init__(self, bucket_name, username):
        self.bucket_name = bucket_name
        self.username = username
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.get_bucket(bucket_name)

    def fetch_user_folders(self):
        username = "".join(self.username.split())
        prefix = f"{username}/"
        # print("Prefix:", prefix)

        # Initialize an empty set for folder names
        folder_names = set()

        # Create an iterator to list the blobs
        iterator = self.bucket.list_blobs(prefix=prefix, delimiter='/')
        # print("Iterator:", iterator)

        # Fetch all blobs and prefixes
        response = iterator._get_next_page_response()
        # print("Response:", response)

        # Extracting folder names from the 'prefixes' key in the response dictionary
        if 'prefixes' in response:
            for p in response['prefixes']:
                # print("Found Prefix:", p)
                folder_name = p.split('/')[-2]  # Getting the folder name
                folder_names.add(folder_name)

        # Extracting from blobs if necessary
        for blob in iterator:
            # print("Found Blob:", blob.name)
            path_parts = blob.name.split('/')
            if len(path_parts) > 1:
                folder_names.add(path_parts[1])

        if not folder_names:
            print("No folders found under the specified path.")

        return list(folder_names)

    def get_public_url(self, blob_name):
        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"

    def fetch_files_with_thumbnails(self):

        # Iterate through each folder
        for folder_name in self.fetch_user_folders():
            prefix = f"{self.username}/{folder_name}/"
            file_pairs = {}

            # Fetch all files within the folder
            blobs = self.storage_client.list_blobs(self.bucket, prefix=prefix)
            for blob in blobs:
                # Check if the file is a thumbnail
                if 'thumbnail' in blob.name:
                    # Extract the base filename
                    base_filename = re.sub(r"-thumbnail\..*$", "", blob.name)
                    thumbnail_filename = blob.name
                    # Generate public URLs
                    thumbnail_url = self.get_public_url(thumbnail_filename)
                    original_file_url = self.get_public_url(f"{base_filename}.png")
                    file_pairs[thumbnail_url] = original_file_url

        return file_pairs


# Example usage
# dashboard = Dashboard("qrksee_images", "user1")

# file_pairs = dashboard.fetch_files_with_thumbnails()
# print(file_pairs)

# folders = dashboard.fetch_user_folders()
# print(folders)
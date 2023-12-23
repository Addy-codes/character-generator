import gradio_client
import shutil
import os
import requests

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


def remove_background(file_path):
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

    # Optional: Clean up any temporary directories created by Gradio
    temp_dir = os.path.dirname(processed_image_path)
    if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)

# Example usage
remove_background("source_image.png")

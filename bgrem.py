import shutil
import os
import gradio_client

# Path to your local image file
local_image_path = "source_image.png"

# The desired new location for your file
new_location1 = "image1.png"

client = gradio_client.Client("https://eccv2022-dis-background-removal.hf.space/--replicas/l8swv/")

# Prepare the image data for sending
with open(local_image_path, "rb") as image_file:
    image_data = {
        "image": image_file.read(),
        "filename": os.path.basename(local_image_path)
    }

# Call the predict method with the image data
result = client.predict(image_data, api_name="/predict")

# Assuming result contains a file path
temp_file_path1 = result[0]

# Copy the file from the temporary location to your desired location
shutil.copy(temp_file_path1, new_location1)

# Delete the temporary file
os.remove(temp_file_path1)

# Remove the directory containing the temporary file
temp_dir = os.path.dirname(temp_file_path1)
if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
    shutil.rmtree(temp_dir)

print(f"File copied to: {new_location1}")

import requests
import json
from io import BytesIO
from PIL import Image
import os
import time
import base64

class ControlNet:
    def __init__(self, api, model_id, model_type):
        self.api = api
        self.MODEL_ID = model_id
        self.MODEL_TYPE = model_type

    def make_api_request(self, prompt, image_path):
        api_host = "https://preview-api.stability.ai"
        model_id = self.MODEL_ID
        token = self.MODEL_TYPE
        weight = 1

        payload = {
            "fine_tunes[]": json.dumps({"id": model_id, "token" : token, "weight": weight}),
            "text_prompts[0][text]": prompt + f", in the style of {token} as given in <{model_id}>",
            "samples": 1,  # num images
            "sampler": "K_DPM_2_ANCESTRAL",
            "steps": 50,
            "style_preset": "3d-model",
            "seed": 0,  # random
            "cfg_scale": 10,
            "image_strength" : 0.05, # if the image strength is more, we are not able to make enough changes to bring out our fine tuned style
        }

        headers = {
            'Content-Type': 'application/json'
        }

        reference_image = open(image_path, "rb")

        print ("------------------------------------------")

        try:
            response = requests.post(
                f"{api_host}/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image",
                data=payload,
                files={
                    "init_image": reference_image,
                },
                headers={
                    "Authorization": self.api
                },
            )
            reference_image.close()
            response.raise_for_status()  # Raise HTTPError for bad response (4xx and 5xx)
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error making API request: {e}")
            return None

    @staticmethod
    def save_image(image_bytes, seed):
        if not os.path.exists("./static/images"):
            os.makedirs("./static/images")

        try:
            with open(f'./static/images/img2img_{seed}.png', "wb") as f:
                f.write(image_bytes.getvalue())
            return f'./static/images/img2img_{seed}.png', seed
        except Exception as e:
            print(f"Error saving image: {e}")
            return None, None

    def extract_image_from_response(self, response):
        try:
            if response and response["status"] == "success" and "output" in response and len(response["output"]) > 0:
                image_url = response["output"][0]
                image_response = requests.get(image_url)
                image_response.raise_for_status()  # Raise HTTPError for bad response (4xx and 5xx)
                if image_response.status_code == 200:
                    image_bytes = BytesIO(image_response.content)
                    image = Image.open(image_bytes)

                    seed = response["meta"]["seed"]
                    saved_image_path, seed = self.save_image(image_bytes, seed)

                    return saved_image_path, seed
                else:
                    print(f"Failed to retrieve image. Status code: {image_response.status_code}")
            else:
                print("Invalid API response or no image found.", response)
        except Exception as e:
            print(f"Error extracting image from response: {e}")

    def process_request(self, prompt, image_path):
        response = self.make_api_request(prompt, image_path)
        time.sleep(4)
        if response is not None and response.status_code == 200:
            #api_response = response.json()
            #saved_image_path, seed = self.extract_image_from_response(api_response)

            data = response.json()
            saved_image_path = f'./static/images/img2img.png'
            for i, image in enumerate(data["artifacts"]):
                with open(saved_image_path, "wb") as f:
                    f.write(base64.b64decode(image["base64"]))
        elif response is not None:
            print(f"Failed to make API request. Status code: {response.status_code}")
        else:
            print("No response received.")

# Example usage
# api_key = "dPUaQdPuy24XCdSnWS9Bkqhz1V6GKo8HygYcTMnj8vLF3hKPr5bdOU6O3LD2"
# prompt_text = "indian cricket player navjyot singh siddhu"
# image_url = "https://storage.googleapis.com/rimorai_bucket1/%23OutlineImages/c83fbd25-b885-4f01-bc55-561ccb0b4e7c_Capture.JPG"

# extractor = ControlNet(api_key)
# extractor.process_request(prompt_text, image_url)
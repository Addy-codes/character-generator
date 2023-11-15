import requests
import json
from io import BytesIO
from PIL import Image
import os
import time

class ControlNet:
    def __init__(self, api):
        self.api = api

    def make_api_request(self, prompt, image_path):
        url = "https://stablediffusionapi.com/api/v5/controlnet"
        payload = {
            "key": self.api,
            "controlnet_model": "canny",
            "controlnet_type": "canny",
            "model_id": "midjourney",
            "auto_hint": "yes",
            "guess_mode": "no",
            "prompt": prompt,
            "negative_prompt": None,
            "init_image": image_path,
            "mask_image": None,
            "width": "512",
            "height": "512",
            "samples": "1",
            "scheduler": "UniPCMultistepScheduler",
            "num_inference_steps": "30",
            "safety_checker": "no",
            "enhance_prompt": "yes",
            "guidance_scale": 7.5,
            "strength": 0.55,
            "lora_model": None,
            "tomesd": "yes",
            "use_karras_sigmas": "yes",
            "vae": None,
            "lora_strength": None,
            "embeddings_model": None,
            "seed": None,
            "webhook": None,
            "track_id": None
        }

        headers = {
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
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
        
    def fetch_processed_image(self, fetch_url, retry_interval=5, max_retries=3):
        retries = 0
        while retries < max_retries:
            try:
                # Attempting with a GET request first
                response = requests.get(fetch_url)
                response.raise_for_status()
                if response.status_code == 200:
                    return BytesIO(response.content)
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 405:
                    # If a 'Method Not Allowed' error occurs, it means we need to try a different method.
                    print("GET request not allowed, trying with POST...")
                    try:
                        # Some APIs require a POST request to retrieve the content
                        response = requests.post(fetch_url)
                        response.raise_for_status()
                        if response.status_code == 200:
                            return BytesIO(response.content)
                    except requests.exceptions.RequestException as post_err:
                        # If a POST request also fails, log the specific error
                        print(f"Error with POST request: {post_err}")
                else:
                    # If there's an HTTP error other than 405, log it directly.
                    print(f"HTTP error occurred: {e}")
            
            except requests.exceptions.RequestException as generic_err:
                # For any other request-related errors, log them directly.
                print(f"Error occurred during the request: {generic_err}")

            # If no return has been triggered by successful data retrieval, wait before retrying.
            print(f"Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
            retries += 1

        # After all retries, if the function hasn't returned, it means the image couldn't be fetched.
        print("Max retries exceeded. Failed to fetch the processed image.")
        return None
    
    def extract_image_from_response(self, response):
        try:
            status = response.get("status")
            if status == "success":
                image_url = response["output"][0]
                image_response = requests.get(image_url)
                image_response.raise_for_status()  # Raise HTTPError for bad response (4xx and 5xx)
                if image_response.status_code == 200:
                    image_bytes = BytesIO(image_response.content)
                    image = Image.open(image_bytes)

                    seed = response["meta"]["seed"]
                    saved_image_path, seed = self.save_image(image_bytes, seed)

                    return saved_image_path, seed
                # ... [Handle success response as before]
            elif status == "processing":
                eta = response.get('eta', 5)  # Use default ETA if not provided
                eta = max(5,eta)
                fetch_url = response.get('fetch_result')

                if fetch_url:
                    print(f"Image is still processing. Trying to fetch after {eta} seconds as suggested.")
                    time.sleep(eta)

                    image_bytes = self.fetch_processed_image(fetch_url)
                    if image_bytes:
                        image = Image.open(image_bytes)
                        seed = response["meta"]["seed"]
                        saved_image_path, seed = self.save_image(image_bytes, seed)
                        return saved_image_path, seed
                else:
                    print("Fetch URL not found in the 'processing' response.")
            else:
                print(f"Unhandled API response status: {status}", response)
        except Exception as e:
            print(f"Error extracting image from response: {e}")


    def process_request(self, prompt, image_path):
        response = self.make_api_request(prompt, image_path)
        print(response.text)
        if response is not None and response.status_code == 200:
            api_response = response.json()
            saved_image_path, seed = self.extract_image_from_response(api_response)

            if saved_image_path:
                print(f"Image saved at: {saved_image_path}")
                print(f"Seed: {seed}")
            else:
                print("Failed to save image.")
        elif response is not None:
            print(f"Failed to make API request. Status code: {response.status_code}")
        else:
            print("No response received.")
        return saved_image_path, seed


# Example usage
# api_key = "dPUaQdPuy24XCdSnWS9Bkqhz1V6GKo8HygYcTMnj8vLF3hKPr5bdOU6O3LD2"
# prompt_text = "2 horses"
# image_url = "https://storage.googleapis.com/rimorai_bucket1/%23OutlineImages/fa8f06ed-ccb2-43cc-b5ec-bf4c84eaad9d_txt2img_3999602510.png"

# extractor = ControlNet(api_key)
# extractor.process_request(prompt_text, image_url)

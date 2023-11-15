import base64
import json
import os
import requests

api_key = "sk-uNRgYorLCf7Duk4sNhOob5ibw4woaIm3YbXMiEpkxOoLndwu" #api_key
model_id = "c64117c4-0010-471b-a7b9-caa5663b33a9"
api_host = "https://preview-api.stability.ai"

token = "man"
prompt = "Make this man look like a new born baby"
weight = 0.7
img_path = "masked_dog_dog.png"

payload = {
    "fine_tunes[]": json.dumps({"id": model_id, "token" : token, "weight": weight}),
    "text_prompts[0][text]": prompt,
    "samples": 1,  # num images
    "sampler": "K_DPMPP_2S_ANCESTRAL",
    "steps": 50,
    "seed": 0,  # random
    "cfg_scale": 7.5,
}

init_image = open(img_path, "rb")

response = requests.post(
    f"{api_host}/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image",
    data=payload,
    files={
        "init_image": init_image,
    },
    headers={
        "Authorization": api_key
    },
)

init_image.close()

if response.status_code != 200:
    raise Exception("Non-200 response: " + str(response.text))

data = response.json()

for i, image in enumerate(data["artifacts"]):
    with open(f"v1_img2img_{i}.png", "wb") as f:
        f.write(base64.b64decode(image["base64"]))
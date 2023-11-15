import base64
import requests
import os

class Sampler(None):
    DDIM = "DDIM"
    DDPM = "DDPM"
    K_DPMPP_2M = "K_DPMPP_2M"
    K_DPMPP_2S_ANCESTRAL = "K_DPMPP_2S_ANCESTRAL"
    K_DPM_2 = "K_DPM_2"
    K_DPM_2_ANCESTRAL = "K_DPM_2_ANCESTRAL"
    K_EULER = "K_EULER"
    K_EULER_ANCESTRAL = "K_EULER_ANCESTRAL"
    K_HEUN = "K_HEUN"
    K_LMS = "K_LMS"

    @staticmethod
    def from_string(val) -> None:
        for sampler in Sampler:
            if sampler.value == val:
                return sampler
        raise Exception(f"Unknown Sampler: {val}")

class Stable:
    def __init__(self):
        self.url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image" #stable 1
        # self.url = "https://api.stability.ai/v1/generation/stable-diffusion-v1-5/text-to-image" # stable 1.5
        # self.url = "https://api.stability.ai/v1/generation/stable-diffusion-512-v2-1/text-to-image"  # stable 2

        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-uNRgYorLCf7Duk4sNhOob5ibw4woaIm3YbXMiEpkxOoLndwu",
        }

    def generate_image(self, prompt):
        self.prompt = prompt
        body = {
            "fine_tunes": [
                {
                    "id": "c64117c4-0010-471b-a7b9-caa5663b33a9",
                    "token": "c64117c4-0010-471b-a7b9-caa5663b33a9",
                    #"weight": 1.0  # You can provide the weight directly here
                }
            ],
            "sampler"
            "steps": 40,
            "width": 1024,
            "height": 1024,
            "seed": 0,
            "cfg_scale": 5,
            "samples": 1,
            "text_prompts": [
                {"text": self.prompt, "weight": 1},
                {"text": "blurry, bad", "weight": -1},
            ],
        }

        response = requests.post(self.url, headers=self.headers, json=body)

        if response.status_code != 200:
            raise Exception("Non-200 response: " + str(response.text))

        data = response.json()

        # make sure the out directory exists
        if not os.path.exists("./static/images"):
            os.makedirs("./static/images")

        for i, image in enumerate(data["artifacts"]):
            with open(f'./static/images/txt2img_{image["seed"]}.png', "wb") as f:
                f.write(base64.b64decode(image["base64"]))

            return f'./static/images/txt2img_{image["seed"]}.png', image["seed"]
            
#stable_diffusion = Stable()
#prompt = "generate an image of an astronaut sailing in outer space surrounded by stars and star dust"
#PATH_FILE, seed = stable_diffusion.generate_image(prompt)
import base64
import requests
import os
from tools.test_tune import (
    FineTuningRESTWrapper,
    FineTune,
    DiffusionFineTune,
    DiffusionResult,
    TextPrompt,
    TextToImageParams,
    ENGINE_ID,
    time,
    Sampler,
    )

class RestAPI:
    def __init__(self, api, model_id, model_type):
        self.url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image" #stable 1
        # self.url = "https://api.stability.ai/v1/generation/stable-diffusion-v1-5/text-to-image" # stable 1.5
        # self.url = "https://api.stability.ai/v1/generation/stable-diffusion-512-v2-1/text-to-image"  # stable 2
        self.API_KEY = api
        self.MODEL_ID = model_id
        self.MODEL_TYPE = model_type
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.API_KEY}",
        }
    
    def list_fine_tunes(self):
        response = requests.get(
            f"https://preview-api.stability.ai/v1/fine-tunes",
            headers={"Authorization": self.API_KEY}
        )
        #print(f"Found {len(response)} models")
        for fine_tune in response:
            print(fine_tune)

    # Not implemented yet
    def generate_images(self, prompt):
        rest_api = FineTuningRESTWrapper(self.API_KEY, "https://preview-api.stability.ai")

        fine_tunes = rest_api.list_fine_tunes()
        print(f"Found {len(fine_tunes)} models")
        for fine_tune in fine_tunes:
            print(f"  Model {fine_tune.id} {fine_tune.status:<9} {fine_tune.name}")
        
        dimensions="1024x1024" #@param ['1024x1024', '1152x896', '1216x832', '1344x768', '1536x640', '640x1536', '768x1344', '832x1216', '896x1152']
        #@markdown > The dimensions of the image to generate, in pixels, and in the format width x height.
        samples=1 #@param {type:"slider", min:1, max:10, step:1}
        #@markdown > The number of images to generate. The higher the value the longer the generation times.
        steps=32 #@param {type:"slider", min:30, max:60, step:1}
        #@markdown > The number of iterations or stages a diffusion model goes through in the process of generating an image from a given text prompt. Lower steps will generate more quickly, but if steps are lowered too much, image quality will suffer. Images with higher steps take longer to generate, but often give more detailed results.
        cfg_scale=7 #@param {type:"slider", min:0, max:35, step:1}
        #@markdown > CFG (Classifier Free Guidance) scale determines how strictly the diffusion process adheres to the prompt text (higher values keep your image closer to your prompt).
        seed=0  #@param {type:"number"}
        #@markdown > The noise seed to use during diffusion.  Using `0` means a random seed will be generated for each image.  If you provide a non-zero value, images will be far less random.
        download_results = False # @param {type:"boolean"}
        #@markdown > Results are displayed inline below this section. By checking this box, the generated images will also be downloaded to your local machine.
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(self.MODEL_ID)
        print(self.MODEL_TYPE)
        params = TextToImageParams(
        fine_tunes=[
            DiffusionFineTune(
                id=self.MODEL_ID,
                token=self.MODEL_TYPE,
                # Uncomment the following to provide a weight for the fine-tune
                # weight=1.0
            ),
        ],
        text_prompts=[
            TextPrompt(
                text=prompt + " , customized to $style ",
                # Uncomment the following to provide a weight for the prompt
                # weight=1.0
            ),
        ],
        engine_id=ENGINE_ID,
        samples=samples,
        steps=steps,
        seed=seed,
        cfg_scale=cfg_scale,
        width=int(dimensions.split("x")[0]),
        height=int(dimensions.split("x")[1]),
        sampler=Sampler.K_DPMPP_2S_ANCESTRAL
        )

        start_time = time.time()

        images = rest_api.text_to_image(params)

        elapsed = time.time() - start_time

        print(f"Diffusion completed in {elapsed:.0f} seconds!")
        print(f"The {len(images)} result{'s' if len(images) > 1 else ''} will be displayed below momentarily (depending on the speed of Colab).\n")

        output_directory = "./static/images"

        # Create the output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)

        # Save each image to the output directory
        for i, image_result in enumerate(images):
            base64_data = image_result.base64.split(',')[0]
            image_data = base64.b64decode(base64_data)
            image_path = os.path.join(output_directory, f"image.png")

            with open(image_path, "wb") as f:
                f.write(image_data)

            print(f"Image {i} saved at: {image_path}")
        return f'./static/images/image.png'
    
    # def generate_image(self, prompt):
    #     self.prompt = prompt
    #     body = {
    #         "fine_tunes": 
    #             [ft.to_dict() for ft in params.fine_tunes],
    #         "steps": 40,
    #         "width": 1024,
    #         "height": 1024,
    #         "seed": 0,
    #         "cfg_scale": 5,
    #         "samples": 1,
    #         "text_prompts": [
    #             {"text": self.prompt, "weight": 1},
    #             {"text": "blurry, bad", "weight": -1},
    #         ],
    #     }
    #     print("Sending Prompt!")
    #     response = requests.post(self.url, headers=self.headers, json=body)

    #     print("Prompt Sent!")
    #     if response.status_code != 200:
    #         raise Exception("Non-200 response: " + str(response.text))

    #     data = response.json()

    #     # make sure the out directory exists
    #     if not os.path.exists("../static/images"):
    #         os.makedirs("../static/images")

    #     for i, image in enumerate(data["artifacts"]):
    #         with open(f'../static/images/image.png', "wb") as f:
    #             f.write(base64.b64decode(image["base64"]))

    #         return f'../static/images/image.png', image["seed"]
            
#stable_diffusion = Stable()
#prompt = "an illustration of <c64117c4-0010-471b-a7b9-caa5663b33a9:1>"
#PATH_FILE, seed = stable_diffusion.generate_image(prompt)

#stable_diffusion.list_fine_tunes()
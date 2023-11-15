import getpass
import logging
import shutil
import sys
import time
from pathlib import Path
from zipfile import ZipFile
import os
import io
import warnings
from PIL import Image
from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
from stability_sdk.api import Context, generation
from stability_sdk.finetune import (
    create_model, delete_model, get_model, list_models, resubmit_model, update_model,
    FineTuneMode, FineTuneParameters, FineTuneStatus
)

class gRPCAPI:
    def __init__(self):
        # Our Host URL should not be prepended with "https" nor should it have a trailing slash.
        os.environ['STABILITY_HOST'] = 'grpc.stability.ai:443'

        # Sign up for an account at the following link to get an API Key.
        # https://platform.stability.ai/

        # Click on the following link once you have created an account to be taken to your API Key.
        # https://platform.stability.ai/account/keys

        # Paste your API Key below.
        os.environ['STABILITY_KEY'] = 'sk-uNRgYorLCf7Duk4sNhOob5ibw4woaIm3YbXMiEpkxOoLndwu'

        engine_id = "stable-diffusion-xl-1024-v1-0"

        # Create API context to query user info and generate images
        self.context = Context(os.environ['STABILITY_HOST'], os.environ['STABILITY_KEY'], generate_engine_id=engine_id)
        (balance, pfp) = self.context.get_user_info()
        print(f"Logged in org:{self.context._user_organization_id} with balance:{balance}")

        # Redirect logs to print statements so we can see them in the notebook
        class PrintHandler(logging.Handler):
            def emit(self, record):
                print(self.format(record))
        logging.getLogger().addHandler(PrintHandler())
        logging.getLogger().setLevel(logging.INFO)

        # Set up our connection to the API.
        self.stability_api = client.StabilityInference(
            key=os.environ['STABILITY_KEY'], # API Key reference.
            verbose=True, # Print debug messages.
            engine="stable-diffusion-xl-1024-v1-0", # Set the engine to use for generation.
            # Check out the following link for a list of available engines: https://platform.stability.ai/docs/features/api-parameters#engine
        )

    def generate_images(self, prompt):
        models = list_models(self.context, org_id=self.context._user_organization_id)
        print(f"Found {len(models)} models")
        for model in models:
            print(f"  Model {model.id} {model.name} {model.status}")

        # Set up our initial generation parameters.
        answers = self.context.generate(
            prompts=[prompt + f" as an Illustration of <c64117c4-0010-471b-a7b9-caa5663b33a9:1>"],
            weights=[1],
            width=1024,
            height=1024,
            seed=42,
            steps=40,
            sampler=generation.SAMPLER_DDIM,
            preset="photographic",
        )

        # Set up our warning to print to the console if the adult content classifier is tripped.
        # If adult content classifier is not tripped, save generated images.
        image = answers[generation.ARTIFACT_IMAGE][0]
        if not os.path.exists("./static/images"):
            os.makedirs("./static/images")
        
        image.save(str("Image")+ ".png")

        print("Image Saved")
        return 

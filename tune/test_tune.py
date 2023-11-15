
#API Integration

#@title Add your API key
import getpass
import io
import logging
import requests
import os
import shutil
import sys
import time
import json
import base64
from enum import Enum
from dataclasses import dataclass, is_dataclass, field, asdict
from typing import List, Optional, Any
from IPython.display import clear_output
from pathlib import Path
from PIL import Image
from zipfile import ZipFile

#API Integration
#@markdown Execute this step and paste your API key in the box that appears. <br/> <br/> Visit https://platform.stability.ai/account/keys to get your API key! <br/> <em>Note: If you are not on the fine-tuning whitelist you will receive an error during training!</em>
API_KEY = getpass.getpass('sk-uNRgYorLCf7Duk4sNhOob5ibw4woaIm3YbXMiEpkxOoLndwu')

#Helper Start
ENGINE_ID = "stable-diffusion-xl-1024-v1-0"

class Printable:
    """ Helper class for printing a class to the console. """

    @staticmethod
    def to_json(obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj):
            return asdict(obj)

        return obj

    def __str__(self):
        return f"{self.__class__.__name__}: {json.dumps(self, default=self.to_json, indent=4)}"


class ToDict:
    """ Helper class to simplify converting dataclasses to dicts. """

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class FineTune(Printable):
    id: str
    user_id: str
    name: str
    mode: str
    engine_id: str
    training_set_id: str
    status: str
    failure_reason: Optional[str] = field(default=None)
    duration_seconds: Optional[int] = field(default=None)
    object_prompt: Optional[str] = field(default=None)


@dataclass
class DiffusionFineTune(Printable, ToDict):
    id: str
    token: str
    weight: Optional[float] = field(default=None)


@dataclass
class TextPrompt(Printable, ToDict):
    text: str
    weight: Optional[float] = field(default=None)


class Sampler(Enum):
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
    def from_string(val) -> Enum or None:
        for sampler in Sampler:
            if sampler.value == val:
                return sampler
        raise Exception(f"Unknown Sampler: {val}")


@dataclass
class TextToImageParams(Printable):
    fine_tunes: List[DiffusionFineTune]
    text_prompts: List[TextPrompt]
    samples: int
    sampler: Sampler
    engine_id: str
    steps: int
    seed: Optional[int] = field(default=0)
    cfg_scale: Optional[int] = field(default=7)
    width: Optional[int] = field(default=1024)
    height: Optional[int] = field(default=1024)


@dataclass
class DiffusionResult:
    base64: str
    seed: int
    finish_reason: str

    def __str__(self):
        return f"DiffusionResult(base64='too long to print', seed='{self.seed}', finish_reason='{self.finish_reason}')"

    def __repr__(self):
        return self.__str__()


@dataclass
class TrainingSetBase(Printable):
    id: str
    name: str


@dataclass
class TrainingSetImage(Printable):
    id: str


@dataclass
class TrainingSet(TrainingSetBase):
    images: List[TrainingSetImage]


class FineTuningRESTWrapper:
    """
    Helper class to simplify interacting with the fine-tuning service via
    Stability's REST API.

    While this class can be copied to your local environment, it is not likely
    robust enough for your needs and does not support all of the features that
    the REST API offers.
    """

    def __init__(self, api_key: str, api_host: str):
        self.api_key = api_key
        self.api_host = api_host

    def create_fine_tune(self,
                         name: str,
                         images: List[str],
                         engine_id: str,
                         mode: str,
                         object_prompt: Optional[str] = None) -> FineTune:
        print(f"Creating {mode} fine-tune called '{name}' using {len(images)} images...")

        payload = {"name": name, "engine_id": engine_id, "mode": mode}
        if object_prompt is not None:
            payload["object_prompt"] = object_prompt

        # Create a training set
        training_set_id = self.create_training_set(name=name)
        payload["training_set_id"] = training_set_id
        print(f"\tCreated training set {training_set_id}")

        # Add images to the training set
        for image in images:
            print(f"\t\tAdding {os.path.basename(image)}")
            self.add_image_to_training_set(
                training_set_id=training_set_id,
                image=image
            )

        # Create the fine-tune
        print(f"\tCreating a fine-tune from the training set")
        response = requests.post(
            f"{self.api_host}/v1/fine-tunes",
            json=payload,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
        )
        raise_on_non200(response)
        print(f"\tCreated fine-tune {response.json()['id']}")

        print(f"Success")
        return FineTune(**response.json())

    def get_fine_tune(self, fine_tune_id: str) -> FineTune:
        response = requests.get(
            f"{self.api_host}/v1/fine-tunes/{fine_tune_id}",
            headers={"Authorization": self.api_key}
        )

        raise_on_non200(response)

        return FineTune(**response.json())

    def list_fine_tunes(self) -> List[FineTune]:
        response = requests.get(
            f"{self.api_host}/v1/fine-tunes",
            headers={"Authorization": self.api_key}
        )

        raise_on_non200(response)

        return [FineTune(**ft) for ft in response.json()]

    def rename_fine_tune(self, fine_tune_id: str, name: str) -> FineTune:
        response = requests.patch(
            f"{self.api_host}/v1/fine-tunes/{fine_tune_id}",
            json={"operation": "RENAME", "name": name},
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
        )

        raise_on_non200(response)

        return FineTune(**response.json())

    def retrain_fine_tune(self, fine_tune_id: str) -> FineTune:
        response = requests.patch(
            f"{self.api_host}/v1/fine-tunes/{fine_tune_id}",
            json={"operation": "RETRAIN"},
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
        )

        raise_on_non200(response)

        return FineTune(**response.json())

    def delete_fine_tune(self, fine_tune: FineTune):
        # Delete the underlying training set
        self.delete_training_set(fine_tune.training_set_id)

        # Delete the fine-tune
        response = requests.delete(
            f"{self.api_host}/v1/fine-tunes/{fine_tune.id}",
            headers={"Authorization": self.api_key}
        )

        raise_on_non200(response)

    def create_training_set(self, name: str) -> str:
        response = requests.post(
            f"{self.api_host}/v1/training-sets",
            json={"name": name},
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
        )

        raise_on_non200(response)

        return response.json().get('id')

    def get_training_set(self, training_set_id: str) -> TrainingSet:
        response = requests.get(
            f"{self.api_host}/v1/training-sets/{training_set_id}",
            headers={"Authorization": self.api_key}
        )

        raise_on_non200(response)

        return TrainingSet(**response.json())

    def list_training_sets(self) -> List[TrainingSetBase]:
        response = requests.get(
            f"{self.api_host}/v1/training-sets",
            headers={"Authorization": self.api_key}
        )

        raise_on_non200(response)

        return [TrainingSetBase(**tsb) for tsb in response.json()]

    def add_image_to_training_set(self, training_set_id: str, image: str) -> str:
        with open(image, 'rb') as image_file:
            response = requests.post(
                f"{self.api_host}/v1/training-sets/{training_set_id}/images",
                headers={"Authorization": self.api_key},
                files={'image': image_file}
            )

        raise_on_non200(response)

        return response.json().get('id')

    def remove_image_from_training_set(self, training_set_id: str, image_id: str) -> None:
        response = requests.delete(
            f"{self.api_host}/v1/training-sets/{training_set_id}/images/{image_id}",
            headers={"Authorization": self.api_key}
        )

        raise_on_non200(response)

    def delete_training_set(self, training_set_id: str) -> None:
        response = requests.delete(
            f"{self.api_host}/v1/training-sets/{training_set_id}",
            headers={"Authorization": self.api_key}
        )

        raise_on_non200(response)

    def text_to_image(self, params: TextToImageParams) -> List[DiffusionResult]:
        payload = {
            "fine_tunes": [ft.to_dict() for ft in params.fine_tunes],
            "text_prompts": [tp.to_dict() for tp in params.text_prompts],
            "samples": params.samples,
            "sampler": params.sampler.value,
            "steps": params.steps,
            "seed": params.seed,
            "width": params.width,
            "height": params.height,
            "cfg_scale": params.cfg_scale,
        }

        response = requests.post(
            f"{self.api_host}/v1/generation/{params.engine_id}/text-to-image",
            json=payload,
            headers={
                "Authorization": self.api_key,
                "Accept": "application/json",
            }
        )

        raise_on_non200(response)

        return [
            DiffusionResult(base64=item["base64"], seed=item["seed"], finish_reason=item["finishReason"])
            for item in response.json()["artifacts"]
        ]


def raise_on_non200(response):
    if 200 <= response.status_code < 300:
        return
    raise Exception(f"Status code {response.status_code}: {json.dumps(response.json(), indent=4)}")


# Redirect logs to print statements so we can see them in the notebook
class PrintHandler(logging.Handler):
    def emit(self, record):
        print(self.format(record))
logging.getLogger().addHandler(PrintHandler())
logging.getLogger().setLevel(logging.INFO)

# Initialize the fine-tune service
rest_api = FineTuningRESTWrapper(API_KEY, "https://preview-api.stability.ai")

#Helper End


#Upload Images
#@title Upload ZIP file of images
training_dir = "./train"
Path(training_dir).mkdir(exist_ok=True)
try:
    from google.colab import files

    upload_res = files.upload()
    print(upload_res.keys())
    extracted_dir = list(upload_res.keys())[0]
    print(f"Received {extracted_dir}")
    if not extracted_dir.endswith(".zip"):
        raise ValueError("Uploaded file must be a zip file")

    zf = ZipFile(io.BytesIO(upload_res[extracted_dir]), "r")
    extracted_dir = Path(extracted_dir).stem
    print(f"Extracting to {extracted_dir}")
    zf.extractall(extracted_dir)

    for root, dirs, files in os.walk(extracted_dir):
        for file in files:
            source_path = os.path.join(root, file)
            target_path = os.path.join(training_dir, file)

            if 'MACOSX' in source_path or 'DS' in source_path:
              continue
            print('Copying', source_path, '==>', target_path)
            # Move the file to the target directory
            shutil.move(source_path, target_path)


except ImportError:
    pass

print(f"Using training images from: {training_dir}")


#Creating Fine-tune
#@title Create a fine-tune
fine_tune_name = "my dog spot" #@param {type:"string"}
#@markdown > Requirements: <ul><li>Must be unique (only across your account, not globally)</li> <li>Must be between 3 and 64 characters (inclusive)</li> <li>Must only contain letters, numbers, spaces, or hyphens</li></ul>
training_mode = "OBJECT" #@param ["FACE", "STYLE", "OBJECT"] {type:"string"}
#@markdown > Determines the kind of fine-tune you're creating: <ul><li><code>FACE</code> - a fine-tune on faces; expects pictures containing a face; automatically crops and centers on the face detected in the input photos.</li> <li> <code>OBJECT</code> - a fine-tune on a particular object (e.g. a bottle); segments out the object using the `object_prompt` below</li> <li><code>STYLE</code> - a fine-tune on a particular style (e.g. satellite photos of earth); crops the images and filters for image quality.</li></ul>
object_prompt = "dog" #@param {type:"string"}
#@markdown > (This field is ignored if `training_mode` is `FACE` or `STYLE`). <br/> Used for segmenting out your subject when the `training_mode` is `OBJECT`. If you want to fine tune on a cat, use `cat` - for a bottle of liquor, use `bottle`. In general, it's best to use the most general word you can to describe your object.

# Gather training images
images = []
for filename in os.listdir(training_dir):
    if os.path.splitext(filename)[1].lower() in ['.png', '.jpg', '.jpeg', '.heic']:
        images.append(os.path.join(training_dir, filename))

# Create the fine-tune
fine_tune = rest_api.create_fine_tune(
    name=fine_tune_name,
    images=images,
    mode=training_mode,
    object_prompt=object_prompt if training_mode == "OBJECT" else None,
    engine_id=ENGINE_ID,
)

print()
print(fine_tune)

#Check on training status
start_time = time.time()
while fine_tune.status != "COMPLETED" and fine_tune.status != "FAILED":
    fine_tune = rest_api.get_fine_tune(fine_tune.id)
    elapsed = time.time() - start_time
    clear_output(wait=True)
    print(f"Training '{fine_tune.name}' ({fine_tune.id}) status: {fine_tune.status} for {elapsed:.0f} seconds")
    time.sleep(10)

clear_output(wait=True)
status_message = "completed" if fine_tune.status == "COMPLETED" else "failed"
print(f"Training '{fine_tune.name}' ({fine_tune.id}) {status_message} after {elapsed:.0f} seconds")

#@title (Optional) Retrain if training failed
if fine_tune.status == "FAILED":
    print(f"Training failed, due to \"{fine_tune.failure_reason}\". Retraining...")
    fine_tune = rest_api.retrain_fine_tune(fine_tune.id)

#@title <font color="#FFFFFF">Generate Images
#@markdown ## Diffusion parameters

fine_tune_alias="$my-dog" #@param {type:"string"}
#@markdown > This is an alias for your fine-tune, allowing you to refer to the fine-tune directly in the prompt.  This token is ephemeral and can be any valid text (though we recommend starting it with a `$` and using dashes instead of spaces e.g. `$my-dog`).  This is _not_ the fine_tune_name you assigned in a prior step, this is just a short-hand we use to determine where to apply your fine-tune in your prompt. <br/><br/> For example, if your token was `$my-dog` you might use a prompt like: `a picture of $my-dog` or `$my-dog chasing a rabbit`.  This syntax really shine when you have more than one fine-tune too!  Given some fine-tune of film noir images you could use a prompt like `$my-dog in the style of $film-noir`.
prompt="a photo of $my-dog"  #@param {type:"string"}
#@markdown > The prompt to diffuse with.  Must contain the `fine_tune_alias` at least once.
dimensions="1024x1024" #@param ['1024x1024', '1152x896', '1216x832', '1344x768', '1536x640', '640x1536', '768x1344', '832x1216', '896x1152']
#@markdown > The dimensions of the image to generate, in pixels, and in the format width x height.
samples=2 #@param {type:"slider", min:1, max:10, step:1}
#@markdown > The number of images to generate. The higher the value the longer the generation times.
steps=32 #@param {type:"slider", min:30, max:60, step:1}
#@markdown > The number of iterations or stages a diffusion model goes through in the process of generating an image from a given text prompt. Lower steps will generate more quickly, but if steps are lowered too much, image quality will suffer. Images with higher steps take longer to generate, but often give more detailed results.
cfg_scale=7 #@param {type:"slider", min:0, max:35, step:1}
#@markdown > CFG (Classifier Free Guidance) scale determines how strictly the diffusion process adheres to the prompt text (higher values keep your image closer to your prompt).
seed=0  #@param {type:"number"}
#@markdown > The noise seed to use during diffusion.  Using `0` means a random seed will be generated for each image.  If you provide a non-zero value, images will be far less random.
download_results = False # @param {type:"boolean"}
#@markdown > Results are displayed inline below this section. By checking this box, the generated images will also be downloaded to your local machine.

params = TextToImageParams(
    fine_tunes=[
        DiffusionFineTune(
            id=fine_tune.id,
            token=fine_tune_alias,
            # Uncomment the following to provide a weight for the fine-tune
            # weight=1.0
        ),
    ],
    text_prompts=[
        TextPrompt(
            text=prompt,
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

for image in images:
  display(Image.open(io.BytesIO(base64.b64decode(image.base64))))

if download_results:
  print(f"Downloading {len(images)} images to disk.")
  from google.colab import files
  Path('./out').mkdir(parents=True, exist_ok=True)
  for index, image in enumerate(images):
    with open(f'./out/txt2img_{image.seed}_{index}.png', "wb") as f:
        f.write(base64.b64decode(image.base64))
        files.download(f.name)
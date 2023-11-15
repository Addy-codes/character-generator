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
#from IPython.display import clear_output
from pathlib import Path
from PIL import Image
from zipfile import ZipFile
from config import api as API_KEY

#@markdown Execute this step and paste your API key in the box that appears. <br/> <br/> Visit https://platform.stability.ai/account/keys to get your API key! <br/> <em>Note: If you are not on the fine-tuning whitelist you will receive an error during training!</em>


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


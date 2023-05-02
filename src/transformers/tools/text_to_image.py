from transformers.tools.base import Tool
from transformers.utils import is_accelerate_available, is_diffusers_available


if is_accelerate_available():
    from accelerate.state import PartialState

if is_diffusers_available():
    from diffusers import DiffusionPipeline


TEXT_TO_IMAGE_DESCRIPTION = (
    "This is a tool that creates an image according to a prompt, which is a text description. It takes an input named `prompt` which "
    "contains the image description and outputs an image."
)


class TextToImageTool(Tool):
    default_checkpoint = "runwayml/stable-diffusion-v1-5"
    description = TEXT_TO_IMAGE_DESCRIPTION

    def __init__(self, device=None, **hub_kwargs) -> None:
        if not is_accelerate_available():
            raise ImportError("Accelerate should be installed in order to use tools.")
        if not is_diffusers_available():
            raise ImportError("Diffusers should be installed in order to use the StableDiffusionTool.")

        super().__init__()

        self.device = device
        self.pipeline = None
        self.hub_kwargs = hub_kwargs

    def setup(self):
        if self.device is None:
            self.device = PartialState().default_device

        self.pipeline = DiffusionPipeline.from_pretrained(self.default_checkpoint)
        self.pipeline.to(self.device)

        self.is_initialized = True

    def __call__(self, prompt):
        if not self.is_initialized:
            self.setup()

        return self.pipeline(prompt).images[0]

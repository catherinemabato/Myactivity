from typing import Dict

from ..utils import is_vision_available
from .base import GenericTensor, Pipeline


if is_vision_available():
    from ..image_utils import load_image


class ImageFeatureExtractionPipeline(Pipeline):
    """
    Image feature extraction pipeline uses no model head. This pipeline extracts the hidden states from the base
    transformer, which can be used as features in downstream tasks.

    Example:

    ```python
    >>> from transformers import pipeline

    >>> extractor = pipeline(model="google/vit-base-patch16-224", task="image-feature-extraction")
    >>> result = extractor("https://huggingface.co/datasets/Narsil/image_dummy/raw/main/parrots.png", return_tensors=True)
    >>> result.shape  # This is a tensor of shape [1, sequence_lenth, hidden_dimension] representing the input image.
    torch.Size([1, 197, 768])
    ```

    Learn more about the basics of using a pipeline in the [pipeline tutorial](../pipeline_tutorial)

    This image feature extraction pipeline can currently be loaded from [`pipeline`] using the task identifier:
    `"image-feature-extraction"`.

    All vision models may be used for this pipeline. See a list of all models, including community-contributed models on
    [huggingface.co/models](https://huggingface.co/models).

    Arguments:
        model ([`PreTrainedModel`] or [`TFPreTrainedModel`]):
            The model that will be used by the pipeline to make predictions. This needs to be a model inheriting from
            [`PreTrainedModel`] for PyTorch and [`TFPreTrainedModel`] for TensorFlow.
        image_processor ([`PreTrainedImageProcessor`], *optional*):
            The image processor that will be used by the pipeline to encode data for the model. This object inherits from
            [`PreTrainedImageProcessor`].
        modelcard (`str` or [`ModelCard`], *optional*):
            Model card attributed to the model for this pipeline.
        framework (`str`, *optional*):
            The framework to use, either `"pt"` for PyTorch or `"tf"` for TensorFlow. The specified framework must be
            installed.

            If no framework is specified, will default to the one currently installed. If no framework is specified and
            both frameworks are installed, will default to the framework of the `model`, or to PyTorch if no model is
            provided.
        args_parser ([`~pipelines.ArgumentHandler`], *optional*):
            Reference to the object in charge of parsing supplied pipeline parameters.
        device (`int`, *optional*, defaults to -1):
            Device ordinal for CPU/GPU supports. Setting this to -1 will leverage CPU, a positive will run the model on
            the associated CUDA device id.
        torch_dtype (`str` or `torch.dtype`, *optional*):
            Sent directly as `model_kwargs` (just a simpler shortcut) to use the available precision for this model
            (`torch.float16`, `torch.bfloat16`, ... or `"auto"`).
    """

    def _sanitize_parameters(self, return_tensors=None, **kwargs):
        preprocess_params = kwargs.pop("image_processor_kwargs", {})
        postprocess_params = {"return_tensors": return_tensors} if return_tensors is not None else {}

        if "timeout" in kwargs:
            preprocess_params["timeout"] = kwargs["timeout"]

        return preprocess_params, {}, postprocess_params

    def preprocess(self, image, timeout=None, **image_processor_kwargs) -> Dict[str, GenericTensor]:
        image = load_image(image, timeout=timeout)
        model_inputs = self.image_processor(image, return_tensors=self.framework, **image_processor_kwargs)
        return model_inputs

    def _forward(self, model_inputs):
        model_outputs = self.model(**model_inputs)
        return model_outputs

    def postprocess(self, model_outputs, return_tensors=False):
        # [0] is the first available tensor, logits or last_hidden_state.
        if return_tensors:
            return model_outputs[0]
        if self.framework == "pt":
            return model_outputs[0].tolist()
        elif self.framework == "tf":
            return model_outputs[0].numpy().tolist()

    def __call__(self, *args, **kwargs):
        """
        Extract the features of the input(s).

        Args:
            images (`str`, `List[str]`, `PIL.Image` or `List[PIL.Image]`):
                The pipeline handles three types of images:

                - A string containing a http link pointing to an image
                - A string containing a local path to an image
                - An image loaded in PIL directly

                The pipeline accepts either a single image or a batch of images, which must then be passed as a string.
                Images in a batch must all be in the same format: all as http links, all as local paths, or all as PIL
                images.
            timeout (`float`, *optional*, defaults to None):
                The maximum time in seconds to wait for fetching images from the web. If None, no timeout is used and
                the call may block forever.
        Return:
            A nested list of `float`: The features computed by the model.
        """
        return super().__call__(*args, **kwargs)

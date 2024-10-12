from typing import Any, Dict, List, Optional, Union

from ..utils import add_end_docstrings, is_torch_available, is_vision_available, logging, requires_backends
from ..utils.deprecation import deprecate_kwarg
from .base import Pipeline, build_pipeline_init_args


if is_vision_available():
    from PIL import Image

    from ..image_utils import load_image

if is_torch_available():
    import torch

    from ..models.auto.modeling_auto import MODEL_FOR_ZERO_SHOT_OBJECT_DETECTION_MAPPING_NAMES

logger = logging.get_logger(__name__)


@add_end_docstrings(build_pipeline_init_args(has_processor=True))
class ZeroShotObjectDetectionPipeline(Pipeline):
    """
    Zero shot object detection pipeline using `OwlViTForObjectDetection`. This pipeline predicts bounding boxes of
    objects when you provide an image and a set of `candidate_labels`.

    Example:

    ```python
    >>> from transformers import pipeline

    >>> detector = pipeline(model="google/owlvit-base-patch32", task="zero-shot-object-detection")
    >>> detector(
    ...     "http://images.cocodataset.org/val2017/000000039769.jpg",
    ...     candidate_labels=["cat", "couch"],
    ... )
    [{'score': 0.287, 'label': 'cat', 'box': {'xmin': 324, 'ymin': 20, 'xmax': 640, 'ymax': 373}}, {'score': 0.254, 'label': 'cat', 'box': {'xmin': 1, 'ymin': 55, 'xmax': 315, 'ymax': 472}}, {'score': 0.121, 'label': 'couch', 'box': {'xmin': 4, 'ymin': 0, 'xmax': 642, 'ymax': 476}}]

    >>> detector(
    ...     "https://huggingface.co/datasets/Narsil/image_dummy/raw/main/parrots.png",
    ...     candidate_labels=["head", "bird"],
    ... )
    [{'score': 0.119, 'label': 'bird', 'box': {'xmin': 71, 'ymin': 170, 'xmax': 410, 'ymax': 508}}]
    ```

    Learn more about the basics of using a pipeline in the [pipeline tutorial](../pipeline_tutorial)

    This object detection pipeline can currently be loaded from [`pipeline`] using the following task identifier:
    `"zero-shot-object-detection"`.

    See the list of available models on
    [huggingface.co/models](https://huggingface.co/models?filter=zero-shot-object-detection).
    """

    _load_processor = True

    # set to False because required sub-processors will be loaded with the `Processor` class
    _load_tokenizer = False
    _load_image_processor = False
    _load_feature_extractor = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.framework == "tf":
            raise ValueError(f"The {self.__class__} is only available in PyTorch.")

        requires_backends(self, "vision")
        self.check_model_type(MODEL_FOR_ZERO_SHOT_OBJECT_DETECTION_MAPPING_NAMES)

    def __call__(
        self,
        image: Union[str, "Image.Image", List[Dict[str, Any]]],
        candidate_labels: Union[str, List[str]] = None,
        threshold: float = 0.1,
        top_k: Optional[int] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ):
        """
        Detect objects (bounding boxes & classes) in the image(s) passed as inputs.

        Args:
            image (`str`, `PIL.Image` or `List[Dict[str, Any]]`):
                The pipeline handles three types of images:

                - A string containing an http url pointing to an image
                - A string containing a local path to an image
                - An image loaded in PIL directly

                You can use this parameter to send directly a list of images, or a dataset or a generator like so:

                ```python
                >>> from transformers import pipeline

                >>> detector = pipeline(model="google/owlvit-base-patch32", task="zero-shot-object-detection")
                >>> detector(
                ...     [
                ...         {
                ...             "image": "http://images.cocodataset.org/val2017/000000039769.jpg",
                ...             "candidate_labels": ["cat", "couch"],
                ...         },
                ...         {
                ...             "image": "http://images.cocodataset.org/val2017/000000039769.jpg",
                ...             "candidate_labels": ["cat", "couch"],
                ...         },
                ...     ]
                ... )
                [[{'score': 0.287, 'label': 'cat', 'box': {'xmin': 324, 'ymin': 20, 'xmax': 640, 'ymax': 373}}, {'score': 0.25, 'label': 'cat', 'box': {'xmin': 1, 'ymin': 55, 'xmax': 315, 'ymax': 472}}, {'score': 0.121, 'label': 'couch', 'box': {'xmin': 4, 'ymin': 0, 'xmax': 642, 'ymax': 476}}], [{'score': 0.287, 'label': 'cat', 'box': {'xmin': 324, 'ymin': 20, 'xmax': 640, 'ymax': 373}}, {'score': 0.254, 'label': 'cat', 'box': {'xmin': 1, 'ymin': 55, 'xmax': 315, 'ymax': 472}}, {'score': 0.121, 'label': 'couch', 'box': {'xmin': 4, 'ymin': 0, 'xmax': 642, 'ymax': 476}}]]
                ```


            candidate_labels (`str` or `List[str]` or `List[List[str]]`):
                What the model should recognize in the image.

            threshold (`float`, *optional*, defaults to 0.1):
                The probability necessary to make a prediction.

            top_k (`int`, *optional*, defaults to None):
                The number of top predictions that will be returned by the pipeline. If the provided number is `None`
                or higher than the number of predictions available, it will default to the number of predictions.

            timeout (`float`, *optional*, defaults to None):
                The maximum time in seconds to wait for fetching images from the web. If None, no timeout is set and
                the call may block forever.


        Return:
            A list of lists containing prediction results, one list per input image. Each list contains dictionaries
            with the following keys:

            - **label** (`str`) -- Text query corresponding to the found object.
            - **score** (`float`) -- Score corresponding to the object (between 0 and 1).
            - **box** (`Dict[str,int]`) -- Bounding box of the detected object in image's original size. It is a
              dictionary with `x_min`, `x_max`, `y_min`, `y_max` keys.
        """
        if isinstance(image, (str, Image.Image)):
            inputs = {"image": image, "candidate_labels": candidate_labels}
        else:
            inputs = image
        results = super().__call__(inputs, timeout=timeout, threshold=threshold, top_k=top_k, **kwargs)
        return results

    def _sanitize_parameters(self, **kwargs):
        preprocess_params = {}
        if "timeout" in kwargs:
            preprocess_params["timeout"] = kwargs["timeout"]
        postprocess_params = {}
        if "threshold" in kwargs:
            postprocess_params["threshold"] = kwargs["threshold"]
        if "top_k" in kwargs:
            postprocess_params["top_k"] = kwargs["top_k"]
        return preprocess_params, {}, postprocess_params

    @deprecate_kwarg("text_queries", new_name="candidate_labels", version="5.0.0")
    def _preprocess_input_keys(self, image, candidate_labels):
        """
        The method is used to convert input keys to pipeline specific keys, taking into consideration
        backward compatibility for deprecated ones.
        """
        return {"image": image, "candidate_labels": candidate_labels}

    def preprocess(self, inputs, timeout=None):
        # convert keys to unified format: image + candidate_labels
        inputs = self._preprocess_input_keys(**inputs)

        image = load_image(inputs["image"], timeout=timeout)
        candidate_labels = inputs["candidate_labels"]

        # preprocess the inputs
        model_inputs = self.processor(images=image, text=candidate_labels, return_tensors=self.framework)

        # save extra data for post processing
        model_inputs["_target_size"] = [image.height, image.width]
        model_inputs["_candidate_labels"] = candidate_labels

        return model_inputs

    def _forward(self, model_inputs):
        # separate extra data and model inputs for forward
        extras = {k: v for k, v in model_inputs.items() if k.startswith("_")}
        inputs = {k: v for k, v in model_inputs.items() if not k.startswith("_")}

        # forward
        model_outputs = self.model(**inputs)

        # pass extra data for post processing
        outputs = {**model_outputs, **extras}

        return outputs

    def postprocess(self, model_outputs, threshold=0.1, top_k=None):
        if hasattr(self.processor, "post_process_grounded_object_detection"):
            # Grounding Dino and OmDet cases
            outputs = self.processor.post_process_grounded_object_detection(
                model_outputs,
                model_outputs["_input_ids"],
                box_threshold=threshold,
                text_threshold=threshold,
                target_sizes=[model_outputs["_target_size"]],
            )[0]
        else:
            # OwlViT and OwlV2 cases
            outputs = self.processor.post_process_object_detection(
                outputs=model_outputs, threshold=threshold, target_sizes=[model_outputs["_target_size"]]
            )[0]
            labels = model_outputs["_candidate_labels"]
            outputs["labels"] = [labels[label_id.item()] for label_id in outputs["labels"]]

        scores = outputs["scores"].tolist()
        boxes = [self._get_bounding_box(box) for box in outputs["boxes"]]
        labels = outputs["labels"]

        annotations = [
            {"score": score, "label": label, "box": box} for score, label, box in zip(scores, labels, boxes)
        ]

        annotations = sorted(annotations, key=lambda x: x["score"], reverse=True)
        if top_k:
            annotations = annotations[:top_k]

        return annotations

    def _get_bounding_box(self, box: "torch.Tensor") -> Dict[str, int]:
        """
        Turns list [xmin, xmax, ymin, ymax] into dict { "xmin": xmin, ... }

        Args:
            box (`torch.Tensor`): Tensor containing the coordinates in corners format.

        Returns:
            bbox (`Dict[str, int]`): Dict containing the coordinates in corners format.
        """
        if self.framework != "pt":
            raise ValueError("The ZeroShotObjectDetectionPipeline is only available in PyTorch.")
        xmin, ymin, xmax, ymax = box.int().tolist()
        bbox = {
            "xmin": xmin,
            "ymin": ymin,
            "xmax": xmax,
            "ymax": ymax,
        }
        return bbox

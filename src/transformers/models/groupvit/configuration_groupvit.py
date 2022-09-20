# coding=utf-8
# Copyright 2022 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" GroupViT model configuration"""

import copy
import os
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Mapping, Optional, Union

from ...configuration_utils import PretrainedConfig
from ...onnx import OnnxConfig
from ...utils import logging


if TYPE_CHECKING:
    from ...processing_utils import ProcessorMixin
    from ...utils import TensorType


logger = logging.get_logger(__name__)

GROUPVIT_PRETRAINED_CONFIG_ARCHIVE_MAP = {
    "nvidia/groupvit-gcc-yfcc": "https://huggingface.co/nvidia/groupvit-gcc-yfcc/resolve/main/config.json",
}


class GroupViTTextConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`GroupViTTextModel`]. It is used to instantiate an
    GroupViT model according to the specified arguments, defining the model architecture. Instantiating a configuration
    with the defaults will yield a similar configuration to that of the GroupViT
    [nvidia/groupvit-gcc-yfcc](https://huggingface.co/nvidia/groupvit-gcc-yfcc) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        vocab_size (`int`, *optional*, defaults to 49408):
            Vocabulary size of the GroupViT text model. Defines the number of different tokens that can be represented
            by the `inputs_ids` passed when calling [`GroupViTModel`].
        hidden_size (`int`, *optional*, defaults to 256):
            Dimensionality of the encoder layers and the pooler layer.
        intermediate_size (`int`, *optional*, defaults to 1024):
            Dimensionality of the "intermediate" (i.e., feed-forward) layer in the Transformer encoder.
        num_hidden_layers (`int`, *optional*, defaults to 12):
            Number of hidden layers in the Transformer encoder.
        num_attention_heads (`int`, *optional*, defaults to 4):
            Number of attention heads for each attention layer in the Transformer encoder.
        max_position_embeddings (`int`, *optional*, defaults to 77):
            The maximum sequence length that this model might ever be used with. Typically set this to something large
            just in case (e.g., 512 or 1024 or 2048).
        hidden_act (`str` or `function`, *optional*, defaults to `"quick_gelu"`):
            The non-linear activation function (function or string) in the encoder and pooler. If string, `"gelu"`,
            `"relu"`, `"selu"` and `"gelu_new"` ``"quick_gelu"` are supported.
        layer_norm_eps (`float`, *optional*, defaults to 1e-5):
            The epsilon used by the layer normalization layers.
        attention_dropout (`float`, *optional*, defaults to 0.0):
            The dropout ratio for the attention probabilities.
        dropout (`float`, *optional*, defaults to 0.0):
            The dropout probability for all fully connected layers in the embeddings, encoder, and pooler.
        initializer_range (`float`, *optional*, defaults to 0.02):
            The standard deviation of the truncated_normal_initializer for initializing all weight matrices.
        initializer_factor (`float`, *optional*, defaults to 1.0):
            A factor for initializing all weight matrices (should be kept to 1, used internally for initialization
            testing).

    Example:

    ```python
    >>> from transformers import GroupViTTextConfig, GroupViTTextModel

    >>> # Initializing a GroupViTTextModel with nvidia/groupvit-gcc-yfcc style configuration
    >>> configuration = GroupViTTextConfig()

    >>> model = GroupViTTextModel(configuration)

    >>> # Accessing the model configuration
    >>> configuration = model.config
    ```"""
    model_type = "groupvit_text_model"

    def __init__(
        self,
        vocab_size=49408,
        hidden_size=256,
        intermediate_size=1024,
        num_hidden_layers=12,
        num_attention_heads=4,
        max_position_embeddings=77,
        hidden_act="quick_gelu",
        layer_norm_eps=0.00001,
        dropout=0.0,
        attention_dropout=0.0,
        initializer_range=0.02,
        initializer_factor=1.0,
        pad_token_id=1,
        bos_token_id=0,
        eos_token_id=2,
        **kwargs
    ):
        super().__init__(pad_token_id=pad_token_id, bos_token_id=bos_token_id, eos_token_id=eos_token_id, **kwargs)

        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.intermediate_size = intermediate_size
        self.dropout = dropout
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.max_position_embeddings = max_position_embeddings
        self.layer_norm_eps = layer_norm_eps
        self.hidden_act = hidden_act
        self.initializer_range = initializer_range
        self.initializer_factor = initializer_factor
        self.attention_dropout = attention_dropout

    @classmethod
    def from_pretrained(cls, pretrained_model_name_or_path: Union[str, os.PathLike], **kwargs) -> "PretrainedConfig":
        config_dict, kwargs = cls.get_config_dict(pretrained_model_name_or_path, **kwargs)

        # get the text config dict if we are loading from GroupViTConfig
        if config_dict.get("model_type") == "groupvit":
            config_dict = config_dict["text_config"]

        if "model_type" in config_dict and hasattr(cls, "model_type") and config_dict["model_type"] != cls.model_type:
            logger.warning(
                f"You are using a model of type {config_dict['model_type']} to instantiate a model of type "
                f"{cls.model_type}. This is not supported for all configurations of models and can yield errors."
            )

        return cls.from_dict(config_dict, **kwargs)


class GroupViTVisionConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`GroupViTVisionModel`]. It is used to instantiate
    an GroupViT model according to the specified arguments, defining the model architecture. Instantiating a
    configuration with the defaults will yield a similar configuration to that of the GroupViT
    [nvidia/groupvit-gcc-yfcc](https://huggingface.co/nvidia/groupvit-gcc-yfcc) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        hidden_size (`int`, *optional*, defaults to 384):
            Dimensionality of the encoder layers and the pooler layer.
        intermediate_size (`int`, *optional*, defaults to 1536):
            Dimensionality of the "intermediate" (i.e., feed-forward) layer in the Transformer encoder.
        depths (`List[int]`, *optional*, defaults to [6, 3, 3]):
            The number of layers in each encoder block.
        num_group_tokens (`List[int]`, *optional*, defaults to [64, 8, 0]):
            The number of group tokens for each stage.
        num_output_groups (`List[int]`, *optional*, defaults to [64, 8, 0]):
            The number of output groups for each stage, 0 means no group.
        num_attention_heads (`int`, *optional*, defaults to 6):
            Number of attention heads for each attention layer in the Transformer encoder.
        image_size (`int`, *optional*, defaults to 224):
            The size (resolution) of each image.
        patch_size (`int`, *optional*, defaults to 16):
            The size (resolution) of each patch.
        hidden_act (`str` or `function`, *optional*, defaults to `"gelu"`):
            The non-linear activation function (function or string) in the encoder and pooler. If string, `"gelu"`,
            `"relu"`, `"selu"` and `"gelu_new"` ``"quick_gelu"` are supported.
        layer_norm_eps (`float`, *optional*, defaults to 1e-5):
            The epsilon used by the layer normalization layers.
        dropout (`float`, *optional*, defaults to 0.0):
            The dropout probabilitiy for all fully connected layers in the embeddings, encoder, and pooler.
        attention_dropout (`float`, *optional*, defaults to 0.0):
            The dropout ratio for the attention probabilities.
        initializer_range (`float`, *optional*, defaults to 0.02):
            The standard deviation of the truncated_normal_initializer for initializing all weight matrices.
        initializer_factor (`float`, *optional*, defaults to 1.0):
            A factor for initializing all weight matrices (should be kept to 1, used internally for initialization
            testing).

    Example:

    ```python
    >>> from transformers import GroupViTVisionConfig, GroupViTVisionModel

    >>> # Initializing a GroupViTVisionModel with nvidia/groupvit-gcc-yfcc style configuration
    >>> configuration = GroupViTVisionConfig()

    >>> model = GroupViTVisionModel(configuration)

    >>> # Accessing the model configuration
    >>> configuration = model.config
    ```"""

    model_type = "groupvit_vision_model"

    def __init__(
        self,
        hidden_size=384,
        intermediate_size=1536,
        depths=[6, 3, 3],
        num_hidden_layers=12,
        num_group_tokens=[64, 8, 0],
        num_output_groups=[64, 8, 8],
        num_attention_heads=6,
        image_size=224,
        patch_size=16,
        num_channels=3,
        hidden_act="gelu",
        layer_norm_eps=1e-5,
        dropout=0.0,
        attention_dropout=0.0,
        initializer_range=0.02,
        initializer_factor=1.0,
        assign_eps=1.0,
        assign_mlp_ratio=[0.5, 4],
        qkv_bias=True,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.hidden_size = hidden_size
        self.intermediate_size = intermediate_size
        self.depths = depths
        if num_hidden_layers != sum(depths):
            logger.warning(
                f"Manually setting num_hidden_layers to {num_hidden_layers}, but we expect num_hidden_layers ="
                f" sum(depth) = {sum(depths)}"
            )
        self.num_hidden_layers = num_hidden_layers
        self.num_group_tokens = num_group_tokens
        self.num_output_groups = num_output_groups
        self.num_attention_heads = num_attention_heads
        self.image_size = image_size
        self.patch_size = patch_size
        self.num_channels = num_channels
        self.hidden_act = hidden_act
        self.layer_norm_eps = layer_norm_eps
        self.dropout = dropout
        self.attention_dropout = attention_dropout
        self.initializer_range = initializer_range
        self.initializer_factor = initializer_factor
        self.assign_eps = assign_eps
        self.assign_mlp_ratio = assign_mlp_ratio
        self.qkv_bias = qkv_bias

    @classmethod
    def from_pretrained(cls, pretrained_model_name_or_path: Union[str, os.PathLike], **kwargs) -> "PretrainedConfig":
        config_dict, kwargs = cls.get_config_dict(pretrained_model_name_or_path, **kwargs)

        # get the vision config dict if we are loading from GroupViTConfig
        if config_dict.get("model_type") == "groupvit":
            config_dict = config_dict["vision_config"]

        if "model_type" in config_dict and hasattr(cls, "model_type") and config_dict["model_type"] != cls.model_type:
            logger.warning(
                f"You are using a model of type {config_dict['model_type']} to instantiate a model of type "
                f"{cls.model_type}. This is not supported for all configurations of models and can yield errors."
            )

        return cls.from_dict(config_dict, **kwargs)


class GroupViTConfig(PretrainedConfig):
    r"""
    [`GroupViTConfig`] is the configuration class to store the configuration of a [`GroupViTModel`]. It is used to
    instantiate a GroupViT model according to the specified arguments, defining the text model and vision model
    configs.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        text_config_dict (`dict`, *optional*):
            Dictionary of configuration options used to initialize [`GroupViTTextConfig`].
        vision_config_dict (`dict`, *optional*):
            Dictionary of configuration options used to initialize [`GroupViTVisionConfig`].
        projection_dim (`int`, *optional*, defaults to 256):
            Dimentionality of text and vision projection layers.
        projection_intermediate_dim (`int`, *optional*, defaults to 4096):
            Dimentionality of intermediate layer of text and vision projection layers.
        logit_scale_init_value (`float`, *optional*, defaults to 2.6592):
            The inital value of the *logit_scale* parameter. Default is used as per the original GroupViT
            implementation.
        kwargs (*optional*):
            Dictionary of keyword arguments.
    """

    model_type = "groupvit"
    is_composition = True

    def __init__(
        self,
        text_config_dict=None,
        vision_config_dict=None,
        projection_dim=256,
        projection_intermediate_dim=4096,
        logit_scale_init_value=2.6592,
        **kwargs
    ):
        super().__init__(text_config_dict=text_config_dict, vision_config_dict=vision_config_dict, **kwargs)

        if text_config_dict is None:
            text_config_dict = {}
            logger.info("text_config_dict is None. Initializing the GroupViTTextConfig with default values.")

        if vision_config_dict is None:
            vision_config_dict = {}
            logger.info("vision_config_dict is None. initializing the GroupViTVisionConfig with default values.")

        self.text_config = GroupViTTextConfig(**text_config_dict)
        self.vision_config = GroupViTVisionConfig(**vision_config_dict)

        self.projection_dim = projection_dim
        self.projection_intermediate_dim = projection_intermediate_dim
        self.logit_scale_init_value = logit_scale_init_value
        self.initializer_range = 0.02
        self.initializer_factor = 1.0
        self.output_segmentation = False

    @classmethod
    def from_text_vision_configs(cls, text_config: GroupViTTextConfig, vision_config: GroupViTVisionConfig, **kwargs):
        r"""
        Instantiate a [`GroupViTConfig`] (or a derived class) from groupvit text model configuration and groupvit
        vision model configuration.

        Returns:
            [`GroupViTConfig`]: An instance of a configuration object
        """

        return cls(text_config_dict=text_config.to_dict(), vision_config_dict=vision_config.to_dict(), **kwargs)

    def to_dict(self):
        """
        Serializes this instance to a Python dictionary. Override the default [`~PretrainedConfig.to_dict`].

        Returns:
            `Dict[str, any]`: Dictionary of all the attributes that make up this configuration instance,
        """
        output = copy.deepcopy(self.__dict__)
        output["text_config"] = self.text_config.to_dict()
        output["vision_config"] = self.vision_config.to_dict()
        output["model_type"] = self.__class__.model_type
        return output


class GroupViTOnnxConfig(OnnxConfig):
    @property
    def inputs(self) -> Mapping[str, Mapping[int, str]]:
        return OrderedDict(
            [
                ("input_ids", {0: "batch", 1: "sequence"}),
                ("pixel_values", {0: "batch", 1: "num_channels", 2: "height", 3: "width"}),
                ("attention_mask", {0: "batch", 1: "sequence"}),
            ]
        )

    @property
    def outputs(self) -> Mapping[str, Mapping[int, str]]:
        return OrderedDict(
            [
                ("logits_per_image", {0: "batch"}),
                ("logits_per_text", {0: "batch"}),
                ("text_embeds", {0: "batch"}),
                ("image_embeds", {0: "batch"}),
            ]
        )

    @property
    def atol_for_validation(self) -> float:
        return 1e-4

    def generate_dummy_inputs(
        self,
        processor: "ProcessorMixin",
        framework: Optional["TensorType"] = None,
    ) -> Mapping[str, Any]:
        text_input_dict = super().generate_dummy_inputs(processor.tokenizer, framework=framework)
        image_input_dict = super().generate_dummy_inputs(processor.feature_extractor, framework=framework)
        return {**text_input_dict, **image_input_dict}

    @property
    def default_onnx_opset(self) -> int:
        return 14

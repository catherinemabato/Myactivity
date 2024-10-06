# coding=utf-8
# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
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
"""SAM2 model configuration"""

from ...configuration_utils import PretrainedConfig
from ...utils import logging


logger = logging.get_logger(__name__)


class Sam2MemoryAttentionConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2MemoryAttention`]. It is used to instantiate a SAM 2
    memory attention module according to the specified arguments, defining the model architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        d_model (`int`, *optional*, defaults to 256):
            The dimension of the model in the memory attention module.
        pos_enc_at_input (`bool`, *optional*, defaults to True):
            Whether to apply positional encoding at the input.
        num_layers (`int`, *optional*, defaults to 4):
            The number of layers in the memory attention module.
        batch_first (`bool`, *optional*, defaults to True):
            Whether the input and output tensors are provided in batch-first format.

    """

    def __init__(
        self,
        d_model=256,
        pos_enc_at_input=True,
        num_layers=4,
        batch_first=True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.d_model = d_model
        self.pos_enc_at_input = pos_enc_at_input
        self.num_layers = num_layers
        self.batch_first = batch_first


class Sam2MemoryEncoderConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2MemoryEncoder`]. It is used to instantiate a SAM 2
    memory encoder according to the specified arguments, defining the model architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        in_dim (`int`, *optional*, defaults to 256):
            Input dimension of the memory encoder.
        out_dim (`int`, *optional*, defaults to 64):
            Output dimension of the memory encoder.

    """

    def __init__(
        self,
        in_dim=256,
        out_dim=64,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.in_dim = in_dim
        self.out_dim = out_dim


class Sam2ImageEncoderConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2ImageEncoder`]. It is used to instantiate a SAM
    image encoder according to the specified arguments, defining the model architecture. Instantiating a configuration
    defaults will yield a similar configuration to that of the SAM 2 Hiera-B+
    [facebook/sam2-hiera-base-plus](https://huggingface.co/facebook/sam2-hiera-base-plus) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        scalp (`int`, *optional*, defaults to 1):
            The scalp parameter for the image encoder.
        embed_dim (`int`, *optional*, defaults to 112):
            Initial embedding dimension.
        num_heads (`int`, *optional*, defaults to 2):
            Initial number of attention heads.
        drop_path_rate (`float`, *optional*, defaults to 0.0):
            Stochastic depth rate.
        q_pool (`int`, *optional*, defaults to 3):
            Number of q_pool stages.
        q_stride (`Tuple[int, int]`, *optional*, defaults to (2, 2)):
            Downsample stride between stages.
        stages (`Tuple[int, ...]`, *optional*, defaults to (2, 3, 16, 3)):
            Number of blocks per stage.
        dim_mul (`float`, *optional*, defaults to 2.0):
            Dimension multiplier factor at stage shift.
        head_mul (`float`, *optional*, defaults to 2.0):
            Head multiplier factor at stage shift.
        window_pos_embed_bkg_spatial_size (`Tuple[int, int]`, *optional*, defaults to (14, 14)):
            Window size per stage when not using global attention.
        window_spec (`Tuple[int, ...]`, *optional*, defaults to (8, 4, 14, 7)):
            Window specifications for each stage.
        global_att_blocks (`Tuple[int, ...]`, *optional*, defaults to (12, 16, 20)):
            Blocks where global attention is used.
        return_interm_layers (`bool`, *optional*, defaults to True):
            Whether to return features from every stage.
        d_model (`int`, *optional*, defaults to 256):
            Dimension of the model in the neck.
        backbone_channel_list (`List[int]`, *optional*, defaults to [896, 448, 224, 112]):
            List of channel dimensions for the backbone.
        kernel_size (`int`, *optional*, defaults to 1):
            Kernel size for convolutions in the neck.
        stride (`int`, *optional*, defaults to 1):
            Stride for convolutions in the neck.
        padding (`int`, *optional*, defaults to 0):
            Padding for convolutions in the neck.
        fpn_top_down_levels (`List[int]`, *optional*, defaults to [2, 3]):
            Levels for top-down FPN connections.
        fpn_interp_model (`str`, *optional*, defaults to "nearest"):
            Interpolation model for FPN.
        fuse_type (`str`, *optional*, defaults to "sum"):
            Type of fusion to use in the neck.

    """

    def __init__(
        self,
        scalp=1,
        embed_dim=112,
        num_heads=2,
        drop_path_rate=0.0,
        q_pool=3,
        q_stride=(2, 2),
        stages=(2, 3, 16, 3),
        dim_mul=2.0,
        head_mul=2.0,
        window_pos_embed_bkg_spatial_size=(14, 14),
        window_spec=(8, 4, 14, 7),
        global_att_blocks=(12, 16, 20),
        return_interm_layers=True,
        d_model=256,
        backbone_channel_list=[896, 448, 224, 112],
        kernel_size=1,
        stride=1,
        padding=0,
        fpn_top_down_levels=[2, 3],
        fpn_interp_model="nearest",
        fuse_type="sum",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.scalp = scalp
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.drop_path_rate = drop_path_rate
        self.q_pool = q_pool
        self.q_stride = q_stride
        self.stages = stages
        self.dim_mul = dim_mul
        self.head_mul = head_mul
        self.window_pos_embed_bkg_spatial_size = window_pos_embed_bkg_spatial_size
        self.window_spec = window_spec
        self.global_att_blocks = global_att_blocks
        self.return_interm_layers = return_interm_layers

        # Neck
        self.d_model = d_model
        self.backbone_channel_list = backbone_channel_list
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.fpn_top_down_levels = fpn_top_down_levels
        self.fpn_interp_model = fpn_interp_model
        self.fuse_type = fuse_type


class Sam2Config(PretrainedConfig):
    r"""
    [`Sam2Config`] is the configuration class to store the configuration of a [`Sam2Model`]. It is used to instantiate a
    SAM2 model according to the specified arguments, defining the memory attention, memory encoder, and image encoder
    configs. Instantiating a configuration defaults will yield a similar configuration to that of the SAM 2 Hiera-B+
    [facebook/sam2-hiera-base-plus](https://huggingface.co/facebook/sam2-hiera-base-plus) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        image_encoder_config (Union[`dict`, `Sam2ImageEncoderConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2ImageEncoderConfig`].
        memory_attention_config (Union[`dict`, `Sam2MemoryAttentionConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2MemoryAttentionConfig`].
        memory_encoder_config (Union[`dict`, `Sam2MemoryEncoderConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2MemoryEncoderConfig`].

        initializer_range (`float`, *optional*, defaults to 0.02): std for parameter initialization
        kwargs (*optional*):
            Dictionary of keyword arguments.

    Example:

    ```python
    >>> from transformers import (
    ...     Sam2ImageEncoderConfig,
    ...     Sam2MemoryAttentionConfig,
    ...     Sam2MemoryEncoderConfig,
    ...     Sam2Model,
    ... )

    >>> # Initializing a Sam2Config with `"facebook/hiera-base-plus"` style configuration
    >>> configuration = Sam2config()

    >>> # Initializing a Sam2Model (with random weights) from the `"facebook/sam-vit-huge"` style configuration
    >>> model = Sam2Model(configuration)

    >>> # Accessing the model configuration
    >>> configuration = model.config

    >>> # We can also initialize a Sam2Config from a Sam2ImageEncoderConfig, Sam2MemoryAttentionConfig, and Sam2MemoryEncoderConfig

    >>> # Initializing SAM2 image encoder, memory attention, and memory encoder configurations
    >>> image_encoder_config = Sam2ImageEncoderConfig()
    >>> memory_attention_config = Sam2MemoryAttentionConfig()
    >>> memory_encoder_config = Sam2MemoryEncoderConfig()

    >>> config = Sam2Config(image_encoder_config, memory_attention_config, memory_encoder_config)
    ```"""

    model_type = "sam2"

    def __init__(
        self,
        image_encoder_config=None,
        memory_attention_config=None,
        memory_encoder_config=None,
        initializer_range=0.02,
        **kwargs,
    ):
        super().__init__(**kwargs)
        image_encoder_config = image_encoder_config if image_encoder_config is not None else {}
        memory_attention_config = memory_attention_config if memory_attention_config is not None else {}
        memory_encoder_config = memory_encoder_config if memory_encoder_config is not None else {}

        self.image_encoder_config = Sam2ImageEncoderConfig(**image_encoder_config)
        self.memory_attention_config = Sam2MemoryAttentionConfig(**memory_attention_config)
        self.memory_encoder_config = Sam2MemoryEncoderConfig(**memory_encoder_config)
        self.initializer_range = initializer_range
        self.num_maskmem = 7  # default 1 input frame + 6 previous frames
        self.image_size = 1024
        self.backbone_stride = 16  # stride of the image backbone output
        self.sigmoid_scale_for_mem_enc = 20  # scale factor for mask sigmoid prob
        self.sigmoid_bias_for_mem_enc = -10  # bias factor for mask sigmoid prob
        # During evaluation whether to binarize the sigmoid mask logits on interacted frames with clicks
        self.binarize_mask_from_pts_for_mem_enc = False
        self.use_mask_input_as_output_without_sam = True  # on frames with mask input whether to directly output the input mask without using a SAM prompt encoder + mask decoder
        # The maximum number of conditioning frames to participate in the memory attention (-1 means no limit; if there are more conditioning frames than this limit
        # we only cross-attend to the temporally closest `max_cond_frames_in_attn` conditioning frames in the encoder when tracking each frame). This gives the model
        # a temporal locality when handling a large number of annotated frames (since closer frames should be more important) and also avoids GPU OOM.
        self.max_cond_frames_in_attn = -1
        # on the first frame whether to directly add the no-memory embedding to the image feature
        # (instead of using the transformer encoder)
        self.directly_add_no_mem_embed = True
        # whether to use high-resolution feature maps in the SAM mask decoder
        self.use_high_res_features_in_sam = True
        # whether to output multiple (3) masks for the first click on initial conditioning frames
        self.multimask_output_in_sam = True
        # the minimum and maximum number of clicks to use multimask_output_in_sam (only relevant when `multimask_output_in_sam=True`;
        # default is 1 for both meaning that only the first click gives multimask output; also note that a box counts as two points)
        self.multimask_min_pt_num = 0
        self.multimask_max_pt_num = 1
        # whether to also use multimask output for tracking (not just for the first click on initial conditioning frames; only relevant when `multimask_output_in_sam=True`)
        self.multimask_output_for_tracking = True
        # Whether to use multimask tokens for obj ptr; Only relevant when both
        # use_obj_ptrs_in_encoder=True and multimask_output_for_tracking=True
        self.use_multimask_token_for_obj_ptr = True
        # whether to use sigmoid to restrict ious prediction to [0-1]
        self.iou_prediction_use_sigmoid = True
        # The memory bank's temporal stride during evaluation (i.e. the `r` parameter in XMem and Cutie; XMem and Cutie use r=5).
        # For r>1 the (self.num_maskmem - 1) non-conditioning memory frames consist of
        # (self.num_maskmem - 2) nearest frames from every r-th frames plus the last frame.
        self.memory_temporal_stride_for_eval = 1
        # if `add_all_frames_to_correct_as_cond` is True we also append to the conditioning frame list any frame that receives a later correction click
        # if `add_all_frames_to_correct_as_cond` is False we conditioning frame list to only use those initial conditioning frames
        self.add_all_frames_to_correct_as_cond = False
        # whether to apply non-overlapping constraints on the object masks in the memory encoder during evaluation (to avoid/alleviate superposing masks)
        self.non_overlap_masks_for_mem_enc = False
        # whether to cross-attend to object pointers from other frames (based on SAM output tokens) in the encoder
        self.use_obj_ptrs_in_encoder = True
        # the maximum number of object pointers from other frames in encoder cross attention (only relevant when `use_obj_ptrs_in_encoder=True`)
        self.max_obj_ptrs_in_encoder = 16
        # whether to add temporal positional encoding to the object pointers in the encoder (only relevant when `use_obj_ptrs_in_encoder=True`)
        self.add_tpos_enc_to_obj_ptrs = False
        # whether to add an extra linear projection layer for the temporal positional encoding in the object pointers to avoid potential interference
        # with spatial positional encoding (only relevant when both `use_obj_ptrs_in_encoder=True` and `add_tpos_enc_to_obj_ptrs=True`)
        self.proj_tpos_enc_in_obj_ptrs = False
        # whether to only attend to object pointers in the past (before the current frame) in the encoder during evaluation
        # (only relevant when `use_obj_ptrs_in_encoder=True`; this might avoid pointer information too far in the future to distract the initial tracking)
        self.only_obj_ptrs_in_the_past_for_eval = True
        # Whether to predict if there is an object in the frame
        self.pred_obj_scores = True
        # Whether to use an MLP to predict object scores
        self.pred_obj_scores_mlp = True
        # Only relevant if pred_obj_scores=True and use_obj_ptrs_in_encoder=True;
        # Whether to have a fixed no obj pointer when there is no object present
        # or to use it as an additive embedding with obj_ptr produced by decoder
        self.fixed_no_obj_ptr = True
        # Soft no object i.e. mix in no_obj_ptr softly
        # hope to make recovery easier if there is a mistake and mitigate accumulation of errors
        self.soft_no_obj_ptr = False
        self.use_mlp_for_obj_ptr_proj = True
        # extra arguments used to construct the SAM mask decoder; if not None it should be a dict of kwargs to be passed into `MaskDecoder` class.
        self.sam_mask_decoder_extra_args = None
        self.compile_image_encoder = False

# Copyright 2022 The HuggingFace Team. All rights reserved.
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
from typing import TYPE_CHECKING

from ...file_utils import _LazyModule, is_flax_available, is_tokenizers_available, is_torch_available
from ...utils import OptionalDependencyNotAvailable


_import_structure = {"configuration_gpt_neox": ["GPT_NEOX_PRETRAINED_CONFIG_ARCHIVE_MAP", "GPTNeoXConfig"]}

try:
    if not is_tokenizers_available():
        raise OptionalDependencyNotAvailable()
except OptionalDependencyNotAvailable:
    pass
else:
    _import_structure["tokenization_gpt_neox_fast"] = ["GPTNeoXTokenizerFast"]

try:
    if not is_torch_available():
        raise OptionalDependencyNotAvailable()
except OptionalDependencyNotAvailable:
    pass
else:
    _import_structure["modeling_gpt_neox"] = [
        "GPT_NEOX_PRETRAINED_MODEL_ARCHIVE_LIST",
        "GPTNeoXForCausalLM",
        "GPTNeoXForQuestionAnswering",
        "GPTNeoXForSequenceClassification",
        "GPTNeoXForTokenClassification",
        "GPTNeoXLayer",
        "GPTNeoXModel",
        "GPTNeoXPreTrainedModel",
    ]

try:
    if not is_flax_available():
        raise OptionalDependencyNotAvailable()
except OptionalDependencyNotAvailable:
    pass
else:
    _import_structure["modeling_flax_gpt_neox"] = [
        "FlaxGPTNeoXForCausalLM",
        "FlaxGPTNeoXModel",
        "FlaxGPTNeoXPreTrainedModel",
    ]

if TYPE_CHECKING:
    from .configuration_gpt_neox import GPT_NEOX_PRETRAINED_CONFIG_ARCHIVE_MAP, GPTNeoXConfig

    try:
        if not is_tokenizers_available():
            raise OptionalDependencyNotAvailable()
    except OptionalDependencyNotAvailable:
        pass
    else:
        from .tokenization_gpt_neox_fast import GPTNeoXTokenizerFast

    try:
        if not is_torch_available():
            raise OptionalDependencyNotAvailable()
    except OptionalDependencyNotAvailable:
        pass
    else:
        from .modeling_gpt_neox import (
            GPT_NEOX_PRETRAINED_MODEL_ARCHIVE_LIST,
            GPTNeoXForCausalLM,
            GPTNeoXForQuestionAnswering,
            GPTNeoXForSequenceClassification,
            GPTNeoXForTokenClassification,
            GPTNeoXLayer,
            GPTNeoXModel,
            GPTNeoXPreTrainedModel,
        )


else:
    import sys

    sys.modules[__name__] = _LazyModule(__name__, globals()["__file__"], _import_structure, module_spec=__spec__)

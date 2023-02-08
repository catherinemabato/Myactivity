# flake8: noqa
# There's no way to ignore "F401 '...' imported but unused" warnings in this
# module, but to preserve other warnings. So, don't check this module at all.

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

from ...utils import (
    OptionalDependencyNotAvailable,
    _LazyModule,
    is_flax_available,
    is_tf_available,
    is_torch_available,
)


_import_structure = {
    "configuration_gptsan_japanese": ["GPTSAN_JAPANESE_PRETRAINED_CONFIG_ARCHIVE_MAP", "GPTSANJapaneseConfig"],
    "tokenization_gptsan_japanese": ["GPTSANJapaneseTokenizer"],
}

try:
    if not is_torch_available():
        raise OptionalDependencyNotAvailable()
except OptionalDependencyNotAvailable:
    pass
else:
    _import_structure["modeling_gptsan_japanese"] = [
        "GPTSAN_JAPANESE_PRETRAINED_MODEL_ARCHIVE_LIST",
        "GPTSANJapaneseDenseActDense",
        "GPTSANJapaneseForConditionalGeneration",
        "GPTSANJapaneseModel",
        "GPTSANJapanesePreTrainedModel",
        "GPTSANJapaneseSparseMLP",
        "GPTSANJapaneseTop1Router",
    ]
    _import_structure["tokenization_gptsan_japanese"] = [
        "GPTSANJapaneseTokenizer",
    ]


if TYPE_CHECKING:
    from .configuration_gptsan_japanese import GPTSAN_JAPANESE_PRETRAINED_CONFIG_ARCHIVE_MAP, GPTSANJapaneseConfig
    from .tokenization_gptsan_japanese import GPTSANJapaneseTokenizer

    try:
        if not is_torch_available():
            raise OptionalDependencyNotAvailable()
    except OptionalDependencyNotAvailable:
        pass
    else:
        from .modeling_gptsan_japanese import (
            GPTSAN_JAPANESE_PRETRAINED_MODEL_ARCHIVE_LIST,
            GPTSANJapaneseDenseActDense,
            GPTSANJapaneseForConditionalGeneration,
            GPTSANJapaneseModel,
            GPTSANJapanesePreTrainedModel,
            GPTSANJapaneseSparseMLP,
            GPTSANJapaneseTop1Router,
        )
        from .tokenization_gptsan_japanese import GPTSANJapaneseTokenizer


else:
    import sys

    sys.modules[__name__] = _LazyModule(__name__, globals()["__file__"], _import_structure, module_spec=__spec__)

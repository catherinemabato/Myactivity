# coding=utf-8
# Copyright 2018 The Microsoft Research Asia LayoutLM Team Authors.
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
""" Tokenization class for model LayoutLM."""


import collections
import logging
import os
from typing import List, Optional

from .tokenization_utils import PreTrainedTokenizer
from .tokenization_bert import BertTokenizer


logger = logging.getLogger(__name__)

VOCAB_FILES_NAMES = {"vocab_file": "vocab.txt"}

PRETRAINED_VOCAB_FILES_MAP = {
    "vocab_file": {
        "layoutlm-base-uncased": "https://s3.amazonaws.com/models.huggingface.co/bert/bert-base-uncased-vocab.txt",
        "layoutlm-large-uncased": "https://s3.amazonaws.com/models.huggingface.co/bert/bert-large-uncased-vocab.txt",
    }
}


PRETRAINED_POSITIONAL_EMBEDDINGS_SIZES = {
    "layoutlm-base-uncased": 512,
    "layoutlm-large-uncased": 512,
}


PRETRAINED_INIT_CONFIGURATION = {
    "layoutlm-base-uncased": {"do_lower_case": True},
    "layoutlm-large-uncased": {"do_lower_case": True},
}



class LayoutLMTokenizer(BertTokenizer):
    r"""
    Constructs a LayoutLM tokenizer.

    :class:`~transformers.LayoutLMTokenizer is identical to :class:`~transformers.BertTokenizer` and runs end-to-end
    tokenization: punctuation splitting + wordpiece.

    Refer to superclass :class:`~transformers.BertTokenizer` for usage examples and documentation concerning
    parameters.
    """

    vocab_files_names = VOCAB_FILES_NAMES
    pretrained_vocab_files_map = PRETRAINED_VOCAB_FILES_MAP
    pretrained_init_configuration = PRETRAINED_INIT_CONFIGURATION
    max_model_input_sizes = PRETRAINED_POSITIONAL_EMBEDDINGS_SIZES
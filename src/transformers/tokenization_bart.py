# coding=utf-8
# Copyright 2020 The Facebook AI Research Team Authors and The HuggingFace Inc. team.
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

import logging
from typing import List, Optional

from .tokenization_roberta import RobertaTokenizer, RobertaTokenizerFast
from .tokenization_utils import BatchEncoding
from .tokenization_xlm_roberta import XLMRobertaTokenizer


logger = logging.getLogger(__name__)


# vocab and merges same as roberta
vocab_url = "https://s3.amazonaws.com/models.huggingface.co/bert/roberta-large-vocab.json"
merges_url = "https://s3.amazonaws.com/models.huggingface.co/bert/roberta-large-merges.txt"
_all_bart_models = [
    "facebook/bart-base",
    "facebook/bart-large",
    "facebook/bart-large-mnli",
    "facebook/bart-large-cnn",
    "facebook/bart-large-xsum",
    "yjernite/bart_eli5",
]


class BartTokenizer(RobertaTokenizer):
    # merges and vocab same as Roberta
    max_model_input_sizes = {m: 1024 for m in _all_bart_models}
    pretrained_vocab_files_map = {
        "vocab_file": {m: vocab_url for m in _all_bart_models},
        "merges_file": {m: merges_url for m in _all_bart_models},
    }


class BartTokenizerFast(RobertaTokenizerFast):
    # merges and vocab same as Roberta
    max_model_input_sizes = {m: 1024 for m in _all_bart_models}
    pretrained_vocab_files_map = {
        "vocab_file": {m: vocab_url for m in _all_bart_models},
        "merges_file": {m: merges_url for m in _all_bart_models},
    }


_all_mbart_models = ["facebook/mbart-large-en-ro", "facebook/mbart-large-cc25"]
SPM_URL = "https://s3.amazonaws.com/models.huggingface.co/bert/facebook/mbart-large-en-ro/sentence.bpe.model"


class MBartTokenizer(XLMRobertaTokenizer):
    """
    This inherits from XLMRobertaTokenizer. ``prepare_translation_batch`` should be used to encode inputs.
    Other tokenizer methods like encode do not work properly.
    The tokenization method is <tokens> <eos> <language code>. There is no BOS token.

    Examples::

        >>> from transformers import MBartTokenizer
        >>> tokenizer = MBartTokenizer.from_pretrained('facebook/mbart-large-en-ro')
        >>> example_english_phrase = " UN Chief Says There Is No Military Solution in Syria"
        >>> expected_translation_romanian = "Şeful ONU declară că nu există o soluţie militară în Siria"
        >>> batch: dict = tokenizer.prepare_translation_batch(
        ...     example_english_phrase, src_lang="en_XX", tgt_lang="ro_RO", tgt_texts=expected_translation_romanian
        ... )

    """

    vocab_files_names = {"vocab_file": "sentencepiece.bpe.model"}
    max_model_input_sizes = {m: 1024 for m in _all_mbart_models}
    pretrained_vocab_files_map = {"vocab_file": {m: SPM_URL for m in _all_mbart_models}}
    lang_code_to_id = {  # NOTE(SS): resize embeddings will break this
        "ar_AR": 250001,
        "cs_CZ": 250002,
        "de_DE": 250003,
        "en_XX": 250004,
        "es_XX": 250005,
        "et_EE": 250006,
        "fi_FI": 250007,
        "fr_XX": 250008,
        "gu_IN": 250009,
        "hi_IN": 250010,
        "it_IT": 250011,
        "ja_XX": 250012,
        "kk_KZ": 250013,
        "ko_KR": 250014,
        "lt_LT": 250015,
        "lv_LV": 250016,
        "my_MM": 250017,
        "ne_NP": 250018,
        "nl_XX": 250019,
        "ro_RO": 250020,
        "ru_RU": 250021,
        "si_LK": 250022,
        "tr_TR": 250023,
        "vi_VN": 250024,
        "zh_CN": 250025,
    }
    id_to_lang_code = {v: k for k, v in lang_code_to_id.items()}
    cur_lang_code = lang_code_to_id["en_XX"]
    prefix_tokens = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fairseq_tokens_to_ids.update(self.lang_code_to_id)
        self.fairseq_ids_to_tokens = {v: k for k, v in self.fairseq_tokens_to_ids.items()}
        self._additional_special_tokens = list(self.lang_code_to_id.keys())
        self.reset_special_tokens()

    def reset_special_tokens(self):

        self.prefix_tokens = []
        self.suffix_tokens = [self.eos_token_id, self.cur_lang_code]

    def build_inputs_with_special_tokens(self, token_ids_0, token_ids_1=None) -> List[int]:
        """Build model inputs from a sequence by appending eos_token_id."""

        if token_ids_1 is None:
            return self.prefix_tokens + token_ids_0 + self.suffix_tokens
        # We don't expect to process pairs, but leave the pair logic for API consistency
        return self.prefix_tokens + token_ids_0 + token_ids_1 + self.suffix_tokens

    def get_special_tokens_mask(
        self, token_ids_0: List[int], token_ids_1: Optional[List[int]] = None, already_has_special_tokens: bool = False
    ) -> List[int]:
        """
        Retrieves sequence ids from a token list that has no special tokens added. This method is called when adding
        special tokens using the tokenizer ``prepare_for_model`` methods.

        Args:
            token_ids_0 (:obj:`List[int]`):
                List of ids.
            token_ids_1 (:obj:`List[int]`, `optional`, defaults to :obj:`None`):
                Optional second list of IDs for sequence pairs.
            already_has_special_tokens (:obj:`bool`, `optional`, defaults to :obj:`False`):
                Set to True if the token list is already formatted with special tokens for the model

        Returns:
            :obj:`List[int]`: A list of integers in the range [0, 1]: 1 for a special token, 0 for a sequence token.
        """

        if already_has_special_tokens:
            if token_ids_1 is not None:
                raise ValueError(
                    "You should not supply a second sequence if the provided sequence of "
                    "ids is already formated with special tokens for the model."
                )
            return list(map(lambda x: 1 if x in [self.sep_token_id, self.cls_token_id] else 0, token_ids_0))
        prefix_ones = [1] * len(self.prefix_tokens)
        suffix_ones = [1] * len(self.suffix_tokens)
        if token_ids_1 is None:
            return prefix_ones + ([0] * len(token_ids_0)) + suffix_ones
        return prefix_ones + ([0] * len(token_ids_0)) + ([0] * len(token_ids_1)) + suffix_ones

    def set_lang(self, lang: str) -> None:
        """Set the current language code in order to call tokenizer properly."""
        self.cur_lang_code = self.lang_code_to_id[lang]
        self.prefix_tokens = [self.cur_lang_code]
        self.suffix_tokens = [self.eos_token_id]

    def prepare_translation_batch(
        self,
        src_texts: List[str],
        src_lang: str = "en_XX",
        tgt_texts: Optional[List[str]] = None,
        tgt_lang: str = "ro_RO",
        max_length: Optional[int] = None,
        pad_to_max_length: bool = True,
        return_tensors: str = "pt",
    ) -> BatchEncoding:
        """
        Arguments:
            src_texts: list of src language texts
            src_lang: default en_XX (english)
            tgt_texts: list of tgt language texts
            tgt_lang: default ro_RO (romanian)
            max_length: (None) defer to config (1024 for mbart-large-en-ro)
            pad_to_max_length: (bool)

        Returns:
            dict with keys input_ids, attention_mask, decoder_input_ids, each value is a torch.Tensor.
        """
        if max_length is None:
            max_length = self.max_len
        self.cur_lang_code = self.lang_code_to_id[src_lang]
        model_inputs: BatchEncoding = self.batch_encode_plus(
            src_texts,
            add_special_tokens=True,
            return_tensors=return_tensors,
            max_length=max_length,
            pad_to_max_length=pad_to_max_length,
            truncation=True,
        )
        if tgt_texts is None:
            return model_inputs
        self.set_lang(tgt_lang)
        decoder_inputs: BatchEncoding = self.batch_encode_plus(
            tgt_texts,
            add_special_tokens=True,
            return_tensors=return_tensors,
            max_length=max_length,
            pad_to_max_length=pad_to_max_length,
            truncation=True,
        )
        for k, v in decoder_inputs.items():
            model_inputs[f"decoder_{k}"] = v
        self.cur_lang_code = self.lang_code_to_id[src_lang]
        self.reset_special_tokens()
        return model_inputs

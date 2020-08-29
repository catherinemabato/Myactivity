# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HuggingFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
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
""" Named entity recognition fine-tuning: utilities to work with CoNLL-2003 task. """


import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, TextIO

import nlp

from filelock import FileLock
from transformers import PreTrainedTokenizer, is_tf_available, is_torch_available


logger = logging.getLogger(__name__)


@dataclass
class InputFeatures:
    """
    A single set of features of data.
    Property names are the same names as the corresponding inputs to a model.
    """

    input_ids: List[int]
    attention_mask: List[int]
    token_type_ids: Optional[List[int]] = None
    label_ids: Optional[List[int]] = None


class TokenClassificationTask(ABC):
    def __init__(self, source_column, target_column):
        self.source_column = source_column
        self.target_column = target_column

    def get_target_column(self) -> str:
        return self.target_column

    def get_source_column(self) -> str:
        return self.source_column

    @abstractmethod
    def get_dataset(self, split: nlp.Split) -> nlp.Dataset:
        raise NotImplementedError

    @abstractmethod
    def get_labels(self, path: Optional[str] = None) -> List[str]:
        raise NotImplementedError

    def write_predictions_to_file(self, writer: TextIO, preds_list: List):
        example_id = 0
        dataset = self.get_dataset(split=nlp.Split.TEST)
        for entry in dataset:
            s_p = preds_list[example_id]
            out = ""
            for source, target in zip(entry[self.get_source_column()], entry[self.get_target_column()]):
                out += f"{source} ({target}|{s_p.pop(0)}) "
            out += "\n"
            writer.write(out)
            example_id += 1

    def convert_examples_to_features(
        self,
        tokenizer: PreTrainedTokenizer,
        max_seq_length: int,
        split: nlp.Split,
        pad_token_label_id=-100,
        sep_token_extra=False,
        cls_token_segment_id=0,
        sequence_a_segment_id=0,
        cls_token_at_end=False,
        mask_padding_with_zero=True,
    ) -> List[InputFeatures]:
        """Loads a data file into a list of `InputFeatures`
        `cls_token_at_end` define the location of the CLS token:
            - False (Default, BERT/XLM pattern): [CLS] + A + [SEP] + B + [SEP]
            - True (XLNet/GPT pattern): A + [SEP] + B + [SEP] + [CLS]
        `cls_token_segment_id` define the segment id associated to the CLS token (0 for BERT, 2 for XLNet)
        """
        # TODO clean up all this to leverage built-in features of tokenizers

        label_map = {label: i for i, label in enumerate(self.get_labels())}

        pad_left = bool(tokenizer.padding_side == "left")
        pad_token_segment_id = tokenizer.pad_token_type_id

        features = []
        dataset: nlp.Dataset = self.get_dataset(split)
        for (ex_index, example) in enumerate(dataset):
            if ex_index % 10_000 == 0:
                logger.info("Writing example %d of %d", ex_index, len(dataset))

            tokens = []
            label_ids = []
            words = example[self.get_source_column()]
            labels = example[self.get_target_column()]
            for word, label in zip(words, labels):
                word_tokens = tokenizer.tokenize(word)

                # bert-base-multilingual-cased sometimes output "nothing ([]) when calling tokenize with just a space.
                if len(word_tokens) > 0:
                    tokens.extend(word_tokens)
                    # Use the real label id for the first token of the word, and padding ids for the remaining tokens
                    label_ids.extend([label_map[label]] + [pad_token_label_id] * (len(word_tokens) - 1))

            # Account for [CLS] and [SEP] with "- 2" and with "- 3" for RoBERTa.
            special_tokens_count = tokenizer.num_special_tokens_to_add()
            if len(tokens) > max_seq_length - special_tokens_count:
                tokens = tokens[: (max_seq_length - special_tokens_count)]
                label_ids = label_ids[: (max_seq_length - special_tokens_count)]

            # The convention in BERT is:
            # (a) For sequence pairs:
            #  tokens:   [CLS] is this jack ##son ##ville ? [SEP] no it is not . [SEP]
            #  type_ids:   0   0  0    0    0     0       0   0   1  1  1  1   1   1
            # (b) For single sequences:
            #  tokens:   [CLS] the dog is hairy . [SEP]
            #  type_ids:   0   0   0   0  0     0   0
            #
            # Where "type_ids" are used to indicate whether this is the first
            # sequence or the second sequence. The embedding vectors for `type=0` and
            # `type=1` were learned during pre-training and are added to the wordpiece
            # embedding vector (and position vector). This is not *strictly* necessary
            # since the [SEP] token unambiguously separates the sequences, but it makes
            # it easier for the model to learn the concept of sequences.
            #
            # For classification tasks, the first vector (corresponding to [CLS]) is
            # used as as the "sentence vector". Note that this only makes sense because
            # the entire model is fine-tuned.
            tokens += [tokenizer.sep_token_id]
            label_ids += [pad_token_label_id]
            if sep_token_extra:
                # roberta uses an extra separator b/w pairs of sentences
                tokens += [tokenizer.sep_token_id]
                label_ids += [pad_token_label_id]
            segment_ids = [sequence_a_segment_id] * len(tokens)

            if cls_token_at_end:
                tokens += [tokenizer.cls_token_id]
                label_ids += [pad_token_label_id]
                segment_ids += [cls_token_segment_id]
            else:
                tokens = [tokenizer.cls_token_id] + tokens
                label_ids = [pad_token_label_id] + label_ids
                segment_ids = [cls_token_segment_id] + segment_ids

            input_ids = tokenizer.convert_tokens_to_ids(tokens)

            # The mask has 1 for real tokens and 0 for padding tokens. Only real
            # tokens are attended to.
            input_mask = [1 if mask_padding_with_zero else 0] * len(input_ids)

            # Zero-pad up to the sequence length.
            padding_length = max_seq_length - len(input_ids)
            if pad_left:
                input_ids = ([tokenizer.pad_token_id] * padding_length) + input_ids
                input_mask = ([0 if mask_padding_with_zero else 1] * padding_length) + input_mask
                segment_ids = ([pad_token_segment_id] * padding_length) + segment_ids
                label_ids = ([pad_token_label_id] * padding_length) + label_ids
            else:
                input_ids += [tokenizer.pad_token_id] * padding_length
                input_mask += [0 if mask_padding_with_zero else 1] * padding_length
                segment_ids += [pad_token_segment_id] * padding_length
                label_ids += [pad_token_label_id] * padding_length

            assert len(input_ids) == max_seq_length
            assert len(input_mask) == max_seq_length
            assert len(segment_ids) == max_seq_length
            assert len(label_ids) == max_seq_length

            if ex_index < 5:
                logger.info("*** Example ***")
                logger.info("guid: %s", ex_index)
                logger.info("tokens: %s", " ".join([str(x) for x in tokens]))
                logger.info("input_ids: %s", " ".join([str(x) for x in input_ids]))
                logger.info("input_mask: %s", " ".join([str(x) for x in input_mask]))
                logger.info("segment_ids: %s", " ".join([str(x) for x in segment_ids]))
                logger.info("label_ids: %s", " ".join([str(x) for x in label_ids]))

            if "token_type_ids" not in tokenizer.model_input_names:
                segment_ids = None

            features.append(
                InputFeatures(
                    input_ids=input_ids, attention_mask=input_mask, token_type_ids=segment_ids, label_ids=label_ids
                )
            )
        return features


if is_torch_available():
    import torch
    from torch import nn
    from torch.utils.data.dataset import Dataset

    class TokenClassificationDataset(Dataset):
        """
        This will be superseded by a framework-agnostic approach
        soon.
        """

        features: List[InputFeatures]
        pad_token_label_id: int = nn.CrossEntropyLoss().ignore_index
        # Use cross entropy ignore_index as padding label id so that only
        # real label ids contribute to the loss later.

        def __init__(
            self,
            token_classification_task: TokenClassificationTask,
            data_dir: str,
            tokenizer: PreTrainedTokenizer,
            model_type,
            max_seq_length: Optional[int] = None,
            overwrite_cache=False,
            split: nlp.Split = nlp.Split.TRAIN,
        ):
            # Load data features from cache or dataset file
            cached_features_file = os.path.join(
                data_dir,
                "cached_{}_{}_{}_{}".format(
                    token_classification_task.__class__.__name__,
                    str(split),
                    tokenizer.__class__.__name__,
                    str(max_seq_length),
                ),
            )

            # Make sure only the first process in distributed training processes the dataset,
            # and the others will use the cache.
            lock_path = cached_features_file + ".lock"
            with FileLock(lock_path):

                if os.path.exists(cached_features_file) and not overwrite_cache:
                    logger.info(f"Loading features from cached file {cached_features_file}")
                    self.features = torch.load(cached_features_file)
                else:
                    logger.info(f"Creating features from dataset file at {data_dir}")
                    self.features = token_classification_task.convert_examples_to_features(
                        tokenizer,
                        max_seq_length,
                        pad_token_label_id=self.pad_token_label_id,
                        cls_token_at_end=bool(model_type in ["xlnet"]),
                        cls_token_segment_id=2 if model_type in ["xlnet"] else 0,
                        split=split,
                    )
                    logger.info(f"Saving features into cached file {cached_features_file}")
                    torch.save(self.features, cached_features_file)

        def __len__(self):
            return len(self.features)

        def __getitem__(self, i) -> InputFeatures:
            return self.features[i]


if is_tf_available():
    import tensorflow as tf

    class TFTokenClassificationDataset:
        """
        This will be superseded by a framework-agnostic approach
        soon.
        """

        features: List[InputFeatures]
        pad_token_label_id: int = -100
        # Use cross entropy ignore_index as padding label id so that only
        # real label ids contribute to the loss later.

        def __init__(
            self,
            token_classification_task: TokenClassificationTask,
            data_dir: str,
            tokenizer: PreTrainedTokenizer,
            labels: List[str],
            model_type: str,
            max_seq_length: Optional[int] = None,
            overwrite_cache=False,
            split: nlp.Split = nlp.Split.TRAIN,
        ):

            self.features = token_classification_task.convert_examples_to_features(
                tokenizer,
                max_seq_length,
                pad_token_label_id=self.pad_token_label_id,
                cls_token_at_end=bool(model_type in ["xlnet"]),
                cls_token_segment_id=2 if model_type in ["xlnet"] else 0,
                split=split,
            )

            def gen():
                for ex in self.features:
                    if ex.token_type_ids is None:
                        yield (
                            {"input_ids": ex.input_ids, "attention_mask": ex.attention_mask},
                            ex.label_ids,
                        )
                    else:
                        yield (
                            {
                                "input_ids": ex.input_ids,
                                "attention_mask": ex.attention_mask,
                                "token_type_ids": ex.token_type_ids,
                            },
                            ex.label_ids,
                        )

            if "token_type_ids" not in tokenizer.model_input_names:
                self.dataset = tf.data.Dataset.from_generator(
                    gen,
                    ({"input_ids": tf.int32, "attention_mask": tf.int32}, tf.int64),
                    (
                        {"input_ids": tf.TensorShape([None]), "attention_mask": tf.TensorShape([None])},
                        tf.TensorShape([None]),
                    ),
                )
            else:
                self.dataset = tf.data.Dataset.from_generator(
                    gen,
                    ({"input_ids": tf.int32, "attention_mask": tf.int32, "token_type_ids": tf.int32}, tf.int64),
                    (
                        {
                            "input_ids": tf.TensorShape([None]),
                            "attention_mask": tf.TensorShape([None]),
                            "token_type_ids": tf.TensorShape([None]),
                        },
                        tf.TensorShape([None]),
                    ),
                )

        def get_dataset(self):
            self.dataset = self.dataset.apply(tf.data.experimental.assert_cardinality(len(self.features)))

            return self.dataset

        def __len__(self):
            return len(self.features)

        def __getitem__(self, i) -> InputFeatures:
            return self.features[i]

# coding=utf-8
# Copyright 2021 The HuggingFace Inc. team. All rights reserved.
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
""" Testing suite for the PyTorch UniSpeechSat model. """

import unittest

from tests.test_modeling_common import floats_tensor, ids_tensor, random_attention_mask
from transformers import UniSpeechSatConfig, is_torch_available
from transformers.testing_utils import require_datasets, require_soundfile, require_torch, slow, torch_device

from .test_configuration_common import ConfigTester
from .test_modeling_common import ModelTesterMixin, _config_zero_init


if is_torch_available():
    import torch

    from transformers import UniSpeechSatModel, Wav2Vec2FeatureExtractor


@require_torch
@require_datasets
@require_soundfile
@slow
class UniSpeechSatModelIntegrationTest(unittest.TestCase):
    def _load_datasamples(self, num_samples):
        from datasets import load_dataset

        import soundfile as sf

        ids = [f"1272-141231-000{i}" for i in range(num_samples)]

        # map files to raw
        def map_to_array(batch):
            speech, _ = sf.read(batch["file"])
            batch["speech"] = speech
            return batch

        ds = load_dataset("patrickvonplaten/librispeech_asr_dummy", "clean", split="validation")

        ds = ds.filter(lambda x: x["id"] in ids).sort("id").map(map_to_array)

        return ds["speech"][:num_samples]

    def _load_superb(self, task, num_samples):
        from datasets import load_dataset

        ds = load_dataset("anton-l/superb_dummy", task, split="test")

        return ds[:num_samples]

    def test_inference_encoder_base(self):
        model = UniSpeechSatModel.from_pretrained("microsoft/unispeech-sat-base-plus")
        model.to(torch_device)
        feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
            "facebook/wav2vec2-base", return_attention_mask=True
        )
        input_speech = self._load_datasamples(2)

        inputs_dict = feature_extractor(input_speech, return_tensors="pt", padding=True)

        with torch.no_grad():
            outputs = model(
                inputs_dict.input_values.to(torch_device),
                attention_mask=inputs_dict.attention_mask.to(torch_device),
            )

        # fmt: off
        expected_hidden_states_slice = torch.tensor(
            [[[-0.0743, 0.1384],
              [-0.0845, 0.1704]],
             [[-0.0954, 0.1936],
              [-0.1123, 0.2095]]],
            device=torch_device,
        )
        # fmt: on

        self.assertTrue(torch.allclose(outputs.last_hidden_state[:, :2, -2:], expected_hidden_states_slice, atol=1e-3))

    def test_inference_encoder_large(self):
        model = UniSpeechSatModel.from_pretrained("microsoft/unispeech-sat-large")
        model.to(torch_device)
        feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained("facebook/wav2vec2-large-xlsr-53")
        input_speech = self._load_datasamples(2)

        inputs_dict = feature_extractor(input_speech, return_tensors="pt", padding=True)

        with torch.no_grad():
            outputs = model(
                inputs_dict.input_values.to(torch_device),
                attention_mask=inputs_dict.attention_mask.to(torch_device),
            )

        # fmt: off
        expected_hidden_states_slice = torch.tensor(
            [[[-0.1172, -0.0797],
              [-0.0012, 0.0213]],
             [[-0.1225, -0.1277],
              [-0.0668, -0.0585]]],
            device=torch_device,
        )
        # fmt: on

        self.assertTrue(torch.allclose(outputs.last_hidden_state[:, :2, -2:], expected_hidden_states_slice, atol=1e-3))

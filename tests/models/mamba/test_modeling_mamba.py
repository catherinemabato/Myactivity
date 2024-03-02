# coding=utf-8
# Copyright 2024 The HuggingFace Team. All rights reserved.
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


from parameterized import parameterized
import unittest
from unittest.util import safe_repr

from transformers import AutoTokenizer, MambaConfig, is_torch_available
from transformers.testing_utils import require_torch, slow, torch_device, require_torch_multi_gpu

from ...generation.test_utils import GenerationTesterMixin
from ...test_configuration_common import ConfigTester
from ...test_modeling_common import ModelTesterMixin, ids_tensor
from ...test_pipeline_mixin import PipelineTesterMixin


if is_torch_available():
    import torch

    from transformers import (
        MAMBA_PRETRAINED_MODEL_ARCHIVE_LIST,
        MambaForCausalLM,
        MambaModel,
    )
    from transformers.pytorch_utils import is_torch_greater_or_equal_than_2_0
else:
    is_torch_greater_or_equal_than_2_0 = False


class MambaModelTester:
    def __init__(
        self,
        parent,
        batch_size=14,
        seq_length=7,
        is_training=True,
        use_labels=True,
        vocab_size=99,
        hidden_size=32,
        num_hidden_layers=2,
        intermediate_size=32,
        hidden_act="silu",
        hidden_dropout_prob=0.1,
        max_position_embeddings=512,
        type_vocab_size=16,
        type_sequence_label_size=2,
        num_labels=3,
        num_choices=4,
        scope=None,
        tie_word_embeddings=True,
    ):
        self.parent = parent
        self.batch_size = batch_size
        self.seq_length = seq_length
        self.is_training = is_training
        self.use_labels = use_labels
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_hidden_layers = num_hidden_layers
        self.intermediate_size = intermediate_size
        self.hidden_act = hidden_act
        self.hidden_dropout_prob = hidden_dropout_prob
        self.max_position_embeddings = max_position_embeddings
        self.type_vocab_size = type_vocab_size
        self.type_sequence_label_size = type_sequence_label_size
        self.num_labels = num_labels
        self.num_choices = num_choices
        self.scope = scope
        self.bos_token_id = vocab_size - 1
        self.eos_token_id = vocab_size - 1
        self.pad_token_id = vocab_size - 1
        self.tie_word_embeddings = tie_word_embeddings

    def get_large_model_config(self):
        return MambaConfig.from_pretrained("ArthurZ/mamba-130m")

    def prepare_config_and_inputs(
        self, gradient_checkpointing=False, scale_attn_by_inverse_layer_idx=False, reorder_and_upcast_attn=False
    ):
        input_ids = ids_tensor([self.batch_size, self.seq_length], self.vocab_size)

        sequence_labels = None
        token_labels = None
        choice_labels = None
        if self.use_labels:
            sequence_labels = ids_tensor([self.batch_size], self.type_sequence_label_size)
            token_labels = ids_tensor([self.batch_size, self.seq_length], self.num_labels)
            choice_labels = ids_tensor([self.batch_size], self.num_choices)

        config = self.get_config(
            gradient_checkpointing=gradient_checkpointing,
            scale_attn_by_inverse_layer_idx=scale_attn_by_inverse_layer_idx,
            reorder_and_upcast_attn=reorder_and_upcast_attn,
        )

        return (
            config,
            input_ids,
            None,
            sequence_labels,
            token_labels,
            choice_labels,
        )

    def get_config(
        self, gradient_checkpointing=False, scale_attn_by_inverse_layer_idx=False, reorder_and_upcast_attn=False
    ):
        return MambaConfig(
            vocab_size=self.vocab_size,
            hidden_size=self.hidden_size,
            num_hidden_layers=self.num_hidden_layers,
            intermediate_size=self.intermediate_size,
            activation_function=self.hidden_act,
            n_positions=self.max_position_embeddings,
            type_vocab_size=self.type_vocab_size,
            use_cache=True,
            bos_token_id=self.bos_token_id,
            eos_token_id=self.eos_token_id,
            pad_token_id=self.pad_token_id,
            gradient_checkpointing=gradient_checkpointing,
            tie_word_embeddings=self.tie_word_embeddings,
        )

    def get_pipeline_config(self):
        config = self.get_config()
        config.vocab_size = 300
        return config

    def prepare_config_and_inputs_for_decoder(self):
        (
            config,
            input_ids,
            sequence_labels,
            token_labels,
            choice_labels,
        ) = self.prepare_config_and_inputs()

        return (
            config,
            input_ids,
            sequence_labels,
            token_labels,
            choice_labels,
        )

    def create_and_check_mamba_model(self, config, input_ids, *args):
        config.output_hidden_states = True
        model = MambaModel(config=config)
        model.to(torch_device)
        model.eval()

        result = model(input_ids)

        self.parent.assertEqual(result.last_hidden_state.shape, (self.batch_size, self.seq_length, self.hidden_size))
        self.parent.assertEqual(len(result.hidden_states), config.num_hidden_layers + 1)

    def create_and_check_causl_lm(self, config, input_ids, *args):
        model = MambaForCausalLM(config)
        model.to(torch_device)
        model.eval()

        result = model(input_ids, labels=input_ids)
        self.parent.assertEqual(result.loss.shape, ())
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.vocab_size))

    def create_and_check_state_equivalency(self, config, input_ids, *args):
        model = MambaModel(config=config)
        model.to(torch_device)
        model.eval()

        outputs = model(input_ids)
        output_whole = outputs.last_hidden_state

        outputs = model(input_ids[:, :-1], use_cache=True)
        output_one = outputs.last_hidden_state

        # Using the state computed on the first inputs, we will get the same output
        outputs = model(input_ids[:, -1:], inference_params=outputs.inference_params)
        output_two = outputs.last_hidden_state

        self.parent.assertTrue(torch.allclose(torch.cat([output_one, output_two], dim=1), output_whole, atol=1e-5))
        # TODO the orignal mamba does not support decoding more than 1 token neither do we

    def create_and_check_forward_and_backwards(self, config, input_ids, *args, gradient_checkpointing=False):
        model = MambaForCausalLM(config)
        model.to(torch_device)
        if gradient_checkpointing:
            model.gradient_checkpointing_enable()

        result = model(input_ids, labels=input_ids)
        self.parent.assertEqual(result.loss.shape, ())
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.vocab_size))
        result.loss.backward()

    def prepare_config_and_inputs_for_common(self):
        (
            config,
            input_ids,
            _,
            sequence_labels,
            token_labels,
            choice_labels,
        ) = self.prepare_config_and_inputs()
        inputs_dict = {"input_ids": input_ids}
        return config, inputs_dict


@unittest.skipIf(
    not is_torch_greater_or_equal_than_2_0, reason="See https://github.com/huggingface/transformers/pull/24204"
)
@require_torch
class MambaModelTest(ModelTesterMixin, GenerationTesterMixin, PipelineTesterMixin, unittest.TestCase):
    all_model_classes = (MambaModel, MambaForCausalLM) if is_torch_available() else ()
    fx_compatible = False  # FIXME let's try to support this @ArthurZucker
    test_torchscript = False  # FIXME let's try to support this @ArthurZucker
    test_missing_keys = False
    test_model_parallel = False
    test_pruning = False
    test_head_masking = False  # Mamba does not have attention heads
    test_model_parallel = False
    pipeline_model_mapping = (
        {"feature-extraction": MambaModel, "text-generation": MambaForCausalLM} if is_torch_available() else {}
    )

    def setUp(self):
        self.model_tester = MambaModelTester(self)
        self.config_tester = ConfigTester(
            self, config_class=MambaConfig, n_embd=37, common_properties=["hidden_size", "num_hidden_layers"]
        )

    def assertInterval(self, member, container, msg=None):
        r"""
        Simple utility function to check if a member is inside an interval.
        """
        if isinstance(member, torch.Tensor):
            max_value, min_value = member.max().item(), member.min().item()
        elif isinstance(member, list) or isinstance(member, tuple):
            max_value, min_value = max(member), min(member)

        if not isinstance(container, list):
            raise TypeError("container should be a list or tuple")
        elif len(container) != 2:
            raise ValueError("container should have 2 elements")

        expected_min, expected_max = container

        is_inside_interval = (min_value >= expected_min) and (max_value <= expected_max)

        if not is_inside_interval:
            standardMsg = "%s not found in %s" % (safe_repr(member), safe_repr(container))
            self.fail(self._formatMessage(msg, standardMsg))

    def test_config(self):
        self.config_tester.run_common_tests()

    @unittest.skip("No attention in mamba")
    def test_retain_grad_hidden_states_attentions(self):
        pass

    @require_torch_multi_gpu
    def test_multi_gpu_data_parallel_forward(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        # some params shouldn't be scattered by nn.DataParallel
        # so just remove them if they are present.
        blacklist_non_batched_params = ["head_mask", "decoder_head_mask", "cross_attn_head_mask"]
        for k in blacklist_non_batched_params:
            inputs_dict.pop(k, None)

        # move input tensors to cuda:O
        for k, v in inputs_dict.items():
            if torch.is_tensor(v):
                inputs_dict[k] = v.to(0)

        for model_class in self.all_model_classes:
            model = model_class(config=config)
            model.to(0)
            model.eval()

            # Wrap model in nn.DataParallel
            model = torch.nn.DataParallel(model)
            with torch.no_grad():
                _ = model(**self._prepare_for_class(inputs_dict, model_class))

    def test_mamba_model(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_mamba_model(*config_and_inputs)

    def test_mamba_lm_head_model(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_causl_lm(*config_and_inputs)

    def test_state_equivalency(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_state_equivalency(*config_and_inputs)

    def test_initialization(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config=config)
            for name, param in model.named_parameters():
                if "A" in name:
                    if param.requires_grad:
                        self.assertTrue(param.data.max().item() == 3.0)
                        self.assertTrue(param.data.min().item() == -5.0)
                elif "B" in name:
                    if param.requires_grad:
                        # check if it's a ones like
                        self.assertTrue(torch.allclose(param.data, torch.ones_like(param.data), atol=1e-5, rtol=1e-5))

        # TODO handle initialization scheme!

    @unittest.skip("Mamba does not use attention equivalent test should be `test_ssm_outputs`")
    def test_attention_outputs(self):
        r"""
        Overriding the test_attention_outputs test as the attention outputs of Mamba are different from other models
        it has a shape `batch_size, seq_len, hidden_size`.
        """
        pass

    def test_ssm_outputs(self):
        pass

    @slow
    def test_model_from_pretrained(self):
        for model_name in MAMBA_PRETRAINED_MODEL_ARCHIVE_LIST[:1]:
            model = MambaModel.from_pretrained(model_name)
            self.assertIsNotNone(model)


@require_torch
class MambaIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.model_id = "ArthurZ/mamba-2.8b"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)

    @parameterized.expand([(torch_device,), ("cpu",)])
    def test_simple_generate(self, device):
        tokenizer = AutoTokenizer.from_pretrained("ArthurZ/mamba-130m")
        tokenizer.pad_token = tokenizer.eos_token

        model = MambaForCausalLM.from_pretrained("ArthurZ/mamba-130m", torch_dtype=torch.float16)
        model.to(device)
        model.config.use_cache = True
        input_ids = tokenizer("Hey how are you doing?", return_tensors="pt")["input_ids"].to(device)

        with torch.no_grad():
            logits = model(input_ids=input_ids).logits

        EXPECTED_LOGITS_NO_GRAD = torch.tensor(
            [
                -55.6875, -69.8750, -49.9062, -51.7500, -57.6875, -57.9375, -56.9688,
                -57.9375, -54.6875, -55.9375, -55.3125, -58.0938, -60.5625, -47.0000,
                -52.0312, -49.7812, -55.9375, -57.9062, -56.7812, -57.1250, -57.3438,
                -58.3125, -57.8125, -58.7812, -59.6250, -59.0938, -58.7188, -52.9375,
                -53.4688, -57.3750, -56.9375, -55.7500, -53.3125, -55.8438, -57.0000,
                -56.9062, -56.2188, -54.7188, -56.4375, -57.5000
            ]
        ,dtype=torch.float32)  # fmt: skip

        torch.testing.assert_close(logits[0, 0, :40].cpu(), EXPECTED_LOGITS_NO_GRAD)

        out = model.generate(input_ids, do_sample=False, max_new_tokens=10)
        output_sentence = tokenizer.decode(out[0, :])
        self.assertEqual(output_sentence, "Hey how are you doing?\n\nI'm so glad you're here.")

    @parameterized.expand([(torch_device,), ("cpu",)])
    def test_simple_generate_cuda_kernels_tiny(self, device):
        expected_output = "Hello my name is John and I am a newbie to the world"

        input_ids = self.tokenizer("Hello my name is", return_tensors="pt").input_ids.to(device)
        model = MambaForCausalLM.from_pretrained("ArthurZ/mamba-130m", torch_dtype=torch.float16).to(device)

        output = model.generate(input_ids, max_new_tokens=10)
        output_sentence = self.tokenizer.decode(output[0].tolist())

        self.assertEqual(output_sentence, expected_output)

    @parameterized.expand([(torch_device,), ("cpu",)])
    @slow
    def test_simple_generate_cuda_kernels_small(self, device):
        expected_output = "Hello my name is\n\nI am a\n\nI am a"

        input_ids = self.tokenizer("Hello my name is", return_tensors="pt").input_ids.to(device)
        model = MambaForCausalLM.from_pretrained("ArthurZ/mamba-790m", torch_dtype=torch.float16).to(device)

        output = model.generate(input_ids, max_new_tokens=10)
        output_sentence = self.tokenizer.decode(output[0].tolist())

        self.assertEqual(output_sentence, expected_output)

    @parameterized.expand([(torch_device,), ("cpu",)])
    @slow
    def test_simple_generate_cuda_kernels_mid(self, device):
        expected_output = "Hello my name is John and I am a\n\nI am a"

        input_ids = self.tokenizer("Hello my name is", return_tensors="pt").input_ids.to(device)
        model = MambaForCausalLM.from_pretrained("ArthurZ/mamba-1.4b", torch_dtype=torch.float16).to(device)

        output = model.generate(input_ids, max_new_tokens=10)
        output_sentence = self.tokenizer.decode(output[0].tolist())

        self.assertEqual(output_sentence, expected_output)

    @parameterized.expand([(torch_device,), ("cpu",)])
    @slow
    def test_simple_generate_cuda_kernels_big(self, device):
        expected_output = "Hello my name is John and I am a new member of this forum"

        input_ids = self.tokenizer("Hello my name is", return_tensors="pt").input_ids.to(device)
        model = MambaForCausalLM.from_pretrained("ArthurZ/mamba-2.8b", torch_dtype=torch.float16).to(device)

        output = model.generate(input_ids, max_new_tokens=10)
        output_sentence = self.tokenizer.decode(output[0].tolist())

        self.assertEqual(output_sentence, expected_output)

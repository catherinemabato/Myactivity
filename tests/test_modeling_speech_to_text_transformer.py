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
""" Testing suite for the PyTorch Speech2TextTransformer model. """


import copy
import inspect
import tempfile
import unittest

from transformers import is_torch_available
from transformers.file_utils import cached_property
from transformers.testing_utils import require_sentencepiece, require_tokenizers, require_torch, slow, torch_device

from .test_configuration_common import ConfigTester
from .test_generation_utils import GenerationTesterMixin
from .test_modeling_common import ModelTesterMixin, floats_tensor, ids_tensor, random_attention_mask


if is_torch_available():
    import torch

    from transformers import (
        Speech2TextConfig,
        Speech2TextTokenizer,
        Speech2TextTransformerForConditionalGeneration,
        Speech2TextTransformerModel,
    )
    from transformers.models.speech_to_text_transformer.modeling_speech_to_text_transformer import (
        Speech2TextTransformerDecoder,
        Speech2TextTransformerEncoder,
    )


def prepare_speech_to_text_transformer_inputs_dict(
    config,
    input_features,
    decoder_input_ids,
    attention_mask=None,
    decoder_attention_mask=None,
):
    if attention_mask is None:
        attention_mask = input_features.ne(0)
    if decoder_attention_mask is None:
        decoder_attention_mask = decoder_input_ids.ne(config.pad_token_id)
    return {
        # "input_ids": input_features,
        "input_features": input_features,
        "decoder_input_ids": decoder_input_ids,
        "attention_mask": attention_mask,
        "decoder_attention_mask": attention_mask,
    }


@require_torch
class Speech2TextTransformerModelTester:
    def __init__(
        self,
        parent,
        batch_size=13,
        seq_length=7,
        is_training=True,
        use_labels=False,
        vocab_size=99,
        hidden_size=16,
        num_hidden_layers=2,
        num_attention_heads=4,
        intermediate_size=4,
        num_conv_layers=2,
        conv_kernel_sizes=(5, 5),
        conv_channels=32,
        input_feat_per_channel=24,
        input_channels=1,
        hidden_act="relu",
        hidden_dropout_prob=0.1,
        attention_probs_dropout_prob=0.1,
        max_position_embeddings=20,
        max_source_positions=20,
        max_target_positions=20,
        eos_token_id=2,
        pad_token_id=1,
        bos_token_id=0,
    ):
        self.parent = parent
        self.batch_size = batch_size
        self.seq_length = seq_length
        self.is_training = is_training
        self.use_labels = use_labels
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.intermediate_size = intermediate_size
        self.num_conv_layers = num_conv_layers
        self.conv_kernel_sizes = conv_kernel_sizes
        self.conv_channels = conv_channels
        self.input_feat_per_channel = input_feat_per_channel
        self.input_channels = input_channels
        self.hidden_act = hidden_act
        self.hidden_dropout_prob = hidden_dropout_prob
        self.attention_probs_dropout_prob = attention_probs_dropout_prob
        self.max_position_embeddings = max_position_embeddings
        self.max_source_positions = max_source_positions
        self.max_target_positions = max_target_positions
        self.eos_token_id = eos_token_id
        self.pad_token_id = pad_token_id
        self.bos_token_id = bos_token_id

    def prepare_config_and_inputs(self):
        input_features = floats_tensor(
            [self.batch_size, self.seq_length, self.input_feat_per_channel], self.vocab_size
        )
        attention_mask = ids_tensor([self.batch_size, self.seq_length], 2)
        attention_mask = torch.ones([self.batch_size, self.seq_length], dtype=torch.long, device=torch_device)
        decoder_input_ids = ids_tensor([self.batch_size, self.seq_length], self.vocab_size)

        config = Speech2TextConfig(
            vocab_size=self.vocab_size,
            d_model=self.hidden_size,
            encoder_layers=self.num_hidden_layers,
            decoder_layers=self.num_hidden_layers,
            encoder_attention_heads=self.num_attention_heads,
            decoder_attention_heads=self.num_attention_heads,
            encoder_ffn_dim=self.intermediate_size,
            decoder_ffn_dim=self.intermediate_size,
            num_conv_layers=self.num_conv_layers,
            conv_kernel_sizes=self.conv_kernel_sizes,
            conv_channels=self.conv_channels,
            input_feat_per_channel=self.input_feat_per_channel,
            input_channels=self.input_channels,
            dropout=self.hidden_dropout_prob,
            attention_dropout=self.attention_probs_dropout_prob,
            max_position_embeddings=self.max_position_embeddings,
            max_source_positions=self.max_source_positions,
            max_target_positions=self.max_target_positions,
            eos_token_id=self.eos_token_id,
            bos_token_id=self.bos_token_id,
            pad_token_id=self.pad_token_id,
        )
        inputs_dict = prepare_speech_to_text_transformer_inputs_dict(
            config,
            input_features=input_features,
            decoder_input_ids=decoder_input_ids,
            attention_mask=attention_mask,
        )
        return config, inputs_dict

    def prepare_config_and_inputs_for_common(self):
        config, inputs_dict = self.prepare_config_and_inputs()
        return config, inputs_dict

    def get_subsampled_output_lengths(self, input_lengths: torch.LongTensor):
        """
        Computes the output length of the convolutional layers
        """

        for i in range(self.num_conv_layers):
            input_lengths = (input_lengths - 1) // 2 + 1

        return input_lengths

    def create_and_check_decoder_model_past_large_inputs(self, config, inputs_dict):
        model = Speech2TextTransformerModel(config=config).get_decoder().to(torch_device).eval()
        input_ids = inputs_dict["decoder_input_ids"]
        attention_mask = inputs_dict["decoder_attention_mask"]

        # first forward pass
        outputs = model(input_ids, attention_mask=attention_mask, use_cache=True)

        output, past_key_values = outputs.to_tuple()

        # create hypothetical multiple next token and extent to next_input_ids
        next_tokens = ids_tensor((self.batch_size, 3), config.vocab_size)
        next_attn_mask = ids_tensor((self.batch_size, 3), 2)

        # append to next input_ids and
        next_input_ids = torch.cat([input_ids, next_tokens], dim=-1)
        next_attention_mask = torch.cat([attention_mask, next_attn_mask], dim=-1)

        output_from_no_past = model(next_input_ids, attention_mask=next_attention_mask)["last_hidden_state"]
        output_from_past = model(next_tokens, attention_mask=next_attention_mask, past_key_values=past_key_values)[
            "last_hidden_state"
        ]

        # select random slice
        random_slice_idx = ids_tensor((1,), output_from_past.shape[-1]).item()
        output_from_no_past_slice = output_from_no_past[:, -3:, random_slice_idx].detach()
        output_from_past_slice = output_from_past[:, :, random_slice_idx].detach()

        self.parent.assertTrue(output_from_past_slice.shape[1] == next_tokens.shape[1])

        # test that outputs are equal for slice
        self.parent.assertTrue(torch.allclose(output_from_past_slice, output_from_no_past_slice, atol=1e-2))

    def check_encoder_decoder_model_standalone(self, config, inputs_dict):
        model = Speech2TextTransformerModel(config=config).to(torch_device).eval()
        outputs = model(**inputs_dict)

        encoder_last_hidden_state = outputs.encoder_last_hidden_state
        last_hidden_state = outputs.last_hidden_state

        with tempfile.TemporaryDirectory() as tmpdirname:
            encoder = model.get_encoder()
            encoder.save_pretrained(tmpdirname)
            encoder = Speech2TextTransformerEncoder.from_pretrained(tmpdirname).to(torch_device)

        encoder_last_hidden_state_2 = encoder(
            inputs_dict["input_features"], attention_mask=inputs_dict["attention_mask"]
        )[0]

        self.parent.assertTrue((encoder_last_hidden_state_2 - encoder_last_hidden_state).abs().max().item() < 1e-3)

        with tempfile.TemporaryDirectory() as tmpdirname:
            decoder = model.get_decoder()
            decoder.save_pretrained(tmpdirname)
            decoder = Speech2TextTransformerDecoder.from_pretrained(tmpdirname).to(torch_device)

        last_hidden_state_2 = decoder(
            input_ids=inputs_dict["decoder_input_ids"],
            attention_mask=inputs_dict["decoder_attention_mask"],
            encoder_hidden_states=encoder_last_hidden_state,
            encoder_attention_mask=inputs_dict["attention_mask"],
        )[0]

        self.parent.assertTrue((last_hidden_state_2 - last_hidden_state).abs().max().item() < 1e-3)


@require_torch
class Speech2TextTransformerModelTest(ModelTesterMixin, GenerationTesterMixin, unittest.TestCase):
    all_model_classes = (
        (Speech2TextTransformerModel, Speech2TextTransformerForConditionalGeneration) if is_torch_available() else ()
    )
    all_generative_model_classes = (Speech2TextTransformerForConditionalGeneration,) if is_torch_available() else ()
    is_encoder_decoder = True
    test_pruning = False
    test_head_masking = False
    test_missing_keys = False
    test_torchscript = False

    input_name = "input_features"

    def setUp(self):
        self.model_tester = Speech2TextTransformerModelTester(self)
        self.config_tester = ConfigTester(self, config_class=Speech2TextConfig)
        self.maxDiff = 3000

    def test_config(self):
        self.config_tester.run_common_tests()

    def test_save_load_strict(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs()
        for model_class in self.all_model_classes:
            model = model_class(config)

            with tempfile.TemporaryDirectory() as tmpdirname:
                model.save_pretrained(tmpdirname)
                model2, info = model_class.from_pretrained(tmpdirname, output_loading_info=True)
            self.assertEqual(info["missing_keys"], [])

    def test_decoder_model_past_with_large_inputs(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_decoder_model_past_large_inputs(*config_and_inputs)

    def test_encoder_decoder_model_standalone(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs_for_common()
        self.model_tester.check_encoder_decoder_model_standalone(*config_and_inputs)

    def test_inputs_embeds(self):
        pass

    def test_generate_fp16(self):
        config, input_dict = self.model_tester.prepare_config_and_inputs()
        input_ids = input_dict["input_features"]
        attention_mask = input_dict["attention_mask"]
        model = Speech2TextTransformerForConditionalGeneration(config).eval().to(torch_device)
        if torch_device == "cuda":
            model.half()
        model.generate(input_ids, attention_mask=attention_mask)
        model.generate(input_ids, num_beams=4, do_sample=True, early_stopping=False, num_return_sequences=3)

    def test_forward_signature(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)
            signature = inspect.signature(model.forward)
            # signature.parameters is an OrderedDict => so arg_names order is deterministic
            arg_names = [*signature.parameters.keys()]

            expected_arg_names = [
                "input_features",
                "attention_mask",
                "decoder_input_ids",
                "decoder_attention_mask",
            ]
            expected_arg_names.extend(
                ["head_mask", "decoder_head_mask", "encoder_outputs"]
                if "head_mask" and "decoder_head_mask" in arg_names
                else ["encoder_outputs"]
            )
            self.assertListEqual(arg_names[: len(expected_arg_names)], expected_arg_names)

    def test_hidden_states_output(self):
        def check_hidden_states_output(inputs_dict, config, model_class):
            model = model_class(config)
            model.to(torch_device)
            model.eval()

            with torch.no_grad():
                outputs = model(**self._prepare_for_class(inputs_dict, model_class))

            hidden_states = outputs.encoder_hidden_states if config.is_encoder_decoder else outputs.hidden_states

            expected_num_layers = getattr(
                self.model_tester, "expected_num_hidden_layers", self.model_tester.num_hidden_layers + 1
            )
            self.assertEqual(len(hidden_states), expected_num_layers)

            if hasattr(self.model_tester, "encoder_seq_length"):
                seq_length = self.model_tester.encoder_seq_length
            else:
                seq_length = self.model_tester.seq_length

            subsampled_seq_length = model._get_subsampled_output_lengths(seq_length)

            self.assertListEqual(
                list(hidden_states[0].shape[-2:]),
                [subsampled_seq_length, self.model_tester.hidden_size],
            )

            if config.is_encoder_decoder:
                hidden_states = outputs.decoder_hidden_states

                self.assertIsInstance(hidden_states, (list, tuple))
                self.assertEqual(len(hidden_states), expected_num_layers)
                seq_len = getattr(self.model_tester, "seq_length", None)
                decoder_seq_length = getattr(self.model_tester, "decoder_seq_length", seq_len)

                self.assertListEqual(
                    list(hidden_states[0].shape[-2:]),
                    [decoder_seq_length, self.model_tester.hidden_size],
                )

        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            inputs_dict["output_hidden_states"] = True
            check_hidden_states_output(inputs_dict, config, model_class)

            # check that output_hidden_states also work using config
            del inputs_dict["output_hidden_states"]
            config.output_hidden_states = True

            check_hidden_states_output(inputs_dict, config, model_class)

    def test_attention_outputs(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()
        config.return_dict = True

        seq_len = getattr(self.model_tester, "seq_length", None)
        decoder_seq_length = getattr(self.model_tester, "decoder_seq_length", seq_len)
        encoder_seq_length = getattr(self.model_tester, "encoder_seq_length", seq_len)
        decoder_key_length = getattr(self.model_tester, "decoder_key_length", decoder_seq_length)
        encoder_key_length = getattr(self.model_tester, "key_length", encoder_seq_length)

        for model_class in self.all_model_classes:
            inputs_dict["output_attentions"] = True
            inputs_dict["output_hidden_states"] = False
            config.return_dict = True
            model = model_class(config)
            model.to(torch_device)
            model.eval()

            subsampled_encoder_seq_length = model._get_subsampled_output_lengths(encoder_seq_length)
            subsampled_encoder_key_length = model._get_subsampled_output_lengths(encoder_key_length)

            with torch.no_grad():
                outputs = model(**self._prepare_for_class(inputs_dict, model_class))
            attentions = outputs.encoder_attentions if config.is_encoder_decoder else outputs.attentions
            self.assertEqual(len(attentions), self.model_tester.num_hidden_layers)

            # check that output_attentions also work using config
            del inputs_dict["output_attentions"]
            config.output_attentions = True
            model = model_class(config)
            model.to(torch_device)
            model.eval()
            with torch.no_grad():
                outputs = model(**self._prepare_for_class(inputs_dict, model_class))
            attentions = outputs.encoder_attentions if config.is_encoder_decoder else outputs.attentions
            self.assertEqual(len(attentions), self.model_tester.num_hidden_layers)

            self.assertListEqual(
                list(attentions[0].shape[-3:]),
                [self.model_tester.num_attention_heads, subsampled_encoder_seq_length, subsampled_encoder_key_length],
            )
            out_len = len(outputs)

            correct_outlen = 5

            # loss is at first position
            if "labels" in inputs_dict:
                correct_outlen += 1  # loss is added to beginning
            if "past_key_values" in outputs:
                correct_outlen += 1  # past_key_values have been returned

            self.assertEqual(out_len, correct_outlen)

            # decoder attentions
            decoder_attentions = outputs.decoder_attentions
            self.assertIsInstance(decoder_attentions, (list, tuple))
            self.assertEqual(len(decoder_attentions), self.model_tester.num_hidden_layers)
            self.assertListEqual(
                list(decoder_attentions[0].shape[-3:]),
                [self.model_tester.num_attention_heads, decoder_seq_length, decoder_key_length],
            )

            # cross attentions
            cross_attentions = outputs.cross_attentions
            self.assertIsInstance(cross_attentions, (list, tuple))
            self.assertEqual(len(cross_attentions), self.model_tester.num_hidden_layers)
            self.assertListEqual(
                list(cross_attentions[0].shape[-3:]),
                [
                    self.model_tester.num_attention_heads,
                    decoder_seq_length,
                    subsampled_encoder_key_length,
                ],
            )

            # Check attention is always last and order is fine
            inputs_dict["output_attentions"] = True
            inputs_dict["output_hidden_states"] = True
            model = model_class(config)
            model.to(torch_device)
            model.eval()
            with torch.no_grad():
                outputs = model(**self._prepare_for_class(inputs_dict, model_class))

            added_hidden_states = 2
            self.assertEqual(out_len + added_hidden_states, len(outputs))

            self_attentions = outputs.encoder_attentions if config.is_encoder_decoder else outputs.attentions

            self.assertEqual(len(self_attentions), self.model_tester.num_hidden_layers)
            self.assertListEqual(
                list(self_attentions[0].shape[-3:]),
                [self.model_tester.num_attention_heads, subsampled_encoder_seq_length, subsampled_encoder_key_length],
            )

    def test_resize_tokens_embeddings(self):
        (
            original_config,
            inputs_dict,
        ) = self.model_tester.prepare_config_and_inputs_for_common()
        if not self.test_resize_embeddings:
            return

        for model_class in self.all_model_classes:
            config = copy.deepcopy(original_config)
            model = model_class(config)
            model.to(torch_device)

            if self.model_tester.is_training is False:
                model.eval()

            model_vocab_size = config.vocab_size
            # Retrieve the embeddings and clone theme
            model_embed = model.resize_token_embeddings(model_vocab_size)
            cloned_embeddings = model_embed.weight.clone()

            # Check that resizing the token embeddings with a larger vocab size increases the model's vocab size
            model_embed = model.resize_token_embeddings(model_vocab_size + 10)
            self.assertEqual(model.config.vocab_size, model_vocab_size + 10)
            # Check that it actually resizes the embeddings matrix
            self.assertEqual(model_embed.weight.shape[0], cloned_embeddings.shape[0] + 10)
            # Check that the model can still do a forward pass successfully (every parameter should be resized)
            model(**self._prepare_for_class(inputs_dict, model_class))

            # Check that resizing the token embeddings with a smaller vocab size decreases the model's vocab size
            model_embed = model.resize_token_embeddings(model_vocab_size - 15)
            self.assertEqual(model.config.vocab_size, model_vocab_size - 15)
            # Check that it actually resizes the embeddings matrix
            self.assertEqual(model_embed.weight.shape[0], cloned_embeddings.shape[0] - 15)

            # make sure that decoder_input_ids are resized
            if "decoder_input_ids" in inputs_dict:
                inputs_dict["decoder_input_ids"].clamp_(max=model_vocab_size - 15 - 1)
            model(**self._prepare_for_class(inputs_dict, model_class))

            # Check that adding and removing tokens has not modified the first part of the embedding matrix.
            models_equal = True
            for p1, p2 in zip(cloned_embeddings, model_embed.weight):
                if p1.data.ne(p2.data).sum() > 0:
                    models_equal = False

            self.assertTrue(models_equal)

    def test_resize_embeddings_untied(self):
        (
            original_config,
            inputs_dict,
        ) = self.model_tester.prepare_config_and_inputs_for_common()
        if not self.test_resize_embeddings:
            return

        original_config.tie_word_embeddings = False

        # if model cannot untied embeddings -> leave test
        if original_config.tie_word_embeddings:
            return

        for model_class in self.all_model_classes:
            config = copy.deepcopy(original_config)
            model = model_class(config).to(torch_device)

            # if no output embeddings -> leave test
            if model.get_output_embeddings() is None:
                continue

            # Check that resizing the token embeddings with a larger vocab size increases the model's vocab size
            model_vocab_size = config.vocab_size
            model.resize_token_embeddings(model_vocab_size + 10)
            self.assertEqual(model.config.vocab_size, model_vocab_size + 10)
            output_embeds = model.get_output_embeddings()
            self.assertEqual(output_embeds.weight.shape[0], model_vocab_size + 10)
            # Check bias if present
            if output_embeds.bias is not None:
                self.assertEqual(output_embeds.bias.shape[0], model_vocab_size + 10)
            # Check that the model can still do a forward pass successfully (every parameter should be resized)
            model(**self._prepare_for_class(inputs_dict, model_class))

            # Check that resizing the token embeddings with a smaller vocab size decreases the model's vocab size
            model.resize_token_embeddings(model_vocab_size - 15)
            self.assertEqual(model.config.vocab_size, model_vocab_size - 15)
            # Check that it actually resizes the embeddings matrix
            output_embeds = model.get_output_embeddings()
            self.assertEqual(output_embeds.weight.shape[0], model_vocab_size - 15)
            # Check bias if present
            if output_embeds.bias is not None:
                self.assertEqual(output_embeds.bias.shape[0], model_vocab_size - 15)
            # Check that the model can still do a forward pass successfully (every parameter should be resized)
            if "decoder_input_ids" in inputs_dict:
                inputs_dict["decoder_input_ids"].clamp_(max=model_vocab_size - 15 - 1)
            # Check that the model can still do a forward pass successfully (every parameter should be resized)
            model(**self._prepare_for_class(inputs_dict, model_class))

    def test_generate_without_input_ids(self):
        pass

    @staticmethod
    def _get_encoder_outputs(
        model, input_ids, attention_mask, output_attentions=None, output_hidden_states=None, num_interleave=1
    ):
        encoder = model.get_encoder()
        encoder_outputs = encoder(
            input_ids,
            attention_mask=attention_mask,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
        )
        encoder_outputs["last_hidden_state"] = encoder_outputs.last_hidden_state.repeat_interleave(
            num_interleave, dim=0
        )
        input_ids = input_ids[:, :, 0]
        input_ids = torch.zeros_like(input_ids[:, :1], dtype=torch.long) + model._get_decoder_start_token_id()
        attention_mask = None
        return encoder_outputs, input_ids, attention_mask

    def _check_outputs(self, output, input_ids, config, use_cache=False, num_return_sequences=1):
        batch_size, seq_length = input_ids.shape[:2]
        subsampled_seq_length = self.model_tester.get_subsampled_output_lengths(seq_length)
        num_sequences_in_output = batch_size * num_return_sequences
        gen_len = (
            output.sequences.shape[-1] - 1 if config.is_encoder_decoder else output.sequences.shape[-1] - seq_length
        )

        # scores
        self._check_scores(num_sequences_in_output, output.scores, length=gen_len, config=config)

        # Attentions
        # encoder
        self._check_encoder_attention_for_generate(
            output.encoder_attentions, batch_size, config, subsampled_seq_length
        )
        # decoder
        self._check_attentions_for_generate(
            num_sequences_in_output,
            output.decoder_attentions,
            min_length=1,
            max_length=output.sequences.shape[-1],
            config=config,
            use_cache=use_cache,
        )

        # Hidden States
        # encoder
        self._check_encoder_hidden_states_for_generate(
            output.encoder_hidden_states, batch_size, config, subsampled_seq_length
        )

        # decoder
        self._check_hidden_states_for_generate(
            num_sequences_in_output,
            output.decoder_hidden_states,
            min_length=1,
            max_length=output.sequences.shape[-1],
            config=config,
            use_cache=use_cache,
        )


def assert_tensors_close(a, b, atol=1e-12, prefix=""):
    """If tensors have different shapes, different values or a and b are not both tensors, raise a nice Assertion error."""
    if a is None and b is None:
        return True
    try:
        if torch.allclose(a, b, atol=atol):
            return True
        raise
    except Exception:
        pct_different = (torch.gt((a - b).abs(), atol)).float().mean().item()
        if a.numel() > 100:
            msg = f"tensor values are {pct_different:.1%} percent different."
        else:
            # msg = f"{a} != {b}"
            print(a.shape)
            print(b.shape)
            msg = "not qual"
            print("not equal")
        if prefix:
            msg = prefix + ": " + msg
        raise AssertionError(msg)


def _long_tensor(tok_lst):
    return torch.tensor(tok_lst, dtype=torch.long, device=torch_device)


TOLERANCE = 1e-4


@require_torch
@require_sentencepiece
@require_tokenizers
@slow
class Speech2TextTransformerModelIntegrationTests(unittest.TestCase):
    @cached_property
    def default_tokenizer(self):
        return Speech2TextTokenizer.from_pretrained("s2t_transformer_s")

    def test_inference_no_head(self):
        model = Speech2TextTransformerModel.from_pretrained("s2t_transformer_s").to(torch_device)
        input_ids = _long_tensor([[0, 31414, 232, 328, 740, 1140, 12695, 69, 46078, 1588, 2]])
        decoder_input_ids = _long_tensor([[2, 0, 31414, 232, 328, 740, 1140, 12695, 69, 46078, 1588]])
        inputs_dict = prepare_speech_to_text_transformer_inputs_dict(model.config, input_ids, decoder_input_ids)
        with torch.no_grad():
            output = model(**inputs_dict)[0]
        expected_shape = torch.Size((1, 11, 1024))
        self.assertEqual(output.shape, expected_shape)
        # change to expected output here
        expected_slice = torch.tensor(
            [[0.7144, 0.8143, -1.2813], [0.7144, 0.8143, -1.2813], [-0.0467, 2.5911, -2.1845]], device=torch_device
        )
        self.assertTrue(torch.allclose(output[:, :3, :3], expected_slice, atol=TOLERANCE))

    def test_inference_head(self):
        model = Speech2TextTransformerForConditionalGeneration.from_pretrained("s2t_transformer_s").to(torch_device)

        # change to intended input
        input_ids = _long_tensor([[0, 31414, 232, 328, 740, 1140, 12695, 69, 46078, 1588, 2]])
        decoder_input_ids = _long_tensor([[0, 31414, 232, 328, 740, 1140, 12695, 69, 46078, 1588, 2]])
        inputs_dict = prepare_speech_to_text_transformer_inputs_dict(model.config, input_ids, decoder_input_ids)
        with torch.no_grad():
            output = model(**inputs_dict)[0]
        expected_shape = torch.Size((1, 11, model.config.vocab_size))
        self.assertEqual(output.shape, expected_shape)
        # change to expected output here
        expected_slice = torch.tensor(
            [[0.7144, 0.8143, -1.2813], [0.7144, 0.8143, -1.2813], [-0.0467, 2.5911, -2.1845]], device=torch_device
        )
        self.assertTrue(torch.allclose(output[:, :3, :3], expected_slice, atol=TOLERANCE))

    def test_seq_to_seq_generation(self):
        hf = Speech2TextTransformerForConditionalGeneration.from_pretrained("s2t_transformer_s").to(torch_device)
        tok = Speech2TextTokenizer.from_pretrained("s2t_transformer_s")

        batch_input = [
            # string 1,
            # string 2,
            # string 3,
            # string 4,
        ]

        # The below article tests that we don't add any hypotheses outside of the top n_beams
        dct = tok.batch_encode_plus(
            batch_input,
            max_length=512,
            padding="max_length",
            truncation_strategy="only_first",
            truncation=True,
            return_tensors="pt",
        )

        hypotheses_batch = hf.generate(
            input_ids=dct["input_ids"].to(torch_device),
            attention_mask=dct["attention_mask"].to(torch_device),
            num_beams=2,
        )

        EXPECTED = [
            # here expected 1,
            # here expected 2,
            # here expected 3,
            # here expected 4,
        ]

        generated = tok.batch_decode(
            hypotheses_batch.tolist(), clean_up_tokenization_spaces=True, skip_special_tokens=True
        )
        assert generated == EXPECTED


class Speech2TextTransformerStandaloneDecoderModelTester:
    def __init__(
        self,
        parent,
        vocab_size=99,
        batch_size=13,
        d_model=16,
        decoder_seq_length=7,
        is_training=True,
        is_decoder=True,
        use_attention_mask=True,
        use_cache=False,
        use_labels=True,
        decoder_start_token_id=2,
        decoder_ffn_dim=32,
        decoder_layers=4,
        encoder_attention_heads=4,
        decoder_attention_heads=4,
        max_position_embeddings=30,
        is_encoder_decoder=False,
        pad_token_id=0,
        bos_token_id=1,
        eos_token_id=2,
        scope=None,
    ):
        self.parent = parent
        self.batch_size = batch_size
        self.decoder_seq_length = decoder_seq_length
        # For common tests
        self.seq_length = self.decoder_seq_length
        self.is_training = is_training
        self.use_attention_mask = use_attention_mask
        self.use_labels = use_labels

        self.vocab_size = vocab_size
        self.d_model = d_model
        self.hidden_size = d_model
        self.num_hidden_layers = decoder_layers
        self.decoder_layers = decoder_layers
        self.decoder_ffn_dim = decoder_ffn_dim
        self.encoder_attention_heads = encoder_attention_heads
        self.decoder_attention_heads = decoder_attention_heads
        self.num_attention_heads = decoder_attention_heads
        self.eos_token_id = eos_token_id
        self.bos_token_id = bos_token_id
        self.pad_token_id = pad_token_id
        self.decoder_start_token_id = decoder_start_token_id
        self.use_cache = use_cache
        self.max_position_embeddings = max_position_embeddings
        self.is_encoder_decoder = is_encoder_decoder

        self.scope = None
        self.decoder_key_length = decoder_seq_length
        self.base_model_out_len = 2
        self.decoder_attention_idx = 1

    def prepare_config_and_inputs(self):
        input_ids = ids_tensor([self.batch_size, self.decoder_seq_length], self.vocab_size)

        attention_mask = None
        if self.use_attention_mask:
            attention_mask = ids_tensor([self.batch_size, self.decoder_seq_length], vocab_size=2)

        lm_labels = None
        if self.use_labels:
            lm_labels = ids_tensor([self.batch_size, self.decoder_seq_length], self.vocab_size)

        config = Speech2TextConfig(
            vocab_size=self.vocab_size,
            d_model=self.d_model,
            decoder_layers=self.decoder_layers,
            decoder_ffn_dim=self.decoder_ffn_dim,
            encoder_attention_heads=self.encoder_attention_heads,
            decoder_attention_heads=self.decoder_attention_heads,
            eos_token_id=self.eos_token_id,
            bos_token_id=self.bos_token_id,
            use_cache=self.use_cache,
            pad_token_id=self.pad_token_id,
            decoder_start_token_id=self.decoder_start_token_id,
            max_position_embeddings=self.max_position_embeddings,
            is_encoder_decoder=self.is_encoder_decoder,
        )

        return (
            config,
            input_ids,
            attention_mask,
            lm_labels,
        )

    def create_and_check_decoder_model_past(
        self,
        config,
        input_ids,
        attention_mask,
        lm_labels,
    ):
        config.use_cache = True
        model = Speech2TextTransformerDecoder(config=config).to(torch_device).eval()
        # first forward pass
        outputs = model(input_ids, use_cache=True)
        outputs_use_cache_conf = model(input_ids)
        outputs_no_past = model(input_ids, use_cache=False)

        self.parent.assertTrue(len(outputs) == len(outputs_use_cache_conf))
        self.parent.assertTrue(len(outputs) == len(outputs_no_past) + 1)

        past_key_values = outputs["past_key_values"]

        # create hypothetical next token and extent to next_input_ids
        next_tokens = ids_tensor((self.batch_size, 1), config.vocab_size)

        # append to next input_ids and
        next_input_ids = torch.cat([input_ids, next_tokens], dim=-1)

        output_from_no_past = model(next_input_ids)["last_hidden_state"]
        output_from_past = model(next_tokens, past_key_values=past_key_values)["last_hidden_state"]

        # select random slice
        random_slice_idx = ids_tensor((1,), output_from_past.shape[-1]).item()
        output_from_no_past_slice = output_from_no_past[:, next_input_ids.shape[-1] - 1, random_slice_idx].detach()
        output_from_past_slice = output_from_past[:, 0, random_slice_idx].detach()

        # test that outputs are equal for slice
        assert torch.allclose(output_from_past_slice, output_from_no_past_slice, atol=1e-3)

    def create_and_check_decoder_model_attention_mask_past(
        self,
        config,
        input_ids,
        attention_mask,
        lm_labels,
    ):
        model = Speech2TextTransformerDecoder(config=config).to(torch_device).eval()

        # create attention mask
        attn_mask = torch.ones(input_ids.shape, dtype=torch.long, device=torch_device)

        half_seq_length = input_ids.shape[-1] // 2
        attn_mask[:, half_seq_length:] = 0

        # first forward pass
        past_key_values = model(input_ids, attention_mask=attn_mask, use_cache=True)["past_key_values"]

        # create hypothetical next token and extent to next_input_ids
        next_tokens = ids_tensor((self.batch_size, 1), config.vocab_size)

        # change a random masked slice from input_ids
        random_seq_idx_to_change = ids_tensor((1,), half_seq_length).item() + 1
        random_other_next_tokens = ids_tensor((self.batch_size, 1), config.vocab_size).squeeze(-1)
        input_ids[:, -random_seq_idx_to_change] = random_other_next_tokens

        # append to next input_ids and attn_mask
        next_input_ids = torch.cat([input_ids, next_tokens], dim=-1)
        attn_mask = torch.cat(
            [attn_mask, torch.ones((attn_mask.shape[0], 1), dtype=torch.long, device=torch_device)],
            dim=1,
        )

        # get two different outputs
        output_from_no_past = model(next_input_ids)["last_hidden_state"]
        output_from_past = model(next_tokens, past_key_values=past_key_values)["last_hidden_state"]

        # select random slice
        random_slice_idx = ids_tensor((1,), output_from_past.shape[-1]).item()
        output_from_no_past_slice = output_from_no_past[:, next_input_ids.shape[-1] - 1, random_slice_idx].detach()
        output_from_past_slice = output_from_past[:, 0, random_slice_idx].detach()

        # test that outputs are equal for slice
        assert torch.allclose(output_from_past_slice, output_from_no_past_slice, atol=1e-2)

    def prepare_config_and_inputs_for_common(self):
        config_and_inputs = self.prepare_config_and_inputs()
        (
            config,
            input_ids,
            attention_mask,
            lm_labels,
        ) = config_and_inputs

        inputs_dict = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        return config, inputs_dict

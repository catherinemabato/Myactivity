# Copyright 2021 The HuggingFace Team. All rights reserved.
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

import json
import os
import shutil
import tempfile
import unittest
from multiprocessing import get_context
from pathlib import Path

import datasets
import numpy as np
from datasets import load_dataset

from transformers import AutoProcessor
from transformers.models.wav2vec2 import Wav2Vec2CTCTokenizer, Wav2Vec2FeatureExtractor
from transformers.models.wav2vec2.tokenization_wav2vec2 import VOCAB_FILES_NAMES
from transformers.testing_utils import require_pyctcdecode, require_torch, require_torchaudio, slow
from transformers.utils import FEATURE_EXTRACTOR_NAME, is_pyctcdecode_available, is_torch_available

from ..wav2vec2.test_feature_extraction_wav2vec2 import floats_list


if is_pyctcdecode_available():
    from huggingface_hub import snapshot_download
    from pyctcdecode import BeamSearchDecoderCTC
    from transformers.models.wav2vec2_with_lm import Wav2Vec2ProcessorWithLM
    from transformers.models.wav2vec2_with_lm.processing_wav2vec2_with_lm import Wav2Vec2DecoderWithLMOutput

if is_torch_available():
    from transformers import Wav2Vec2ForCTC


@require_pyctcdecode
class Wav2Vec2ProcessorWithLMTest(unittest.TestCase):
    def setUp(self):
        vocab = "| <pad> <unk> <s> </s> a b c d e f g h i j k".split()
        vocab_tokens = dict(zip(vocab, range(len(vocab))))

        self.add_kwargs_tokens_map = {
            "unk_token": "<unk>",
            "bos_token": "<s>",
            "eos_token": "</s>",
        }
        feature_extractor_map = {
            "feature_size": 1,
            "padding_value": 0.0,
            "sampling_rate": 16000,
            "return_attention_mask": False,
            "do_normalize": True,
        }

        self.tmpdirname = tempfile.mkdtemp()
        self.vocab_file = os.path.join(self.tmpdirname, VOCAB_FILES_NAMES["vocab_file"])
        self.feature_extraction_file = os.path.join(self.tmpdirname, FEATURE_EXTRACTOR_NAME)
        with open(self.vocab_file, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(vocab_tokens) + "\n")

        with open(self.feature_extraction_file, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(feature_extractor_map) + "\n")

        # load decoder from hub
        self.decoder_name = "hf-internal-testing/ngram-beam-search-decoder"

    def get_tokenizer(self, **kwargs_init):
        kwargs = self.add_kwargs_tokens_map.copy()
        kwargs.update(kwargs_init)
        return Wav2Vec2CTCTokenizer.from_pretrained(self.tmpdirname, **kwargs)

    def get_feature_extractor(self, **kwargs):
        return Wav2Vec2FeatureExtractor.from_pretrained(self.tmpdirname, **kwargs)

    def get_decoder(self, **kwargs):
        return BeamSearchDecoderCTC.load_from_hf_hub(self.decoder_name, **kwargs)

    def tearDown(self):
        shutil.rmtree(self.tmpdirname)

    def test_save_load_pretrained_default(self):
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        decoder = self.get_decoder()

        processor = Wav2Vec2ProcessorWithLM(tokenizer=tokenizer, feature_extractor=feature_extractor, decoder=decoder)

        processor.save_pretrained(self.tmpdirname)
        processor = Wav2Vec2ProcessorWithLM.from_pretrained(self.tmpdirname)

        # tokenizer
        self.assertEqual(processor.tokenizer.get_vocab(), tokenizer.get_vocab())
        self.assertIsInstance(processor.tokenizer, Wav2Vec2CTCTokenizer)

        # feature extractor
        self.assertEqual(processor.feature_extractor.to_json_string(), feature_extractor.to_json_string())
        self.assertIsInstance(processor.feature_extractor, Wav2Vec2FeatureExtractor)

        # decoder
        self.assertEqual(processor.decoder._alphabet.labels, decoder._alphabet.labels)
        self.assertEqual(
            processor.decoder.model_container[decoder._model_key]._unigram_set,
            decoder.model_container[decoder._model_key]._unigram_set,
        )
        self.assertIsInstance(processor.decoder, BeamSearchDecoderCTC)

    def test_save_load_pretrained_additional_features(self):
        processor = Wav2Vec2ProcessorWithLM(
            tokenizer=self.get_tokenizer(), feature_extractor=self.get_feature_extractor(), decoder=self.get_decoder()
        )
        processor.save_pretrained(self.tmpdirname)

        # make sure that error is thrown when decoder alphabet doesn't match
        processor = Wav2Vec2ProcessorWithLM.from_pretrained(
            self.tmpdirname, alpha=5.0, beta=3.0, score_boundary=-7.0, unk_score_offset=3
        )

        # decoder
        self.assertEqual(processor.language_model.alpha, 5.0)
        self.assertEqual(processor.language_model.beta, 3.0)
        self.assertEqual(processor.language_model.score_boundary, -7.0)
        self.assertEqual(processor.language_model.unk_score_offset, 3)

    def test_load_decoder_tokenizer_mismatch_content(self):
        tokenizer = self.get_tokenizer()
        # add token to trigger raise
        tokenizer.add_tokens(["xx"])
        with self.assertRaisesRegex(ValueError, "include"):
            Wav2Vec2ProcessorWithLM(
                tokenizer=tokenizer, feature_extractor=self.get_feature_extractor(), decoder=self.get_decoder()
            )

    def test_feature_extractor(self):
        feature_extractor = self.get_feature_extractor()
        tokenizer = self.get_tokenizer()
        decoder = self.get_decoder()

        processor = Wav2Vec2ProcessorWithLM(tokenizer=tokenizer, feature_extractor=feature_extractor, decoder=decoder)

        raw_speech = floats_list((3, 1000))

        input_feat_extract = feature_extractor(raw_speech, return_tensors="np")
        input_processor = processor(raw_speech, return_tensors="np")

        for key in input_feat_extract.keys():
            self.assertAlmostEqual(input_feat_extract[key].sum(), input_processor[key].sum(), delta=1e-2)

    def test_tokenizer(self):
        feature_extractor = self.get_feature_extractor()
        tokenizer = self.get_tokenizer()
        decoder = self.get_decoder()

        processor = Wav2Vec2ProcessorWithLM(tokenizer=tokenizer, feature_extractor=feature_extractor, decoder=decoder)

        input_str = "This is a test string"

        with processor.as_target_processor():
            encoded_processor = processor(input_str)

        encoded_tok = tokenizer(input_str)

        for key in encoded_tok.keys():
            self.assertListEqual(encoded_tok[key], encoded_processor[key])

    def _get_dummy_logits(self, shape=(2, 10, 16), seed=77):
        np.random.seed(seed)
        return np.random.rand(*shape)

    def test_decoder(self):
        feature_extractor = self.get_feature_extractor()
        tokenizer = self.get_tokenizer()
        decoder = self.get_decoder()

        processor = Wav2Vec2ProcessorWithLM(tokenizer=tokenizer, feature_extractor=feature_extractor, decoder=decoder)

        logits = self._get_dummy_logits(shape=(10, 16), seed=13)

        decoded_processor = processor.decode(logits)

        decoded_decoder = decoder.decode_beams(logits)[0]

        self.assertEqual(decoded_decoder[0], decoded_processor.text)
        self.assertEqual("</s> <s> </s>", decoded_processor.text)
        self.assertEqual(decoded_decoder[-2], decoded_processor.logit_score)
        self.assertEqual(decoded_decoder[-1], decoded_processor.lm_score)

    def test_decoder_batch(self):
        feature_extractor = self.get_feature_extractor()
        tokenizer = self.get_tokenizer()
        decoder = self.get_decoder()

        processor = Wav2Vec2ProcessorWithLM(tokenizer=tokenizer, feature_extractor=feature_extractor, decoder=decoder)

        logits = self._get_dummy_logits()

        decoded_processor = processor.batch_decode(logits)

        logits_list = [array for array in logits]
        pool = get_context("fork").Pool()
        decoded_beams = decoder.decode_beams_batch(pool, logits_list)
        texts_decoder, logit_scores_decoder, lm_scores_decoder = [], [], []
        for beams in decoded_beams:
            texts_decoder.append(beams[0][0])
            logit_scores_decoder.append(beams[0][-2])
            lm_scores_decoder.append(beams[0][-1])
        pool.close()

        self.assertListEqual(texts_decoder, decoded_processor.text)
        self.assertListEqual(["<s> <s> </s>", "<s> <s> <s>"], decoded_processor.text)
        self.assertListEqual(logit_scores_decoder, decoded_processor.logit_score)
        self.assertListEqual(lm_scores_decoder, decoded_processor.lm_score)

    def test_decoder_with_params(self):
        feature_extractor = self.get_feature_extractor()
        tokenizer = self.get_tokenizer()
        decoder = self.get_decoder()

        processor = Wav2Vec2ProcessorWithLM(tokenizer=tokenizer, feature_extractor=feature_extractor, decoder=decoder)

        logits = self._get_dummy_logits()

        beam_width = 20
        beam_prune_logp = -20.0
        token_min_logp = -4.0

        decoded_processor_out = processor.batch_decode(
            logits,
            beam_width=beam_width,
            beam_prune_logp=beam_prune_logp,
            token_min_logp=token_min_logp,
        )
        decoded_processor = decoded_processor_out.text

        logits_list = [array for array in logits]
        pool = get_context("fork").Pool()
        decoded_decoder_out = decoder.decode_beams_batch(
            pool,
            logits_list,
            beam_width=beam_width,
            beam_prune_logp=beam_prune_logp,
            token_min_logp=token_min_logp,
        )
        pool.close()

        decoded_decoder = [d[0][0] for d in decoded_decoder_out]

        self.assertListEqual(decoded_decoder, decoded_processor)
        self.assertListEqual(["<s> </s> </s>", "<s> <s> </s>"], decoded_processor)

    def test_decoder_with_params_of_lm(self):
        feature_extractor = self.get_feature_extractor()
        tokenizer = self.get_tokenizer()
        decoder = self.get_decoder()

        processor = Wav2Vec2ProcessorWithLM(tokenizer=tokenizer, feature_extractor=feature_extractor, decoder=decoder)

        logits = self._get_dummy_logits()

        alpha = 2.0
        beta = 5.0
        unk_score_offset = -20.0
        lm_score_boundary = True

        decoded_processor_out = processor.batch_decode(
            logits,
            alpha=alpha,
            beta=beta,
            unk_score_offset=unk_score_offset,
            lm_score_boundary=lm_score_boundary,
        )
        decoded_processor = decoded_processor_out.text

        logits_list = [array for array in logits]
        decoder.reset_params(
            alpha=alpha,
            beta=beta,
            unk_score_offset=unk_score_offset,
            lm_score_boundary=lm_score_boundary,
        )
        pool = get_context("fork").Pool()
        decoded_decoder_out = decoder.decode_beams_batch(
            pool,
            logits_list,
        )
        pool.close()

        decoded_decoder = [d[0][0] for d in decoded_decoder_out]

        self.assertListEqual(decoded_decoder, decoded_processor)
        self.assertListEqual(["<s> </s> <s> </s> </s>", "</s> </s> <s> </s> </s>"], decoded_processor)
        lm_model = processor.decoder.model_container[processor.decoder._model_key]
        self.assertEqual(lm_model.alpha, 2.0)
        self.assertEqual(lm_model.beta, 5.0)
        self.assertEqual(lm_model.unk_score_offset, -20.0)
        self.assertEqual(lm_model.score_boundary, True)

    def test_decoder_download_ignores_files(self):
        processor = Wav2Vec2ProcessorWithLM.from_pretrained("hf-internal-testing/processor_with_lm")

        language_model = processor.decoder.model_container[processor.decoder._model_key]
        path_to_cached_dir = Path(language_model._kenlm_model.path.decode("utf-8")).parent.parent.absolute()

        downloaded_decoder_files = os.listdir(path_to_cached_dir)
        expected_decoder_files = ["alphabet.json", "language_model"]

        downloaded_decoder_files.sort()
        expected_decoder_files.sort()

        # test that only decoder relevant files from
        # https://huggingface.co/hf-internal-testing/processor_with_lm/tree/main
        # are downloaded and none of the rest (e.g. README.md, ...)
        self.assertListEqual(downloaded_decoder_files, expected_decoder_files)

    def test_decoder_local_files(self):
        local_dir = snapshot_download("hf-internal-testing/processor_with_lm")

        processor = Wav2Vec2ProcessorWithLM.from_pretrained(local_dir)

        language_model = processor.decoder.model_container[processor.decoder._model_key]
        path_to_cached_dir = Path(language_model._kenlm_model.path.decode("utf-8")).parent.parent.absolute()

        local_decoder_files = os.listdir(local_dir)
        expected_decoder_files = os.listdir(path_to_cached_dir)

        local_decoder_files.sort()
        expected_decoder_files.sort()

        # test that both decoder form hub and local files in cache are the same
        self.assertListEqual(local_decoder_files, expected_decoder_files)

    def test_processor_from_auto_processor(self):
        processor_wav2vec2 = Wav2Vec2ProcessorWithLM.from_pretrained("hf-internal-testing/processor_with_lm")
        processor_auto = AutoProcessor.from_pretrained("hf-internal-testing/processor_with_lm")

        raw_speech = floats_list((3, 1000))

        input_wav2vec2 = processor_wav2vec2(raw_speech, return_tensors="np")
        input_auto = processor_auto(raw_speech, return_tensors="np")

        for key in input_wav2vec2.keys():
            self.assertAlmostEqual(input_wav2vec2[key].sum(), input_auto[key].sum(), delta=1e-2)

        logits = self._get_dummy_logits()

        decoded_wav2vec2 = processor_wav2vec2.batch_decode(logits)
        decoded_auto = processor_auto.batch_decode(logits)

        self.assertListEqual(decoded_wav2vec2.text, decoded_auto.text)

    @staticmethod
    def get_from_offsets(offsets, key):
        retrieved_list = [d[key] for d in offsets]
        return retrieved_list

    def test_offsets_integration_fast(self):
        processor = Wav2Vec2ProcessorWithLM.from_pretrained("hf-internal-testing/processor_with_lm")
        logits = self._get_dummy_logits()[0]

        outputs = processor.decode(logits, output_word_offsets=True)
        # check Wav2Vec2CTCTokenizerOutput keys for word
        self.assertTrue(len(outputs.keys()), 2)
        self.assertTrue("text" in outputs)
        self.assertTrue("word_offsets" in outputs)
        self.assertTrue(isinstance(outputs, Wav2Vec2DecoderWithLMOutput))

        self.assertEqual(" ".join(self.get_from_offsets(outputs["word_offsets"], "word")), outputs.text)
        self.assertListEqual(self.get_from_offsets(outputs["word_offsets"], "word"), ["<s>", "<s>", "</s>"])
        self.assertListEqual(self.get_from_offsets(outputs["word_offsets"], "start_offset"), [0, 2, 4])
        self.assertListEqual(self.get_from_offsets(outputs["word_offsets"], "end_offset"), [1, 3, 5])

    def test_offsets_integration_fast_batch(self):
        processor = Wav2Vec2ProcessorWithLM.from_pretrained("hf-internal-testing/processor_with_lm")
        logits = self._get_dummy_logits()

        outputs = processor.batch_decode(logits, output_word_offsets=True)

        # check Wav2Vec2CTCTokenizerOutput keys for word
        self.assertTrue(len(outputs.keys()), 2)
        self.assertTrue("text" in outputs)
        self.assertTrue("word_offsets" in outputs)
        self.assertTrue(isinstance(outputs, Wav2Vec2DecoderWithLMOutput))

        self.assertListEqual(
            [" ".join(self.get_from_offsets(o, "word")) for o in outputs["word_offsets"]], outputs.text
        )
        self.assertListEqual(self.get_from_offsets(outputs["word_offsets"][0], "word"), ["<s>", "<s>", "</s>"])
        self.assertListEqual(self.get_from_offsets(outputs["word_offsets"][0], "start_offset"), [0, 2, 4])
        self.assertListEqual(self.get_from_offsets(outputs["word_offsets"][0], "end_offset"), [1, 3, 5])

    @slow
    @require_torch
    @require_torchaudio
    def test_word_time_stamp_integration(self):
        import torch

        ds = load_dataset("common_voice", "en", split="train", streaming=True)
        ds = ds.cast_column("audio", datasets.Audio(sampling_rate=16_000))
        ds_iter = iter(ds)
        sample = next(ds_iter)

        processor = AutoProcessor.from_pretrained("patrickvonplaten/wav2vec2-base-100h-with-lm")
        model = Wav2Vec2ForCTC.from_pretrained("patrickvonplaten/wav2vec2-base-100h-with-lm")

        # compare to filename `common_voice_en_100038.mp3` of dataset viewer on https://huggingface.co/datasets/common_voice/viewer/en/train
        input_values = processor(sample["audio"]["array"], return_tensors="pt").input_values

        with torch.no_grad():
            logits = model(input_values).logits.cpu().numpy()

        output = processor.decode(logits[0], output_word_offsets=True)

        time_offset = model.config.inputs_to_logits_ratio / processor.feature_extractor.sampling_rate
        word_time_stamps = [
            {
                "start_time": d["start_offset"] * time_offset,
                "end_time": d["end_offset"] * time_offset,
                "word": d["word"],
            }
            for d in output["word_offsets"]
        ]

        EXPECTED_TEXT = "WHY DOES A MILE SANDRA LOOK LIKE SHE WANTS TO CONSUME JOHN SNOW ON THE RIVER AT THE WALL"

        # output words
        self.assertEqual(" ".join(self.get_from_offsets(word_time_stamps, "word")), EXPECTED_TEXT)
        self.assertEqual(" ".join(self.get_from_offsets(word_time_stamps, "word")), output.text)

        # output times
        start_times = [round(x, 2) for x in self.get_from_offsets(word_time_stamps, "start_time")]
        end_times = [round(x, 2) for x in self.get_from_offsets(word_time_stamps, "end_time")]

        # fmt: off
        self.assertListEqual(
            start_times,
            [
                1.42, 1.64, 2.12, 2.26, 2.54, 3.0, 3.24, 3.6, 3.8, 4.1, 4.26, 4.94, 5.28, 5.66, 5.78, 5.94, 6.32, 6.54, 6.66,
            ],
        )

        self.assertListEqual(
            end_times,
            [
                1.54, 1.88, 2.14, 2.46, 2.9, 3.18, 3.54, 3.72, 4.02, 4.18, 4.76, 5.16, 5.56, 5.7, 5.86, 6.2, 6.38, 6.62, 6.94,
            ],
        )
        # fmt: on

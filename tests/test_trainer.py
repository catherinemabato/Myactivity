import unittest

from transformers import AutoTokenizer, TrainingArguments, is_torch_available
from transformers.testing_utils import require_torch


if is_torch_available():
    import torch
    from torch.utils.data import IterableDataset

    from transformers import (
        AutoModelForSequenceClassification,
        DataCollatorForLanguageModeling,
        DataCollatorForPermutationLanguageModeling,
        GlueDataset,
        GlueDataTrainingArguments,
        LineByLineTextDataset,
        TextDataset,
        Trainer,
        default_data_collator,
    )


PATH_SAMPLE_TEXT = "./tests/fixtures/sample_text.txt"


@require_torch
class DataCollatorIntegrationTest(unittest.TestCase):
    def test_default_with_dict(self):
        features = [{"label": i, "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue(batch["labels"].equal(torch.tensor(list(range(8)))))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

        # With label_ids
        features = [{"label_ids": [0, 1, 2], "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue(batch["labels"].equal(torch.tensor([[0, 1, 2]] * 8)))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

        # Features can already be tensors
        features = [{"label": i, "inputs": torch.randint(10, [10])} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue(batch["labels"].equal(torch.tensor(list(range(8)))))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 10]))

        # Labels can already be tensors
        features = [{"label": torch.tensor(i), "inputs": torch.randint(10, [10])} for i in range(8)]
        batch = default_data_collator(features)
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertTrue(batch["labels"].equal(torch.tensor(list(range(8)))))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 10]))

    def test_default_with_no_labels(self):
        features = [{"label": None, "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue("labels" not in batch)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

        # With label_ids
        features = [{"label_ids": None, "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue("labels" not in batch)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

    def test_default_classification(self):
        MODEL_ID = "bert-base-cased-finetuned-mrpc"
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        data_args = GlueDataTrainingArguments(
            task_name="mrpc", data_dir="./tests/fixtures/tests_samples/MRPC", overwrite_cache=True
        )
        dataset = GlueDataset(data_args, tokenizer=tokenizer, mode="dev")
        data_collator = default_data_collator
        batch = data_collator(dataset.features)
        self.assertEqual(batch["labels"].dtype, torch.long)

    def test_default_regression(self):
        MODEL_ID = "distilroberta-base"
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        data_args = GlueDataTrainingArguments(
            task_name="sts-b", data_dir="./tests/fixtures/tests_samples/STS-B", overwrite_cache=True
        )
        dataset = GlueDataset(data_args, tokenizer=tokenizer, mode="dev")
        data_collator = default_data_collator
        batch = data_collator(dataset.features)
        self.assertEqual(batch["labels"].dtype, torch.float)

    def test_lm_tokenizer_without_padding(self):
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
        # ^ causal lm

        dataset = LineByLineTextDataset(tokenizer, file_path=PATH_SAMPLE_TEXT, block_size=512)
        examples = [dataset[i] for i in range(len(dataset))]
        with self.assertRaises(ValueError):
            # Expect error due to padding token missing on gpt2:
            data_collator(examples)

        dataset = TextDataset(tokenizer, file_path=PATH_SAMPLE_TEXT, block_size=512, overwrite_cache=True)
        examples = [dataset[i] for i in range(len(dataset))]
        batch = data_collator(examples)
        self.assertIsInstance(batch, dict)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 512)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 512)))

    def test_lm_tokenizer_with_padding(self):
        tokenizer = AutoTokenizer.from_pretrained("distilroberta-base")
        data_collator = DataCollatorForLanguageModeling(tokenizer)
        # ^ masked lm

        dataset = LineByLineTextDataset(tokenizer, file_path=PATH_SAMPLE_TEXT, block_size=512)
        examples = [dataset[i] for i in range(len(dataset))]
        batch = data_collator(examples)
        self.assertIsInstance(batch, dict)
        self.assertEqual(batch["input_ids"].shape, torch.Size((31, 107)))
        self.assertEqual(batch["labels"].shape, torch.Size((31, 107)))

        dataset = TextDataset(tokenizer, file_path=PATH_SAMPLE_TEXT, block_size=512, overwrite_cache=True)
        examples = [dataset[i] for i in range(len(dataset))]
        batch = data_collator(examples)
        self.assertIsInstance(batch, dict)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 512)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 512)))

    def test_plm(self):
        tokenizer = AutoTokenizer.from_pretrained("xlnet-base-cased")
        data_collator = DataCollatorForPermutationLanguageModeling(tokenizer)
        # ^ permutation lm

        dataset = LineByLineTextDataset(tokenizer, file_path=PATH_SAMPLE_TEXT, block_size=512)
        examples = [dataset[i] for i in range(len(dataset))]
        batch = data_collator(examples)
        self.assertIsInstance(batch, dict)
        self.assertEqual(batch["input_ids"].shape, torch.Size((31, 112)))
        self.assertEqual(batch["perm_mask"].shape, torch.Size((31, 112, 112)))
        self.assertEqual(batch["target_mapping"].shape, torch.Size((31, 112, 112)))
        self.assertEqual(batch["labels"].shape, torch.Size((31, 112)))

        dataset = TextDataset(tokenizer, file_path=PATH_SAMPLE_TEXT, block_size=512, overwrite_cache=True)
        examples = [dataset[i] for i in range(len(dataset))]
        batch = data_collator(examples)
        self.assertIsInstance(batch, dict)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 512)))
        self.assertEqual(batch["perm_mask"].shape, torch.Size((2, 512, 512)))
        self.assertEqual(batch["target_mapping"].shape, torch.Size((2, 512, 512)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 512)))

        example = [torch.randint(5, [5])]
        with self.assertRaises(ValueError):
            # Expect error due to odd sequence length
            data_collator(example)


@require_torch
class SampleIterableDataset(IterableDataset):
    def __init__(self, file_path):
        self.file_path = file_path

    def parse_file(self):
        f = open(self.file_path, "r")
        return f.readlines()

    def __iter__(self):
        return iter(self.parse_file())


@require_torch
class TrainerIntegrationTest(unittest.TestCase):
    def test_trainer_eval_mrpc(self):
        MODEL_ID = "bert-base-cased-finetuned-mrpc"
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
        data_args = GlueDataTrainingArguments(
            task_name="mrpc", data_dir="./tests/fixtures/tests_samples/MRPC", overwrite_cache=True
        )
        eval_dataset = GlueDataset(data_args, tokenizer=tokenizer, mode="dev")

        training_args = TrainingArguments(output_dir="./examples", no_cuda=True)
        trainer = Trainer(model=model, args=training_args, eval_dataset=eval_dataset)
        result = trainer.evaluate()
        self.assertLess(result["eval_loss"], 0.2)

    def test_trainer_eval_lm(self):
        MODEL_ID = "distilroberta-base"
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        dataset = LineByLineTextDataset(
            tokenizer=tokenizer, file_path=PATH_SAMPLE_TEXT, block_size=tokenizer.max_len_single_sentence,
        )
        self.assertEqual(len(dataset), 31)

    def test_trainer_iterable_dataset(self):
        MODEL_ID = "bert-base-cased-finetuned-mrpc"
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
        train_dataset = SampleIterableDataset(PATH_SAMPLE_TEXT)
        training_args = TrainingArguments(output_dir="./examples", no_cuda=True)
        trainer = Trainer(model=model, args=training_args, train_dataset=train_dataset)
        loader = trainer.get_train_dataloader()
        self.assertIsInstance(loader, torch.utils.data.DataLoader)

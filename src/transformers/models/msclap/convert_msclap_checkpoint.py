# coding=utf-8
# Copyright 2023 The HuggingFace Inc. team. All rights reserved.
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

import argparse
import re


from transformers import MSClapConfig, MSClapModel, MSClapFeatureExtractor

from msclap import CLAP

KEYS_TO_MODIFY_MAPPING = {
    "caption_encoder": "text_model",
    "text_model.projection": "text_projection", 
    "audio_encoder.base.htsat": "audio_model.audio_encoder",
    "audio_encoder.projection": "audio_projection", 
    "attn": "attention.self",
    "self.proj": "output.dense",
    "attention.self_mask": "attn_mask",
    "mlp.fc1": "intermediate.dense",
    "mlp.fc2": "output.dense",
    "norm1": "layernorm_before",
    "norm2": "layernorm_after",
    "bn0": "batch_norm",
}


IGNORE_WEIGHTS = [
    "spectrogram_extractor", 
    "logmel_extractor", 
    "attn_mask", 
    "head", 
]

GPT2_WEIGHTS = "caption_encoder.base"

def get_unused_weights(model, converted_state_dict, condition = "audio_model"): 

    audio_model_state_dict = [layer for layer in model.state_dict().keys() if re.search(condition, layer)]
    audio_layers_converted_checkpoints = [layer for layer in  converted_state_dict if re.search(condition, layer)]

    unused_audio_weights = set(audio_layers_converted_checkpoints) ^ set(audio_model_state_dict)
    unused_audio_weights = unused_audio_weights.intersection(set(audio_layers_converted_checkpoints))
    unused_audio_weights = [
        element for element in unused_audio_weights 
        if not any(re.search(pattern, element) for pattern in IGNORE_WEIGHTS)
    ]

    return unused_audio_weights

def init_msclap(version):

    clap_model = CLAP(version = version, use_cuda=False)

    return clap_model


def get_config_from_original(clap_model):
    audio_config = {
        "patch_embeds_hidden_size": clap_model.clap.audio_encoder.base.htsat.embed_dim,
        "depths": clap_model.clap.audio_encoder.base.htsat.depths,
        "hidden_size": clap_model.clap.audio_encoder.projection.linear1.in_features,
        "projection_dim": clap_model.clap.audio_encoder.projection.linear1.out_features,
    }

    text_config = {
        "hidden_size": clap_model.clap.caption_encoder.projection.linear1.in_features, 
        "projection_dim": clap_model.clap.audio_encoder.projection.linear1.out_features
    }

    projection_dim = clap_model.clap.audio_encoder.projection.linear1.out_features

    return MSClapConfig(audio_config=audio_config, text_config=text_config, projection_dim=projection_dim)


def rename_state_dict(state_dict):
    model_state_dict = {}

    sequential_layers_pattern = r".*sequential.(\d+).*"
    text_projection_pattern = r".*_projection.(\d+).*"

    for key, value in state_dict.items():
        # check if any key needs to be modified
        is_used = False

        if re.search(GPT2_WEIGHTS, key): 
            # Avoid all the other mapping transformations applied to the Audio Model and Projection Layers: 
            key = key.replace("caption_encoder", "text_model")
        else: 
            for key_to_modify, new_key in KEYS_TO_MODIFY_MAPPING.items():
                if key_to_modify in key:
                    key = key.replace(key_to_modify, new_key)

        if re.match(sequential_layers_pattern, key):
            # replace sequential layers with list
            sequential_layer = re.match(sequential_layers_pattern, key).group(1)

            key = key.replace(f"sequential.{sequential_layer}.", f"layers.{int(sequential_layer)//3}.linear.")
        elif re.match(text_projection_pattern, key):
            projecton_layer = int(re.match(text_projection_pattern, key).group(1))

            # Because in CLAP they use `nn.Sequential`...
            transformers_projection_layer = 1 if projecton_layer == 0 else 2

            key = key.replace(f"_projection.{projecton_layer}.", f"_projection.linear{transformers_projection_layer}.")

        if "audio" and "qkv" in key:
            # split qkv into query key and value
            mixed_qkv = value
            qkv_dim = mixed_qkv.size(0) // 3

            query_layer = mixed_qkv[:qkv_dim]
            key_layer = mixed_qkv[qkv_dim : qkv_dim * 2]
            value_layer = mixed_qkv[qkv_dim * 2 :]

            model_state_dict[key.replace("qkv", "query")] = query_layer
            model_state_dict[key.replace("qkv", "key")] = key_layer
            model_state_dict[key.replace("qkv", "value")] = value_layer
        else:
            model_state_dict[key] = value

    return model_state_dict


def convert_msclap_checkpoint(version, pytorch_dump_folder_path, enable_fusion=False):
    clap_model = init_msclap(version)

    clap_model.clap.eval()

    state_dict = clap_model.clap.state_dict()
    state_dict = rename_state_dict(state_dict)

    transformers_config = get_config_from_original(clap_model)
    transformers_config.audio_config.enable_fusion = enable_fusion
    model = MSClapModel(transformers_config)

    # ignore the spectrogram embedding layer
    model.load_state_dict(state_dict, strict=False)

    unused_audio_encoder_weights = get_unused_weights(model, state_dict, "audio_model")
    unused_audio_projection_weights = get_unused_weights(model, state_dict, "audio_projection")
    unused_text_encoder_weights = get_unused_weights(model, state_dict, "text_model")
    unused_text_projection_weights = get_unused_weights(model, state_dict, "text_projection")
   
    print(unused_audio_encoder_weights)
    print(unused_audio_projection_weights)
    print(unused_text_encoder_weights)
    print(unused_text_projection_weights)

    model.save_pretrained(pytorch_dump_folder_path)
    transformers_config.save_pretrained(pytorch_dump_folder_path)
    

def convert_feature_extractor_checkpoints(version ): 
    clap_model = init_msclap(version)
    
    clap_model.clap.eval()
    
    
    feature_extractor = MSClapFeatureExtractor()
    
    print('ok')
    
    
    pass



# check that both models share the same state dict: 


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.add_argument("--pytorch_dump_folder_path", default=None, type=str, help="Path to the output PyTorch model.")
    # parser.add_argument("--checkpoint_path", default=None, type=str, help="Path to fairseq checkpoint")
    # parser.add_argument("--config_path", default=None, type=str, help="Path to hf config.json of model to convert")
    # args = parser.parse_args()

    convert_feature_extractor_checkpoints("2023")

    pytorch_dump_folder_path = "/home/kamil/cache/msclap/"
    convert_msclap_checkpoint(
        '2023', pytorch_dump_folder_path
    )

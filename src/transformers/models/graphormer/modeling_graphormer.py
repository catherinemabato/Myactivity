# coding=utf-8
# Copyright 2022 Microsoft, clefourrier The HuggingFace Inc. team. All rights reserved.
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
""" PyTorch Graphormer model."""


import math
from typing import Optional, Tuple, Union

import torch
from torch import nn
from torch.nn import BCEWithLogitsLoss, CrossEntropyLoss, MSELoss

from ...activations import ACT2FN
from ...modeling_outputs import SequenceClassifierOutput
from ...modeling_utils import PreTrainedModel
from ...utils import logging
from .configuration_graphormer import GraphormerConfig
from .fairseq_utils import LayerDropModuleList, quant_noise


logger = logging.get_logger(__name__)

_CHECKPOINT_FOR_DOC = "graphormer-base-pcqm4mv1"
_CONFIG_FOR_DOC = "GraphormerConfig"


GRAPHORMER_PRETRAINED_MODEL_ARCHIVE_LIST = [
    "graphormer-base-pcqm4mv1",
    "graphormer-base-pcqm4mv2",
    # See all Graphormer models at https://huggingface.co/models?filter=graphormer
]


def init_params(module, num_layers):
    if isinstance(module, nn.Linear):
        module.weight.data.normal_(mean=0.0, std=0.02 / math.sqrt(num_layers))
        if module.bias is not None:
            module.bias.data.zero_()
    if isinstance(module, nn.Embedding):
        module.weight.data.normal_(mean=0.0, std=0.02)


class GraphNodeFeature(nn.Module):
    """
    Compute node features for each node in the graph.
    """

    def __init__(self, config):
        super(GraphNodeFeature, self).__init__()
        self.num_heads = config.num_attention_heads
        self.num_atoms = config.num_atoms

        self.atom_encoder = nn.Embedding(config.num_atoms + 1, config.hidden_size, padding_idx=config.pad_token_id)
        self.in_degree_encoder = nn.Embedding(
            config.num_in_degree, config.hidden_size, padding_idx=config.pad_token_id
        )
        self.out_degree_encoder = nn.Embedding(
            config.num_out_degree, config.hidden_size, padding_idx=config.pad_token_id
        )

        self.graph_token = nn.Embedding(1, config.hidden_size)

        # initializes all embedding parameters
        self.apply(lambda module: init_params(module, num_layers=config.num_layers))

    def forward(self, x, in_degree, out_degree):
        n_graph, n_node = x.size()[:2]

        node_feature = (  # node feature + graph token
            self.atom_encoder(x).sum(dim=-2)  # [n_graph, n_node, n_hidden]
            + self.in_degree_encoder(in_degree)
            + self.out_degree_encoder(out_degree)
        )

        graph_token_feature = self.graph_token.weight.unsqueeze(0).repeat(n_graph, 1, 1)

        graph_node_feature = torch.cat([graph_token_feature, node_feature], dim=1)

        return graph_node_feature


class GraphAttnBias(nn.Module):
    """
    Compute attention bias for each head.
    """

    def __init__(self, config):
        super(GraphAttnBias, self).__init__()
        self.num_heads = config.num_attention_heads
        self.multi_hop_max_dist = config.multi_hop_max_dist

        # We do not change edge feature embedding learning, as edge embeddings are represented as a combination of the original features
        # + shortest path
        self.edge_encoder = nn.Embedding(config.num_edges + 1, config.num_attention_heads, padding_idx=0)

        self.edge_type = config.edge_type
        if self.edge_type == "multi_hop":
            self.edge_dis_encoder = nn.Embedding(
                config.num_edge_dis * config.num_attention_heads * config.num_attention_heads,
                1,
            )

        self.spatial_pos_encoder = nn.Embedding(config.num_spatial, config.num_attention_heads, padding_idx=0)

        self.graph_token_virtual_distance = nn.Embedding(1, config.num_attention_heads)

        self.apply(lambda module: init_params(module, num_layers=config.num_layers))

    def forward(self, x, attn_bias, spatial_pos, edge_input, attn_edge_type):
        n_graph, n_node = x.size()[:2]
        graph_attn_bias = attn_bias.clone()
        graph_attn_bias = graph_attn_bias.unsqueeze(1).repeat(
            1, self.num_heads, 1, 1
        )  # [n_graph, n_head, n_node+1, n_node+1]

        # spatial pos
        # [n_graph, n_node, n_node, n_head] -> [n_graph, n_head, n_node, n_node]
        spatial_pos_bias = self.spatial_pos_encoder(spatial_pos).permute(0, 3, 1, 2)
        graph_attn_bias[:, :, 1:, 1:] = graph_attn_bias[:, :, 1:, 1:] + spatial_pos_bias

        # reset spatial pos here
        t = self.graph_token_virtual_distance.weight.view(1, self.num_heads, 1)
        graph_attn_bias[:, :, 1:, 0] = graph_attn_bias[:, :, 1:, 0] + t
        graph_attn_bias[:, :, 0, :] = graph_attn_bias[:, :, 0, :] + t

        # edge feature
        if self.edge_type == "multi_hop":
            spatial_pos_ = spatial_pos.clone()

            spatial_pos_[spatial_pos_ == 0] = 1  # set pad to 1
            # set 1 to 1, x > 1 to x - 1
            spatial_pos_ = torch.where(spatial_pos_ > 1, spatial_pos_ - 1, spatial_pos_)
            if self.multi_hop_max_dist > 0:
                spatial_pos_ = spatial_pos_.clamp(0, self.multi_hop_max_dist)
                edge_input = edge_input[:, :, :, : self.multi_hop_max_dist, :]
            # [n_graph, n_node, n_node, max_dist, n_head]

            edge_input = self.edge_encoder(edge_input).mean(-2)
            max_dist = edge_input.size(-2)
            edge_input_flat = edge_input.permute(3, 0, 1, 2, 4).reshape(max_dist, -1, self.num_heads)
            edge_input_flat = torch.bmm(
                edge_input_flat,
                self.edge_dis_encoder.weight.reshape(-1, self.num_heads, self.num_heads)[:max_dist, :, :],
            )
            edge_input = edge_input_flat.reshape(max_dist, n_graph, n_node, n_node, self.num_heads).permute(
                1, 2, 3, 0, 4
            )
            edge_input = (edge_input.sum(-2) / (spatial_pos_.float().unsqueeze(-1))).permute(0, 3, 1, 2)
        else:
            # [n_graph, n_node, n_node, n_head] -> [n_graph, n_head, n_node, n_node]
            edge_input = self.edge_encoder(attn_edge_type).mean(-2).permute(0, 3, 1, 2)

        graph_attn_bias[:, :, 1:, 1:] = graph_attn_bias[:, :, 1:, 1:] + edge_input
        graph_attn_bias = graph_attn_bias + attn_bias.unsqueeze(1)  # reset

        return graph_attn_bias


class MultiheadAttention(nn.Module):
    """Multi-headed attention.

    See "Attention Is All You Need" for more details.
    """

    def __init__(self, config):
        super().__init__()
        self.embedding_dim = config.embedding_dim
        self.kdim = config.kdim if config.kdim is not None else config.embedding_dim
        self.vdim = config.vdim if config.vdim is not None else config.embedding_dim
        self.qkv_same_dim = self.kdim == config.embedding_dim and self.vdim == config.embedding_dim

        self.num_heads = config.num_attention_heads
        self.dropout_module = torch.nn.Dropout(p=config.dropout, inplace=False)

        self.head_dim = config.embedding_dim // config.num_attention_heads
        if not (self.head_dim * config.num_attention_heads == self.embedding_dim):
            raise AssertionError("The embedding_dim must be divisible by num_heads.")
        self.scaling = self.head_dim**-0.5

        self.self_attention = True  # config.self_attention
        if not (self.self_attention):
            raise NotImplementedError("The Graphormer model only supports self attention for now.")
        if self.self_attention and not self.qkv_same_dim:
            raise AssertionError("Self-attention requires query, key and value to be of the same size.")

        self.k_proj = quant_noise(
            nn.Linear(self.kdim, config.embedding_dim, bias=config.bias),
            config.q_noise,
            config.qn_block_size,
        )
        self.v_proj = quant_noise(
            nn.Linear(self.vdim, config.embedding_dim, bias=config.bias),
            config.q_noise,
            config.qn_block_size,
        )
        self.q_proj = quant_noise(
            nn.Linear(config.embedding_dim, config.embedding_dim, bias=config.bias),
            config.q_noise,
            config.qn_block_size,
        )

        self.out_proj = quant_noise(
            nn.Linear(config.embedding_dim, config.embedding_dim, bias=config.bias),
            config.q_noise,
            config.qn_block_size,
        )

        self.onnx_trace = False

    def reset_parameters(self):
        if self.qkv_same_dim:
            # Empirically observed the convergence to be much better with
            # the scaled initialization
            nn.init.xavier_uniform_(self.k_proj.weight, gain=1 / math.sqrt(2))
            nn.init.xavier_uniform_(self.v_proj.weight, gain=1 / math.sqrt(2))
            nn.init.xavier_uniform_(self.q_proj.weight, gain=1 / math.sqrt(2))
        else:
            nn.init.xavier_uniform_(self.k_proj.weight)
            nn.init.xavier_uniform_(self.v_proj.weight)
            nn.init.xavier_uniform_(self.q_proj.weight)

        nn.init.xavier_uniform_(self.out_proj.weight)
        if self.out_proj.bias is not None:
            nn.init.constant_(self.out_proj.bias, 0.0)

    def forward(
        self,
        query,
        key: Optional[torch.Tensor],
        value: Optional[torch.Tensor],
        attn_bias: Optional[torch.Tensor],
        key_padding_mask: Optional[torch.Tensor] = None,
        need_weights: bool = True,
        attn_mask: Optional[torch.Tensor] = None,
        before_softmax: bool = False,
        need_head_weights: bool = False,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Args:
            key_padding_mask (Bytetorch.Tensor, optional): mask to exclude
                keys that are pads, of shape `(batch, src_len)`, where padding elements are indicated by 1s.
            need_weights (bool, optional): return the attention weights,
                averaged over heads (default: False).
            attn_mask (Bytetorch.Tensor, optional): typically used to
                implement causal attention, where the mask prevents the attention from looking forward in time
                (default: None).
            before_softmax (bool, optional): return the raw attention
                weights and values before the attention softmax.
            need_head_weights (bool, optional): return the attention
                weights for each head. Implies *need_weights*. Default: return the average attention weights over all
                heads.
        """
        if need_head_weights:
            need_weights = True

        tgt_len, bsz, embedding_dim = query.size()
        src_len = tgt_len
        if not (embedding_dim == self.embedding_dim):
            raise AssertionError(
                f"The query embedding dimension {embedding_dim} is not equal to the expected embedding_dim"
                f" {self.embedding_dim}."
            )
        if not (list(query.size()) == [tgt_len, bsz, embedding_dim]):
            raise AssertionError("Query size incorrect in Graphormer, compared to model dimensions.")

        if key is not None:
            src_len, key_bsz, _ = key.size()
            if not torch.jit.is_scripting():
                if (key_bsz != bsz) or (value is None) or not (src_len, bsz == value.shape[:2]):
                    raise AssertionError(
                        "The batch shape does not match the key or value shapes provided to the attention."
                    )

        q = self.q_proj(query)
        k = self.k_proj(query)
        v = self.v_proj(query)

        q *= self.scaling

        q = q.contiguous().view(tgt_len, bsz * self.num_heads, self.head_dim).transpose(0, 1)
        if k is not None:
            k = k.contiguous().view(-1, bsz * self.num_heads, self.head_dim).transpose(0, 1)
        if v is not None:
            v = v.contiguous().view(-1, bsz * self.num_heads, self.head_dim).transpose(0, 1)

        if (k is None) or not (k.size(1) == src_len):
            raise AssertionError("The shape of the key generated in the attention is incorrect")

        # This is part of a workaround to get around fork/join parallelism
        # not supporting Optional types.
        if key_padding_mask is not None and key_padding_mask.dim() == 0:
            key_padding_mask = None

        if key_padding_mask is not None:
            if key_padding_mask.size(0) != bsz or key_padding_mask.size(1) != src_len:
                raise AssertionError(
                    "The shape of the generated padding mask for the key does not match expected dimensions."
                )
        attn_weights = torch.bmm(q, k.transpose(1, 2))
        attn_weights = self.apply_sparse_mask(attn_weights, tgt_len, src_len, bsz)

        if list(attn_weights.size()) != [bsz * self.num_heads, tgt_len, src_len]:
            raise AssertionError("The attention weights generated do not match the expected dimensions.")

        if attn_bias is not None:
            attn_weights += attn_bias.view(bsz * self.num_heads, tgt_len, src_len)

        if attn_mask is not None:
            attn_mask = attn_mask.unsqueeze(0)
            attn_weights += attn_mask

        if key_padding_mask is not None:
            # don't attend to padding symbols
            attn_weights = attn_weights.view(bsz, self.num_heads, tgt_len, src_len)
            attn_weights = attn_weights.masked_fill(
                key_padding_mask.unsqueeze(1).unsqueeze(2).to(torch.bool), float("-inf")
            )
            attn_weights = attn_weights.view(bsz * self.num_heads, tgt_len, src_len)

        if before_softmax:
            return attn_weights, v

        attn_weights_float = torch.nn.functional.softmax(attn_weights, dim=-1)
        attn_weights = attn_weights_float.type_as(attn_weights)
        attn_probs = self.dropout_module(attn_weights)

        if v is None:
            raise AssertionError("No value generated")
        attn = torch.bmm(attn_probs, v)
        if list(attn.size()) != [bsz * self.num_heads, tgt_len, self.head_dim]:
            raise AssertionError("The attention generated do not match the expected dimensions.")

        attn = attn.transpose(0, 1).contiguous().view(tgt_len, bsz, embedding_dim)
        attn = self.out_proj(attn)

        attn_weights = None
        if need_weights:
            attn_weights = attn_weights_float.contiguous().view(bsz, self.num_heads, tgt_len, src_len).transpose(1, 0)
            if not need_head_weights:
                # average attention weights over heads
                attn_weights = attn_weights.mean(dim=0)

        return attn, attn_weights

    def apply_sparse_mask(self, attn_weights, tgt_len: int, src_len: int, bsz: int):
        return attn_weights


class GraphormerGraphEncoderLayer(nn.Module):
    def __init__(self, config) -> None:
        super().__init__()

        if config.init_fn is not None:
            config.init_fn()

        # Initialize parameters
        self.embedding_dim = config.embedding_dim
        self.num_attention_heads = config.num_attention_heads
        self.attention_dropout = config.attention_dropout
        self.q_noise = config.q_noise
        self.qn_block_size = config.qn_block_size
        self.pre_layernorm = config.pre_layernorm

        self.dropout_module = torch.nn.Dropout(p=config.dropout, inplace=False)

        self.activation_dropout_module = torch.nn.Dropout(p=config.dropout, inplace=False)

        # Initialize blocks
        self.activation_fn = ACT2FN[config.activation_fn]
        self.self_attn = MultiheadAttention(config)

        # layer norm associated with the self attention layer
        self.self_attn_layer_norm = nn.LayerNorm(self.embedding_dim)

        self.fc1 = self.build_fc(
            self.embedding_dim,
            config.ffn_embedding_dim,
            q_noise=config.q_noise,
            qn_block_size=config.qn_block_size,
        )
        self.fc2 = self.build_fc(
            config.ffn_embedding_dim,
            self.embedding_dim,
            q_noise=config.q_noise,
            qn_block_size=config.qn_block_size,
        )

        # layer norm associated with the position wise feed-forward NN
        self.final_layer_norm = nn.LayerNorm(self.embedding_dim)

    def build_fc(self, input_dim, output_dim, q_noise, qn_block_size):
        return quant_noise(nn.Linear(input_dim, output_dim), q_noise, qn_block_size)

    def forward(
        self,
        x: torch.Tensor,
        self_attn_bias: Optional[torch.Tensor] = None,
        self_attn_mask: Optional[torch.Tensor] = None,
        self_attn_padding_mask: Optional[torch.Tensor] = None,
    ):
        """
        nn.LayerNorm is applied either before or after the self-attention/ffn modules similar to the original
        Transformer implementation.
        """
        residual = x
        if self.pre_layernorm:
            x = self.self_attn_layer_norm(x)

        x, attn = self.self_attn(
            query=x,
            key=x,
            value=x,
            attn_bias=self_attn_bias,
            key_padding_mask=self_attn_padding_mask,
            need_weights=False,
            attn_mask=self_attn_mask,
        )
        x = self.dropout_module(x)
        x = residual + x
        if not self.pre_layernorm:
            x = self.self_attn_layer_norm(x)

        residual = x
        if self.pre_layernorm:
            x = self.final_layer_norm(x)
        x = self.activation_fn(self.fc1(x))
        x = self.activation_dropout_module(x)
        x = self.fc2(x)
        x = self.dropout_module(x)
        x = residual + x
        if not self.pre_layernorm:
            x = self.final_layer_norm(x)

        return x, attn


class GraphormerGraphEncoder(nn.Module):
    def __init__(self, config):
        super().__init__()

        self.dropout_module = torch.nn.Dropout(p=config.dropout, inplace=False)
        self.layerdrop = config.layerdrop
        self.embedding_dim = config.embedding_dim
        self.apply_graphormer_init = config.apply_graphormer_init
        self.traceable = config.traceable

        self.graph_node_feature = GraphNodeFeature(config)
        self.graph_attn_bias = GraphAttnBias(config)

        self.embed_scale = config.embed_scale

        if config.q_noise > 0:
            self.quant_noise = quant_noise(
                nn.Linear(self.embedding_dim, self.embedding_dim, bias=False),
                config.q_noise,
                config.qn_block_size,
            )
        else:
            self.quant_noise = None

        if config.encoder_normalize_before:
            self.emb_layer_norm = nn.LayerNorm(self.embedding_dim)
        else:
            self.emb_layer_norm = None

        if config.pre_layernorm:
            self.final_layer_norm = nn.LayerNorm(self.embedding_dim)

        if self.layerdrop > 0.0:
            self.layers = LayerDropModuleList(p=self.layerdrop)
        else:
            self.layers = nn.ModuleList([])
        self.layers.extend([GraphormerGraphEncoderLayer(config) for _ in range(config.num_layers)])

        # Apply initialization of model params after building the model
        if config.freeze_embeddings:
            raise NotImplementedError("Freezing embeddings is not implemented yet.")

        for layer in range(config.num_trans_layers_to_freeze):
            m = self.layers[layer]
            if m is not None:
                for p in m.parameters():
                    p.requires_grad = False

    def forward(
        self,
        x,
        attn_bias,
        in_degree,
        out_degree,
        spatial_pos,
        edge_input,
        attn_edge_type,
        perturb=None,
        last_state_only: bool = False,
        token_embeddings: Optional[torch.Tensor] = None,
        attn_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.torch.Tensor, torch.Tensor]:
        # compute padding mask. This is needed for multi-head attention
        data_x = x
        n_graph, n_node = data_x.size()[:2]
        padding_mask = (data_x[:, :, 0]).eq(0)
        padding_mask_cls = torch.zeros(n_graph, 1, device=padding_mask.device, dtype=padding_mask.dtype)
        padding_mask = torch.cat((padding_mask_cls, padding_mask), dim=1)

        attn_bias = self.graph_attn_bias(x, attn_bias, spatial_pos, edge_input, attn_edge_type)

        if token_embeddings is not None:
            x = token_embeddings
        else:
            x = self.graph_node_feature(x, in_degree, out_degree)

        if perturb is not None:
            x[:, 1:, :] += perturb

        if self.embed_scale is not None:
            x = x * self.embed_scale

        if self.quant_noise is not None:
            x = self.quant_noise(x)

        if self.emb_layer_norm is not None:
            x = self.emb_layer_norm(x)

        x = self.dropout_module(x)

        x = x.transpose(0, 1)

        inner_states = []
        if not last_state_only:
            inner_states.append(x)

        for layer in self.layers:
            x, _ = layer(
                x,
                self_attn_padding_mask=padding_mask,
                self_attn_mask=attn_mask,
                self_attn_bias=attn_bias,
            )
            if not last_state_only:
                inner_states.append(x)

        graph_rep = x[0, :, :]

        if last_state_only:
            inner_states = [x]

        if self.traceable:
            return torch.stack(inner_states), graph_rep
        else:
            return inner_states, graph_rep


class GraphormerDecoderHead(nn.Module):
    def __init__(self, embedding_dim, num_classes):
        super().__init__()
        """num_classes should be 1 for regression, or the number of classes for classification"""
        self.lm_output_learned_bias = nn.Parameter(torch.zeros(1))
        self.classifier = nn.Linear(embedding_dim, num_classes, bias=False)
        self.num_classes = num_classes

    def forward(self, x, **unused):
        x = self.classifier(x)
        x = x + self.lm_output_learned_bias
        return x


class GraphormerPreTrainedModel(PreTrainedModel):
    """
    An abstract class to handle weights initialization and a simple interface for downloading and loading pretrained
    models.
    """

    config_class = GraphormerConfig
    base_model_prefix = "graphormer"
    supports_gradient_checkpointing = True
    _keys_to_ignore_on_load_missing = [r"position_ids"]

    def normal_(self, data):
        # with FSDP, module params will be on CUDA, so we cast them back to CPU
        # so that the RNG is consistent with and without FSDP
        data.copy_(data.cpu().normal_(mean=0.0, std=0.02).to(data.device))

    def init_graphormer_params(self, module):
        """
        Initialize the weights specific to the Graphormer Model.
        """
        if isinstance(module, nn.Linear):
            self.normal_(module.weight.data)
            if module.bias is not None:
                module.bias.data.zero_()
        if isinstance(module, nn.Embedding):
            self.normal_(module.weight.data)
            if module.padding_idx is not None:
                module.weight.data[module.padding_idx].zero_()
        if isinstance(module, MultiheadAttention):
            self.normal_(module.q_proj.weight.data)
            self.normal_(module.k_proj.weight.data)
            self.normal_(module.v_proj.weight.data)

    def _init_weights(self, module):
        """Initialize the weights"""
        if isinstance(module, (nn.Linear, nn.Conv2d)):
            module.weight.data.normal_(mean=0.0, std=0.02)
            if module.bias is not None:
                module.bias.data.zero_()
        elif isinstance(module, nn.Embedding):
            module.weight.data.normal_(mean=0.0, std=0.02)
            if module.padding_idx is not None:
                module.weight.data[module.padding_idx].zero_()
        elif isinstance(module, MultiheadAttention):
            module.q_proj.weight.data.normal_(mean=0.0, std=0.02)
            module.k_proj.weight.data.normal_(mean=0.0, std=0.02)
            module.v_proj.weight.data.normal_(mean=0.0, std=0.02)
            module.reset_parameters()
        elif isinstance(module, nn.LayerNorm):
            module.bias.data.zero_()
            module.weight.data.fill_(1.0)
        elif isinstance(module, GraphormerGraphEncoder):
            if module.apply_graphormer_init:
                module.apply(self.init_graphormer_params)

        elif isinstance(module, nn.LayerNorm):
            module.bias.data.zero_()
            module.weight.data.fill_(1.0)

    def _set_gradient_checkpointing(self, module, value=False):
        if isinstance(module, GraphormerModel):
            module.gradient_checkpointing = value


class GraphormerModel(GraphormerPreTrainedModel):
    """The Graphormer model is a graph-encoder model.

    It goes from a graph to its representation. If you want to use the model for a downstream classification task, use
    GraphormerForGraphClassification instead. For any other downstream task, feel free to add a new class, or combine
    this model with a downstream model of your choice, following the example in GraphormerForGraphClassification.
    """

    def __init__(self, config):
        super().__init__(config)
        self.max_nodes = config.max_nodes

        self.graph_encoder = GraphormerGraphEncoder(config)

        self.share_input_output_embed = config.share_input_output_embed
        self.lm_output_learned_bias = None

        # Remove head is set to true during fine-tuning
        self.load_softmax = not getattr(config, "remove_head", False)

        self.lm_head_transform_weight = nn.Linear(config.embedding_dim, config.embedding_dim)
        self.activation_fn = ACT2FN[config.activation_fn]
        self.layer_norm = nn.LayerNorm(config.embedding_dim)

        self.post_init()

    def reset_output_layer_parameters(self):
        self.lm_output_learned_bias = nn.Parameter(torch.zeros(1))

    def get_input_embeddings(self):
        # This function does not make a lot of sense, as we combine at least 4 different types of embeddings for graph data (node, edges, features, ...)
        return

    def forward(
        self,
        x,
        attn_bias,
        in_degree,
        out_degree,
        spatial_pos,
        edge_input,
        attn_edge_type,
        perturb=None,
        masked_tokens=None,
        **unused
    ):
        inner_states, graph_rep = self.graph_encoder(
            x, attn_bias, in_degree, out_degree, spatial_pos, edge_input, attn_edge_type, perturb=perturb
        )

        # last inner state, then revert Batch and Graph len
        x = inner_states[-1].transpose(0, 1)

        # project masked tokens only
        if masked_tokens is not None:
            raise NotImplementedError

        x = self.layer_norm(self.activation_fn(self.lm_head_transform_weight(x)))

        # project back to size of vocabulary
        if self.share_input_output_embed and hasattr(self.graph_encoder.embed_tokens, "weight"):
            x = torch.nn.functional.linear(x, self.graph_encoder.embed_tokens.weight)

        return x

    def max_nodes(self):
        """Maximum output length supported by the encoder."""
        return self.max_nodes


class GraphormerForGraphClassification(GraphormerPreTrainedModel):
    """
    This model can be used for graph-level classification or regression tasks.

    It can be trained on
    - regression (by setting config.num_classes to 1); there should be one float-type label per graph
    - one task classification (by setting config.num_classes to the number of classes); there should be one integer
      label per graph
    - binary multi-task classification (by setting config.num_classes to the number of labels); there should be a list
      of integer labels for each graph.
    """

    def __init__(self, config):
        super().__init__(config)
        self.encoder = GraphormerModel(config)
        self.embedding_dim = config.embedding_dim

        self.classifier = GraphormerDecoderHead(self.embedding_dim, config.num_labels)

        # Initialize weights and apply final processing
        self.post_init()

    def forward(
        self,
        x,
        attn_bias,
        in_degree,
        out_degree,
        spatial_pos,
        edge_input,
        attn_edge_type,
        labels: Optional[torch.LongTensor] = None,
    ) -> Union[Tuple[torch.Tensor], SequenceClassifierOutput]:
        outputs = self.encoder(x, attn_bias, in_degree, out_degree, spatial_pos, edge_input, attn_edge_type)

        head_outputs = self.classifier(outputs)
        logits = head_outputs[:, 0, :].contiguous()

        if labels is not None:
            mask = ~torch.isnan(labels)

            if self.classifier.num_classes == 1:  # regression
                loss_fct = MSELoss()
                loss = loss_fct(logits[mask].squeeze(), labels[mask].squeeze().float())
            elif self.classifier.num_classes > 1 and len(labels.shape) == 1:  # One task classification
                loss_fct = CrossEntropyLoss()
                loss = loss_fct(logits[mask].view(-1, self.classifier.num_classes), labels[mask].view(-1))
            else:  # Binary multi-task classification
                loss_fct = BCEWithLogitsLoss(reduction="sum")
                loss = loss_fct(logits[mask], labels[mask])

        return SequenceClassifierOutput(loss=loss, logits=logits, hidden_states=None, attentions=None)

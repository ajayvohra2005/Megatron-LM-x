# Copyright (c) 2024, NVIDIA CORPORATION. All rights reserved.

from megatron.core.fusions.fused_bias_dropout import get_bias_dropout_add
from megatron.core.models.gpt.gpt_layer_specs import _get_mlp_module_spec
from megatron.core.tensor_parallel.layers import ColumnParallelLinear, RowParallelLinear
from megatron.core.transformer.attention import SelfAttention, SelfAttentionSubmodules
import torch

try:
    from megatron.core.extensions.transformer_engine import (
            TEDotProductAttention as DotProductAttention, TENorm as WrappedTorchNorm
    )
except ImportError:
    import warnings

    if torch.cuda.is_available():
        warnings.warn('Transformer Engine is not installed. Falling back to Megatron Local')
    
    from megatron.core.transformer.dot_product_attention import DotProductAttention
    from megatron.core.transformer.torch_norm import WrappedTorchNorm


from megatron.core.transformer.enums import AttnMaskType
from megatron.core.transformer.identity_op import IdentityOp
from megatron.core.transformer.spec_utils import ModuleSpec
from megatron.core.transformer.transformer_layer import TransformerLayer, TransformerLayerSubmodules


# Use this spec for ModelOpt PTQ and TensorRT-LLM export
def get_gpt_layer_modelopt_spec(
    num_experts: int = None,
    moe_grouped_gemm: bool = False,
    remap_te_layernorm: bool = False,
    qk_layernorm: bool = False,
) -> ModuleSpec:
    """Mix the native spec with TENorm.

    This is essentially the native local spec except for the layernorm implementation
    is using TENorm from Transformer-Engine. The issue is that FusedLayerNorm from apex
    has stopped supporting RMSNorm needed by llama.
    """
    mlp = _get_mlp_module_spec(
        use_te=False, num_experts=num_experts, moe_grouped_gemm=moe_grouped_gemm, fp8=False
    )
    sharded_state_dict_keys_map = {}
    if remap_te_layernorm:
        if num_experts:
            sharded_state_dict_keys_map = {
                'input_layernorm.': 'self_attention.linear_qkv.layer_norm_'
            }
        else:
            sharded_state_dict_keys_map = {
                'input_layernorm.': 'self_attention.linear_qkv.layer_norm_',
                'pre_mlp_layernorm.': 'mlp.linear_fc1.layer_norm_',
            }
    return ModuleSpec(
        module=TransformerLayer,
        submodules=TransformerLayerSubmodules(
            input_layernorm=WrappedTorchNorm,
            self_attention=ModuleSpec(
                module=SelfAttention,
                params={"attn_mask_type": AttnMaskType.causal},
                submodules=SelfAttentionSubmodules(
                    linear_qkv=ColumnParallelLinear,
                    core_attention=DotProductAttention,
                    linear_proj=RowParallelLinear,
                    q_layernorm=WrappedTorchNorm if qk_layernorm else IdentityOp,
                    k_layernorm=WrappedTorchNorm if qk_layernorm else IdentityOp,
                ),
            ),
            self_attn_bda=get_bias_dropout_add,
            pre_mlp_layernorm=WrappedTorchNorm,
            mlp=mlp,
            mlp_bda=get_bias_dropout_add,
            # Map TE-layernorm-fusion keys back
            sharded_state_dict_keys_map=sharded_state_dict_keys_map,
        ),
    )

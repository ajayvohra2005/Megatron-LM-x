# Copyright (c) 2023, NVIDIA CORPORATION. All rights reserved.

from megatron.core.device_utils import get_current_device, get_current_device_type, get_xla_model
from megatron.core.models.gpt.gpt_layer_specs import get_gpt_layer_local_spec
import pytest
import torch

from megatron.core.transformer.mlp import MLP
from tests.unit_tests.test_utilities import Utils
from megatron.core.tensor_parallel.random import model_parallel_device_manual_seed
from megatron.core.transformer.transformer_config import TransformerConfig
from tests.unit_tests.test_utilities import Utils


xm = get_xla_model()

class TestParallelMLP:

    def setup_method(self, method):
        Utils.initialize_model_parallel(1,1)
        model_parallel_device_manual_seed(123)
        transformer_config = TransformerConfig(num_layers=2, hidden_size=12, num_attention_heads=4, use_cpu_initialization=True)
        self.mlp = MLP(transformer_config,
                       get_gpt_layer_local_spec().submodules.mlp.submodules)

    def teardown_method(self, method):
        Utils.destroy_model_parallel()

    def test_constructor(self):
        assert isinstance(self.mlp, MLP)

        num_weights = sum([p.numel() for p in self.mlp.parameters()])
        assert num_weights == 1212

    """
    def test_cpu_forward(self, mlp):
        # [sequence length, micro batch size, hidden size]
        hidden_states = torch.ones((32, 2, mlp.config.hidden_size))
        output, output_bias = mlp(hidden_states)
        assert output.shape[0] == 32
        assert output.shape[1] == 2
        assert output.shape[2] == mlp.config.hidden_size
        assert output_bias.shape[0] == mlp.config.hidden_size
        assert output.dtype == torch.float32
    """

    @pytest.mark.skipif(not xm and not torch.cuda.is_available(), reason="Device not available")
    def test_gpu_forward(self):
        mlp = self.mlp
        mlp.to(device=get_current_device())
        # [sequence length, batch size, hidden size]
        hidden_states = torch.ones((32, 2, mlp.config.hidden_size))
        hidden_states = hidden_states.to(device=get_current_device())
        output, output_bias = mlp(hidden_states)
        assert output.shape[0] == 32
        assert output.shape[1] == 2
        assert output.shape[2] == mlp.config.hidden_size
        assert output_bias.shape[0] == mlp.config.hidden_size
        assert output.dtype == torch.float32
        assert output.device.type == get_current_device_type()
        assert output_bias.device.type == get_current_device_type()

# Copyright (c) 2023, NVIDIA CORPORATION. All rights reserved.

from megatron.core.device_utils import get_current_device
import os

import pytest
import torch

from megatron.core.models.gpt.gpt_layer_specs import get_gpt_layer_with_transformer_engine_spec
from megatron.core.models.gpt.gpt_model import GPTModel
from megatron.core.tensor_parallel.random import model_parallel_device_manual_seed
from megatron.core.transformer.transformer_config import TransformerConfig
from tests.unit_tests.test_utilities import Utils


class TestGPTModel:

    def setup_method(self, method):
        os.environ.pop('NVTE_FUSED_ATTN', None)
        os.environ.pop('NVTE_FLASH_ATTN', None)
        os.environ.pop('NVTE_UNFUSED_ATTN', None)
        Utils.initialize_model_parallel(1, 1)
        model_parallel_device_manual_seed(123)
        transformer_config = TransformerConfig(
            num_layers=2, hidden_size=12, num_attention_heads=4, use_cpu_initialization=True
        )
        self.gpt_model = GPTModel(
            config=transformer_config,
            transformer_layer_spec=get_gpt_layer_with_transformer_engine_spec(),
            vocab_size=100,
            max_sequence_length=4,
        )

    def teardown_method(self, method):
        Utils.destroy_model_parallel()

    @pytest.mark.internal
    def test_constructor(self):
        assert isinstance(self.gpt_model, GPTModel)

        assert self.gpt_model.max_sequence_length == 4

        num_weights = sum([p.numel() for p in self.gpt_model.parameters()])
        assert num_weights == 6240

    @pytest.mark.internal
    def test_set_input_tensor(self):
        config: TransformerConfig = self.gpt_model.config
        sequence_length = self.gpt_model.max_sequence_length
        micro_batch_size = 2

        # [sequence length, batch size, hidden size]
        input_tensor = torch.ones((sequence_length, micro_batch_size, config.hidden_size))

        self.gpt_model.set_input_tensor(input_tensor)

        assert self.gpt_model.decoder.input_tensor.shape[0] == sequence_length
        assert self.gpt_model.decoder.input_tensor.shape[1] == micro_batch_size
        assert self.gpt_model.decoder.input_tensor.shape[2] == config.hidden_size

    @pytest.mark.internal
    def test_post_process_forward(self):
        config: TransformerConfig = self.gpt_model.config
        sequence_length = self.gpt_model.max_sequence_length
        micro_batch_size = 2

        self.gpt_model.to(device=get_current_device())

        data = list(range(sequence_length))
        input_ids = torch.tensor(data, dtype=torch.int64).repeat((micro_batch_size, 1)).to(device=get_current_device())
        position_ids = torch.tensor(data, dtype=torch.int64).repeat((micro_batch_size, 1)).to(device=get_current_device())
        attention_mask = torch.ones(
            (micro_batch_size, 1, sequence_length, sequence_length), dtype=bool
        ).to(device=get_current_device())

        logits = self.gpt_model.forward(
            input_ids=input_ids, position_ids=position_ids, attention_mask=attention_mask
        )

        assert logits.shape[0] == micro_batch_size
        assert logits.shape[1] == sequence_length
        assert logits.shape[2] == self.gpt_model.vocab_size

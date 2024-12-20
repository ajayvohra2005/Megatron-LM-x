# Copyright (c) 2024, NVIDIA CORPORATION. All rights reserved.
from megatron.core.parallel_state import is_pipeline_first_stage, is_pipeline_last_stage
from megatron.core.transformer.transformer_config import TransformerConfig
from megatron.core.models.gpt.gpt_model import GPTModel
from tests.unit_tests.test_utilities import Utils
from megatron.core.tensor_parallel.random import model_parallel_device_manual_seed
from megatron.core.inference.modelopt_support.gpt.model_specs import get_gpt_layer_modelopt_spec
from megatron.core.inference.modelopt_support.gpt.state_dict_hooks import (
    mcore_gpt_load_te_state_dict_pre_hook,
)
from megatron.core.models.gpt.gpt_layer_specs import (
    get_gpt_layer_with_transformer_engine_spec,
    get_gpt_layer_local_spec
)
from megatron.core.models.gpt.gpt_model import GPTModel
from megatron.core.transformer.transformer_config import TransformerConfig
from tests.unit_tests.test_utilities import Utils

try:
    import transformer_engine  # pylint: disable=unused-import

    HAVE_TE = True
except ImportError:
    HAVE_TE = False

class TestModelOptGPTModel:

    def setup_method(self, method):
        Utils.initialize_model_parallel(1,1)
        model_parallel_device_manual_seed(123)
        transformer_config = TransformerConfig(
            num_layers=2, hidden_size=12, num_attention_heads=4, use_cpu_initialization=True
        )
        self.gpt_model = GPTModel(
            config=transformer_config,
            transformer_layer_spec=get_gpt_layer_with_transformer_engine_spec() if HAVE_TE else get_gpt_layer_local_spec(),
            vocab_size=100,
            max_sequence_length=4,
            pre_process=is_pipeline_first_stage(),
            post_process=is_pipeline_last_stage(),
        )
        # Ensure that a GPTModel can be built with the modelopt spec.
        self.modelopt_gpt_model = GPTModel(
            config=transformer_config,
            transformer_layer_spec=get_gpt_layer_modelopt_spec(),
            vocab_size=100,
            max_sequence_length=4,
        )

    def test_load_te_state_dict_pre_hook(self):
        handle = self.modelopt_gpt_model._register_load_state_dict_pre_hook(
            mcore_gpt_load_te_state_dict_pre_hook
        )
        self.modelopt_gpt_model.load_state_dict(self.gpt_model.state_dict())
        handle.remove()

    def teardown_method(self, method):
        Utils.destroy_model_parallel()

from megatron.core.device_utils import get_current_device, get_current_rng_state, get_xla_model
from megatron.core.tensor_parallel.random import DeviceRNGStatesTracker
from megatron.core.tensor_parallel.random import model_parallel_device_manual_seed,get_device_rng_tracker
from megatron.core.tensor_parallel.random import checkpoint
from megatron.core.device_utils import set_manual_seed
from tests.unit_tests.test_utilities import Utils
import pytest
import torch

def test_device_rng_states_tracker():
    rng_tracker = DeviceRNGStatesTracker()
    rng_tracker.set_states({"state1":1234})
    assert(rng_tracker.get_states()["state1"] == 1234)
    rng_tracker.reset()
    assert rng_tracker.get_states() == {}
    seed = 1111
    rng_tracker.add("state2", seed)
    with pytest.raises(Exception):
        assert rng_tracker.add("state3", seed)
    with pytest.raises(Exception):
        assert rng_tracker.add("state2", 111)
    assert rng_tracker.get_states()['state2'] is not None
    with pytest.raises(Exception):
        assert ()

    rng_tracker.fork("state2")
    set_manual_seed(seed)
    rng_state = get_current_rng_state()
    xm = get_xla_model()
    if xm is None:
        assert torch.equal(rng_tracker.get_states()['state2'], rng_state)
    else:
        assert int(rng_tracker.get_states()['state2']) == rng_state

def test_model_parallel_device_manual_seed():
    Utils.initialize_model_parallel(4,2)
    model_parallel_device_manual_seed(0)
    rng_tracker = get_device_rng_tracker()
    assert(rng_tracker.get_states()['model-parallel-rng'] is not None)
    Utils.destroy_model_parallel()


def test_checkpoint():
    def test_forward(*input):
        return input[0] + input[1]

    assert torch.equal(
        torch.ones(16) * 3, checkpoint(test_forward, None, torch.ones(16), torch.ones(16) * 2)
    )
    Utils.initialize_model_parallel()
    input1 = torch.ones((4,4))
    checkpoint(test_forward, True, input1, torch.ones((4,4))*2)
    assert(torch.equal(torch.ones(input1.numel()).to(device=get_current_device()), input1))
    Utils.destroy_model_parallel()

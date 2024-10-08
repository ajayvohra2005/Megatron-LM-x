import torch

from megatron.core.tensor_parallel.data import broadcast_data
from megatron.core.device_utils import get_current_device
import torch
from tests.unit_tests.test_utilities import Utils


def test_broadcast_data():
    Utils.initialize_model_parallel(2, 4)
    input_data = {
        0 : torch.ones((8,8)).to(device=get_current_device()) * 0.0,
        1 : torch.ones((8,8)).to(device=get_current_device()) * 1.0,
        2 : torch.ones((8,8)).to(device=get_current_device()) * 2.0,
        3 : torch.ones((8,8)).to(device=get_current_device()) * 3.0,
        4 : torch.ones((8,8)).to(device=get_current_device()) * 4.0,
        5 : torch.ones((8,8)).to(device=get_current_device()) * 5.0,
        6 : torch.ones((8,8)).to(device=get_current_device()) * 6.0,
        7 : torch.ones((8,8)).to(device=get_current_device()) * 7.0
        }
    dtype = torch.float32
    actual_output = broadcast_data([0, 1], input_data, dtype)
    assert torch.equal(actual_output[0], input_data[0])
    assert torch.equal(actual_output[1], input_data[1])
    Utils.destroy_model_parallel()

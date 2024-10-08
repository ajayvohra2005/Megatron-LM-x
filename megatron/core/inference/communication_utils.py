# Copyright (c) 2024, NVIDIA CORPORATION. All rights reserved.
import torch

from megatron.core import parallel_state
from megatron.core.device_utils import get_current_device, get_xla_model


def _is_device(tensor):
    """Check if a tensor is not none and is on a device."""
    assert tensor is not None
    assert tensor.is_cuda or tensor.is_xla


def broadcast_from_last_pipeline_stage(size, dtype, tensor=None):
    """Broadcast a tensor from last pipeline stage to all ranks."""

    if parallel_state.is_pipeline_last_stage():
        _is_device(tensor)
        assert tensor.is_contiguous()
    else:
        tensor = torch.empty(size, dtype=dtype, device=get_current_device())
    # Get the group and corresponding source rank.
    src = parallel_state.get_pipeline_model_parallel_last_rank()
    xm = get_xla_model()
    if xm:
        groups = parallel_state.get_pipeline_model_parallel_groups()
        xm.collective_broadcast([tensor],
                         src,
                         groups=groups)
    else:
        group = parallel_state.get_pipeline_model_parallel_group()
        torch.distributed.broadcast(tensor, src, group)
    return tensor


def recv_from_prev_pipeline_rank_(recv_buffer=None):
    """Receive from previous pipeline stage and update the
    input buffer inplace."""
    recv_prev_op = torch.distributed.P2POp(
        torch.distributed.irecv, recv_buffer, parallel_state.get_pipeline_model_parallel_prev_rank()
    )
    reqs = torch.distributed.batch_isend_irecv([recv_prev_op])
    for req in reqs:
        req.wait()
    # To protect against race condition when using batch_isend_irecv().
    if torch.cuda.is_available():
            torch.cuda.synchronize()


def send_to_next_pipeline_rank(tensor=None):
    """Send output to the next pipeline stage."""
    send_next_op = torch.distributed.P2POp(
        torch.distributed.isend, tensor, parallel_state.get_pipeline_model_parallel_next_rank()
    )
    reqs = torch.distributed.batch_isend_irecv([send_next_op])
    for req in reqs:
        req.wait()
    # To protect against race condition when using batch_isend_irecv().
    if torch.cuda.is_available():
            torch.cuda.synchronize()

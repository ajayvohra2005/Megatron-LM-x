# Copyright (c) 2024, NVIDIA CORPORATION. All rights reserved.

import filecmp
import os
from unittest import mock

import pytest
import torch
import torch.distributed

from megatron.core.device_utils import get_xla_model
from megatron.core.parallel_state import get_default_process_group
from megatron.training.arguments import parse_args
from megatron.training.checkpointing import (
    _NON_PERSISTENT_CKPT_SUBDIR,
    load_checkpoint,
    save_checkpoint,
)
from tests.unit_tests.dist_checkpointing import (
    TempNamedDir,
    init_basic_mock_args,
    init_checkpointing_mock_args,
    setup_model_and_optimizer,
)
from tests.unit_tests.test_utilities import Utils

xm =  get_xla_model()

class TestNonPersistentSaveAndLoad:
    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        Utils.destroy_model_parallel()

    @pytest.mark.parametrize(('tp,pp'), [(2, 4)])
    def test_basic_save_load_scenarios(self, tmp_path_dist_ckpt, tp, pp):
        Utils.initialize_model_parallel(tp, pp)
        num_floating_point_operations_so_far = 0
        dist_opt = xm is None
        model, optimizer = setup_model_and_optimizer(1, tp, pp, dist_opt=dist_opt)
        opt_param_scheduler = None

        mock_args = parse_args(ignore_unknown_args=True)
        with TempNamedDir(
            tmp_path_dist_ckpt / "test_non_persistent",
            sync=True, process_group=get_default_process_group()
        ) as non_persistent_ckpt_dir, mock.patch(
            'megatron.training.checkpointing.get_args', new=lambda: mock_args
        ), mock.patch(
            "megatron.training.checkpointing.update_num_microbatches"
        ):
            init_basic_mock_args(mock_args, tp, pp)
            init_checkpointing_mock_args(mock_args, non_persistent_ckpt_dir)
            mock_args.non_persistent_ckpt_type = "global"
            mock_args.no_save_rng = True
            mock_args.no_load_rng = True

            save_checkpoint(
                2,
                model,
                optimizer,
                opt_param_scheduler,
                num_floating_point_operations_so_far,
                {},
                non_persistent_ckpt=True,
            )
            torch.distributed.barrier(group=get_default_process_group())
            save_checkpoint(
                3, model, optimizer, opt_param_scheduler, num_floating_point_operations_so_far, {},
            )
            torch.distributed.barrier(group=get_default_process_group())
            save_checkpoint(
                4,
                model,
                optimizer,
                opt_param_scheduler,
                num_floating_point_operations_so_far,
                {},
                non_persistent_ckpt=True,
            )
            torch.distributed.barrier(group=get_default_process_group())
            iteration, _ = load_checkpoint(model, optimizer, opt_param_scheduler)
            torch.distributed.barrier(group=get_default_process_group())
            assert iteration == 4
            save_checkpoint(
                6, model, optimizer, opt_param_scheduler, num_floating_point_operations_so_far, {}, 
            )
            torch.distributed.barrier(group=get_default_process_group())
            iteration, _ = load_checkpoint(model, optimizer, opt_param_scheduler)
            torch.distributed.barrier(group=get_default_process_group())
            assert iteration == 6
            save_checkpoint(
                8,
                model,
                optimizer,
                opt_param_scheduler,
                num_floating_point_operations_so_far,
                {},
                non_persistent_ckpt=True,
            )
            torch.distributed.barrier(group=get_default_process_group())
            iteration, _ = load_checkpoint(model, optimizer, opt_param_scheduler)
            torch.distributed.barrier(group=get_default_process_group())
            assert iteration == 8
            assert "iter_0000003" in os.listdir(non_persistent_ckpt_dir)
            assert "iter_0000006" in os.listdir(non_persistent_ckpt_dir)
            assert "iter_0000002" not in os.listdir(
                os.path.join(non_persistent_ckpt_dir, _NON_PERSISTENT_CKPT_SUBDIR)
            )
            assert "iter_0000004" in os.listdir(
                os.path.join(non_persistent_ckpt_dir, _NON_PERSISTENT_CKPT_SUBDIR)
            )
            assert "iter_0000008" in os.listdir(
                os.path.join(non_persistent_ckpt_dir, _NON_PERSISTENT_CKPT_SUBDIR)
            )
            ckpt_dirs = [
                "iter_0000003",
                "iter_0000006",
                _NON_PERSISTENT_CKPT_SUBDIR + "/iter_0000004",
                _NON_PERSISTENT_CKPT_SUBDIR + "/iter_0000008",
            ]
            for ckpt_a in ckpt_dirs:
                for ckpt_b in ckpt_dirs:
                    for filename in os.listdir(os.path.join(non_persistent_ckpt_dir, ckpt_a)):
                        if filename != "common.pt" and filename != ".metadata":
                            assert filecmp.cmp(
                                os.path.join(non_persistent_ckpt_dir, ckpt_a, filename),
                                os.path.join(non_persistent_ckpt_dir, ckpt_b, filename),
                                shallow=False,
                            ), [filename, ckpt_a, ckpt_b]
            torch.distributed.barrier(group=get_default_process_group())

        Utils.destroy_model_parallel()


class TestLegacySaveAndLoad:
    @pytest.mark.parametrize(('tp,pp'), [(2, 4)])
    def test_basic_save_load_scenario(self, tmp_path_dist_ckpt, tp, pp):
        Utils.initialize_model_parallel(tp, pp)
        num_floating_point_operations_so_far = 0
        dist_opt = xm is None
        model, optimizer = setup_model_and_optimizer(1, tp, pp, dist_opt=dist_opt)
        opt_param_scheduler = None

        mock_args = parse_args(ignore_unknown_args=True)
        with TempNamedDir(tmp_path_dist_ckpt / "test_legacy", 
                          sync=True, process_group=get_default_process_group()) as legacy_ckpt_dir, mock.patch(
            'megatron.training.checkpointing.get_args', new=lambda: mock_args
        ), mock.patch("megatron.training.checkpointing.update_num_microbatches"):
            init_basic_mock_args(mock_args, tp, pp)
            init_checkpointing_mock_args(mock_args, legacy_ckpt_dir)

            save_checkpoint(
                2, model, optimizer, opt_param_scheduler, num_floating_point_operations_so_far, {}
            )
            torch.distributed.barrier(group=get_default_process_group())
            iteration, _ = load_checkpoint(model, optimizer, opt_param_scheduler)
            torch.distributed.barrier(group=get_default_process_group())
            assert iteration == 2
            assert "iter_0000002" in os.listdir(legacy_ckpt_dir)
            torch.distributed.barrier(group=get_default_process_group())

        Utils.destroy_model_parallel()

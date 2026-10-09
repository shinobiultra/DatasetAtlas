"""Execution-device policy and Transformers output compatibility."""
from types import SimpleNamespace

import numpy as np
import pytest

from dataset_atlas.processors.device import torch_device
from dataset_atlas.processors.embeddings import _pooled_features, _vector
from dataset_atlas.jobs.manager import _resource_class


def runtime(cuda=False,mps=False):
    return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:cuda,device_count=lambda:1 if cuda else 0),
                           backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda:mps)),
                           __version__='fixture',version=SimpleNamespace(cuda='fixture-runtime'))


def test_device_auto_and_explicit_unavailable_accelerator():
    assert torch_device(runtime(),{})[0]=='cpu'
    assert torch_device(runtime(cuda=True),{})[0]=='cuda'
    assert torch_device(runtime(mps=True),{})[0]=='mps'
    device,proof=torch_device(runtime(cuda=True),{'device':'cpu'})
    assert device=='cpu' and proof['cuda_runtime'] is None
    for config in ({'device':'cuda'},{'device':'cuda:1'},{'device':'mps'},{'device':'http://external'}):
        with pytest.raises(ValueError):torch_device(runtime(),config)
    with pytest.raises(ValueError,match='unavailable'):torch_device(runtime(cuda=True),{'device':'cuda:1'})


def test_siglip2_uses_pooled_features_from_both_supported_api_shapes():
    class Tensor:
        def detach(self):return self
        def cpu(self):return self
        def numpy(self):return np.array([[3.0,4.0]])
    value=Tensor()
    for output in (value,SimpleNamespace(pooler_output=value,last_hidden_state='must not use token states')):
        assert _vector(_pooled_features(output).detach().cpu().numpy(),2)==pytest.approx([0.6,0.8])
    with pytest.raises(ValueError,match='pooled'):_pooled_features(SimpleNamespace(pooler_output=None))


def test_auto_acceleration_uses_the_exclusive_gpu_lease():
    accelerated={'device':'cpu','supported_devices':['auto','cpu','cuda','mps']}
    assert _resource_class(accelerated,{})=='gpu'
    assert _resource_class(accelerated,{'device':'auto'})=='gpu'
    assert _resource_class(accelerated,{'device':'cpu'})=='cpu'
    assert _resource_class(accelerated,{'device':'cuda:0'})=='gpu'
    assert _resource_class({'device':'cpu'},{})=='cpu'

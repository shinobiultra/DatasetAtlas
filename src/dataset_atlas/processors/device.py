"""Resolve an explicit local execution device without downloading anything."""
import re


def torch_device(torch,config):
    requested=config.get('device','auto')
    if not isinstance(requested,str) or not re.fullmatch(r'auto|cpu|mps|cuda(?::[0-9]{1,2})?',requested):
        raise ValueError('device must be auto, cpu, mps, cuda or cuda:N')
    cuda=getattr(getattr(torch,'cuda',None),'is_available',lambda:False)()
    mps=getattr(getattr(getattr(torch,'backends',None),'mps',None),'is_available',lambda:False)()
    device=('cuda' if cuda else 'mps' if mps else 'cpu') if requested=='auto' else requested
    if device.startswith('cuda'):
        index=int(device.split(':',1)[1]) if ':' in device else 0
        if not cuda or index>=torch.cuda.device_count():raise ValueError('Requested CUDA device is unavailable')
    elif device=='mps' and not mps:raise ValueError('Requested MPS device is unavailable')
    return device,{'requested_device':requested,'device':device,'torch_version':getattr(torch,'__version__',None),
                   'cuda_runtime':getattr(getattr(torch,'version',None),'cuda',None) if device.startswith('cuda') else None}

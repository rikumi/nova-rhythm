"""CPU safetensors reader using ordinary file reads, avoiding Windows mmap faults."""
import json
import struct


def load_cpu_safetensors(path, return_metadata=False):
    import torch
    dtypes = {'F64': torch.float64, 'F32': torch.float32, 'F16': torch.float16,
              'BF16': torch.bfloat16, 'F8_E4M3': torch.float8_e4m3fn,
              'F8_E5M2': torch.float8_e5m2, 'I64': torch.int64, 'I32': torch.int32,
              'I16': torch.int16, 'I8': torch.int8, 'U8': torch.uint8, 'BOOL': torch.bool}
    tensors = {}
    with open(path, 'rb') as stream:
        size = struct.unpack('<Q', stream.read(8))[0]
        if size > 100 * 1024 * 1024:
            raise ValueError('Invalid safetensors header length')
        header = json.loads(stream.read(size))
        for name, entry in header.items():
            if name == '__metadata__':
                continue
            start, end = entry['data_offsets']
            stream.seek(8 + size + start)
            data = bytearray(end - start)
            if stream.readinto(data) != len(data):
                raise ValueError('Truncated safetensors data: ' + name)
            dtype = dtypes[entry['dtype']]
            tensors[name] = torch.frombuffer(data, dtype=dtype).reshape(entry['shape']) if data else torch.empty(entry['shape'], dtype=dtype)
    return (tensors, header.get('__metadata__')) if return_metadata else tensors

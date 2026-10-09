"""Synthetic GLB bounds tests; these fixtures are not dataset coverage."""
import io
import json
import struct
import zlib

import pytest
from PIL import Image

from dataset_atlas.storage.glb import verify_glb


def glb(native=None, binary=b'\0' * 36):
    native = native or {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': len(binary)}],
                        'bufferViews': [{'buffer': 0, 'byteLength': len(binary)}],
                        'accessors': [{'type': 'VEC3', 'componentType':5126, 'count': 3}], 'nodes': [{}]}
    document = json.dumps(native).encode()
    document += b' ' * (-len(document) % 4)
    padded = binary + b'\0' * (-len(binary) % 4)
    chunks = struct.pack('<I4s', len(document), b'JSON') + document
    chunks += struct.pack('<I4s', len(padded), b'BIN\0') + padded
    return struct.pack('<4sII', b'glTF', 2, 12 + len(chunks)) + chunks


def base():
    return {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': 36}],
            'bufferViews': [{'buffer': 0, 'byteLength': 36}],
            'accessors': [{'type': 'VEC3', 'componentType':5126, 'count': 3}], 'nodes': [{}]}


def test_original_container_is_preserved_and_geometry_limit_checked():
    payload = glb()
    proof = verify_glb(payload)
    assert proof['original_bytes'] == len(payload) and proof['accessor_vec3_count'] == 3
    assert proof['external_resources'] is False
    with pytest.raises(ValueError, match='geometry limit'):
        verify_glb(payload, max_vertices=2)
    with pytest.raises(ValueError, match='byte limit'):
        verify_glb(payload, max_bytes=len(payload)-1)
    with pytest.raises(ValueError, match='header'):
        verify_glb(payload[:-1])


@pytest.mark.parametrize('change,reason', [
    ({'buffers': [{'byteLength': 36, 'uri': 'https://example.org/fixture.bin'}]}, 'embedded'),
    ({'images': [{'uri': 'https://example.org/fixture.png'}]}, 'external resources'),
    ({'bufferViews': [{'byteOffset': 35, 'byteLength': 4}]}, 'exceeds original'),
    ({'accessors': [{'type': 'VEC3', 'count': -1}]}, 'accessor count'),
    ({'nodes': [{'children': [1]}, {'children': [0]}]}, 'cyclic'),
    ({'nodes': [{'children': [2]}]}, 'hierarchy'),
    ({'extensionsRequired': ['KHR_draco_mesh_compression']}, 'unsupported preview decoder'),
    ({'images': [{'bufferView': -1}]}, 'image view'),
])
def test_unsafe_or_unsupported_originals_are_explicitly_excluded(change, reason):
    with pytest.raises(ValueError, match=reason):
        verify_glb(glb(base() | change))


def test_embedded_original_texture_is_decoded_with_a_pixel_budget():
    stream = io.BytesIO(); Image.new('RGB', (3, 4)).save(stream, 'PNG')
    texture = stream.getvalue()
    native = base() | {'buffers': [{'byteLength': len(texture)}],
                      'bufferViews': [{'byteLength': len(texture)}], 'images': [{'bufferView': 0}]}
    assert verify_glb(glb(native, texture))['texture_pixels'] == 12
    with pytest.raises(ValueError, match='pixel limit'):
        verify_glb(glb(native, texture), max_texture_pixels=11)


def test_checksumming_png_chunks_does_not_admit_an_undecodable_texture():
    stream = io.BytesIO(); Image.new('RGB', (3, 4)).save(stream, 'PNG')
    source = stream.getvalue(); chunks = [source[:8]]; position = 8
    while position < len(source):
        length, kind = struct.unpack_from('>I4s', source, position)
        payload = source[position+8:position+8+length]
        if kind == b'IDAT': payload = b'not compressed pixels'
        chunks.append(struct.pack('>I', len(payload))+kind+payload+struct.pack('>I', zlib.crc32(kind+payload)))
        position += 12+length
    texture = b''.join(chunks)
    with Image.open(io.BytesIO(texture)) as image: image.verify()
    native = base() | {'buffers': [{'byteLength': len(texture)}],
                      'bufferViews': [{'byteLength': len(texture)}], 'images': [{'bufferView': 0}]}
    with pytest.raises(OSError): verify_glb(glb(native, texture))


@pytest.mark.parametrize('kind', ['SCALAR','VEC2','VEC4','MAT2','MAT3','MAT4'])
def test_all_unbacked_accessor_allocations_are_bounded_before_viewer_decode(kind):
    native=base();native['accessors'].append({'componentType':5125,'type':kind,'count':1_000_000_000})
    with pytest.raises(ValueError,match='allocation limit'):verify_glb(glb(native))


@pytest.mark.parametrize('accessor', [
    {'componentType':9999,'type':'SCALAR','count':1},
    {'componentType':5126,'type':'INVALID','count':1},
    {'componentType':5126,'type':'VEC3','count':4,'bufferView':0},
    {'componentType':5126,'type':'VEC3','count':3,'bufferView':10},
    {'componentType':5126,'type':'VEC3','count':3,'bufferView':0,'byteOffset':1},
    {'componentType':5126,'type':'VEC3','count':3,'sparse':{'count':4}},
])
def test_invalid_accessor_type_reference_layout_or_sparse_count_is_refused(accessor):
    native=base();native['accessors']=[accessor]
    with pytest.raises(ValueError):verify_glb(glb(native))


def test_sparse_backed_accessor_counts_clone_and_index_allocations():
    native=base();native['accessors']=[{'componentType':5126,'type':'VEC3','count':2,
        'sparse':{'count':1,'indices':{'componentType':5121,'bufferView':0},'values':{'bufferView':0,'byteOffset':4}}}]
    assert verify_glb(glb(native))['decoded_accessor_bytes']==61
    with pytest.raises(ValueError,match='allocation limit'):verify_glb(glb(native),max_accessor_bytes=96)


def test_overlapping_buffer_views_cannot_multiply_decoder_allocations():
    native=base();native['bufferViews']=[{'byteLength':36}]*100
    with pytest.raises(ValueError,match='buffer view allocation'):verify_glb(glb(native),max_accessor_bytes=1000)


def test_instanced_nodes_cannot_multiply_render_geometry_work():
    native=base();native['meshes']=[{'primitives':[{'attributes':{'POSITION':0}}]}];native['nodes']=[{'mesh':0}]*10
    with pytest.raises(ValueError,match='instanced render'):verify_glb(glb(native),max_render_vertices=20)


def test_empty_nodes_in_many_scenes_cannot_multiply_object_allocations():
    native=base();native['nodes']=[{}]*1000;native['scenes']=[{'nodes':[0]}]*20
    with pytest.raises(ValueError,match='scene node allocation'):verify_glb(glb(native))

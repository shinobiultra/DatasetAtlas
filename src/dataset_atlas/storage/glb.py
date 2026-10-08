"""Bounded inspection of native GLB containers; no source code is executed."""
import base64
import io
import json
import struct

from PIL import Image


def verify_glb(data,*,max_bytes=32_000_000,max_vertices=1_000_000,max_texture_pixels=10_000_000,max_accessor_bytes=64_000_000,max_render_vertices=3_000_000):
    if not 20<=len(data)<=max_bytes:raise ValueError('GLB exceeds preview byte limit')
    magic,version,length=struct.unpack_from('<4sII',data)
    if magic!=b'glTF' or version!=2 or length!=len(data):raise ValueError('Invalid native GLB header')
    chunks=[];position=12
    while position<len(data):
        if position+8>len(data):raise ValueError('Truncated native GLB chunk')
        size,kind=struct.unpack_from('<I4s',data,position);position+=8
        if size%4 or position+size>len(data):raise ValueError('Invalid native GLB chunk length')
        chunks.append((kind,memoryview(data)[position:position+size]));position+=size
    if not chunks or chunks[0][0]!=b'JSON' or len(chunks)>2 or (len(chunks)==2 and chunks[1][0]!=b'BIN\x00'):
        raise ValueError('Unsupported native GLB chunk layout')
    if len(chunks[0][1])>8_000_000:raise ValueError('GLB JSON exceeds preview limit')
    native=json.loads(bytes(chunks[0][1]));binary=chunks[1][1] if len(chunks)==2 else memoryview(b'')
    if native.get('asset',{}).get('version')!='2.0':raise ValueError('Native GLB asset version changed')
    supported={'KHR_materials_unlit','KHR_texture_transform',
               'KHR_materials_clearcoat','KHR_materials_transmission','KHR_materials_ior',
               'KHR_materials_specular','KHR_materials_sheen','KHR_materials_volume',
               'KHR_materials_emissive_strength','KHR_materials_iridescence','KHR_lights_punctual',
               'KHR_materials_anisotropy','KHR_materials_dispersion'}
    if set(native.get('extensionsRequired',[]))-supported:raise ValueError('GLB requires an unsupported preview decoder')
    buffers=native.get('buffers',[])
    if len(buffers)!=1 or buffers[0].get('uri') is not None or not 0<=buffers[0]['byteLength']<=len(binary):
        raise ValueError('GLB preview requires one embedded original buffer')
    views=native.get('bufferViews',[])
    for view in views:
        if view.get('buffer',0)!=0 or type(view.get('byteOffset',0)) is not int or type(view.get('byteLength')) is not int:
            raise ValueError('Invalid native GLB buffer view')
        if min(view.get('byteOffset',0),view['byteLength'])<0 or view.get('byteOffset',0)+view['byteLength']>buffers[0]['byteLength']:
            raise ValueError('Native GLB buffer view exceeds original binary')
    view_bytes=sum(view['byteLength'] for view in views)
    if view_bytes>max_accessor_bytes:raise ValueError('GLB exceeds decoded buffer view allocation limit')
    component_bytes={5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}
    components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT2':4,'MAT3':9,'MAT4':16}
    def view_range(index,offset,count,element_bytes,alignment,*,allow_stride=True):
        if type(index) is not int or not 0<=index<len(views):raise ValueError('Invalid native GLB accessor view')
        view=views[index];stride=view.get('byteStride',element_bytes) if allow_stride else element_bytes
        if (type(offset) is not int or offset<0 or offset%alignment or type(stride) is not int
                or stride<element_bytes or ('byteStride' in view and (not allow_stride or not 4<=stride<=252 or stride%4))):
            raise ValueError('Invalid native GLB accessor layout')
        length=0 if count==0 else (count-1)*stride+element_bytes
        if offset+length>view['byteLength']:raise ValueError('Native GLB accessor exceeds original buffer view')
    accessors=native.get('accessors',[]);decoded_bytes=0
    for accessor in accessors:
        if type(accessor.get('count')) is not int or accessor['count']<0:
            raise ValueError('Invalid native GLB accessor count')
        kind=accessor.get('type');component=accessor.get('componentType')
        if kind not in components or type(component) is not int or component not in component_bytes:
            raise ValueError('Invalid native GLB accessor type or component')
        width=component_bytes[component];elements=components[kind];count=accessor['count']
        allocation=count*elements*width
        decoded_bytes+=allocation
        # Matrix columns are padded to four bytes in the source buffer.
        dimension=int(kind[-1]) if kind.startswith('MAT') else 1
        element_bytes=dimension*((dimension*width+3)//4*4) if kind.startswith('MAT') else elements*width
        offset=accessor.get('byteOffset',0)
        if 'bufferView' in accessor:view_range(accessor['bufferView'],offset,count,element_bytes,width)
        elif offset!=0:raise ValueError('Unbacked native GLB accessor has an offset')
        sparse=accessor.get('sparse')
        if sparse is not None:
            sparse_count=sparse.get('count');indices=sparse.get('indices',{});values=sparse.get('values',{})
            sparse_component=indices.get('componentType')
            if (type(sparse_count) is not int or not 0<=sparse_count<=count
                    or type(sparse_component) is not int or sparse_component not in {5121,5123,5125}):
                raise ValueError('Invalid native GLB sparse accessor')
            index_width=component_bytes[sparse_component]
            view_range(indices.get('bufferView'),indices.get('byteOffset',0),sparse_count,index_width,index_width,allow_stride=False)
            view_range(values.get('bufferView'),values.get('byteOffset',0),sparse_count,element_bytes,width,allow_stride=False)
            decoded_bytes+=allocation+sparse_count*(elements*width+index_width)
        if decoded_bytes+view_bytes>max_accessor_bytes:raise ValueError('GLB exceeds decoded accessor allocation limit')
    vertices=sum(accessor['count'] for accessor in accessors if accessor.get('type')=='VEC3')
    if vertices>max_vertices:raise ValueError('GLB exceeds preview geometry limit')
    pixels=0
    for image in native.get('images',[]):
        if 'uri' in image:
            uri=image['uri']
            if not isinstance(uri,str) or not uri.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):
                raise ValueError('GLB preview cannot fetch external resources')
            payload=base64.b64decode(uri.split(',',1)[1],validate=True)
        else:
            position=image.get('bufferView')
            if type(position) is not int or not 0<=position<len(views):raise ValueError('Invalid native GLB image view')
            view=views[position];start=view.get('byteOffset',0);payload=binary[start:start+view['byteLength']]
        with Image.open(io.BytesIO(payload)) as texture:
            if texture.format not in {'PNG','JPEG'}:raise ValueError('Unsupported native GLB texture format')
            pixels+=texture.width*texture.height
            if pixels>max_texture_pixels:raise ValueError('GLB exceeds preview texture pixel limit')
            texture.load()
    nodes=native.get('nodes',[])
    if len(nodes)>10000:raise ValueError('GLB exceeds preview node limit')
    active=set();done=set();parents=set()
    def visit(index,depth=0):
        if type(index) is not int or not 0<=index<len(nodes) or depth>128 or index in active:
            raise ValueError('Invalid or cyclic native GLB hierarchy')
        if index in done:return
        active.add(index)
        for child in nodes[index].get('children',[]):
            if child in parents:raise ValueError('Native GLB node has multiple parents')
            parents.add(child);visit(child,depth+1)
        active.remove(index);done.add(index)
    for i in range(len(nodes)):visit(i)
    scenes=native.get('scenes',[]);roots=0
    if len(scenes)>128 or len(nodes)*max(1,len(scenes))>10000:raise ValueError('GLB exceeds preview scene node allocation limit')
    for scene in scenes:
        for index in scene.get('nodes',[]):
            if type(index) is not int or not 0<=index<len(nodes) or index in parents:raise ValueError('Invalid native GLB scene root')
            roots+=1
    if roots>10000:raise ValueError('GLB exceeds preview scene allocation limit')
    weights=[]
    for mesh in native.get('meshes',[]):
        count=0
        for primitive in mesh.get('primitives',[]):
            index=primitive.get('indices',primitive.get('attributes',{}).get('POSITION'))
            if type(index) is not int or not 0<=index<len(accessors):raise ValueError('Invalid native GLB primitive accessor')
            count+=accessors[index]['count']
        weights.append(count)
    rendered=0;joints=0;skins=native.get('skins',[])
    for node in nodes:
        if 'EXT_mesh_gpu_instancing' in node.get('extensions',{}):raise ValueError('GLB instancing is outside the bounded preview decoder')
        if 'mesh' in node:
            index=node['mesh']
            if type(index) is not int or not 0<=index<len(weights):raise ValueError('Invalid native GLB mesh reference')
            rendered+=weights[index]
        if 'skin' in node:
            index=node['skin']
            if type(index) is not int or not 0<=index<len(skins):raise ValueError('Invalid native GLB skin reference')
            joints+=len(skins[index].get('joints',[]))
    rendered*=max(1,len(scenes));joints*=max(1,len(scenes))
    if rendered>max_render_vertices or joints>100_000:raise ValueError('GLB exceeds preview instanced render allocation limit')
    return {'format':'glTF 2.0 binary','original_bytes':len(data),'meshes':len(native.get('meshes',[])),
            'nodes':len(nodes),'accessor_vec3_count':vertices,'decoded_accessor_bytes':decoded_bytes,'buffer_view_allocation_bytes':view_bytes,'texture_pixels':pixels,
            'render_primitive_vertices':rendered,'skin_joint_instances':joints,
            'external_resources':False,'required_extensions':native.get('extensionsRequired',[])}

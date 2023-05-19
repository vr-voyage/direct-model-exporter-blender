import bpy
import math
from mathutils import Color

def best_texture_size_for(size):
    sizes = [
        1*1,
        2*2,
        4*4,
        8*8,
        16*16,
        32*32,
        64*64,
        128*128,
        256*256,
        512*512,
        1024*1024,
        2048*2048]
    
    for i in range(len(sizes)):
        if sizes[i] > size:
            square_size = 1 << i
            return [square_size, square_size]
    return [-1, -1]

def generate_exr_with_data(data, filepath):

    print("First data : %x" % data[0])

    data_size = len(data)
    width, height = best_texture_size_for(data_size)

    if (width == -1):
        print(f"Can't store {data_size} bytes in a 2K texture")
    
    print(f'Width : {width} - Height : {height}')
    # Create a new image with the specified width and height
    bpy.ops.image.new(
        name="ExrSaveData",
        width=width,
        height=height,
        float=True)

    image = bpy.data.images['ExrSaveData']

    image_settings = bpy.context.scene.render.image_settings
    image_settings.file_format = "OPEN_EXR"
    image_settings.color_depth = '32'
    image_settings.exr_codec = 'ZIP'

    #pixels = np.empty((height, width, 4), dtype=np.float32)
    
    pixels = image.pixels
    n_pixels = len(pixels)

    # Ugh... Blender has a flip OPERATOR, but it's not
    # accessible directly from the image object.
    # The EXR will be stored so that the first pixel
    # is at the top left.
    # Meaning that the first pixel data will suddenly
    # be written at (n_pixels - width)
    #
    # So... let's write each row, from top to bottom,
    # so that when saving the EXR file, the data will
    # start from 0 again...
    #
    # Fuck you Blender
    row = 0
    cursor = n_pixels
    width_in_pixels = width * 4
    mask = width_in_pixels - 1

    
    

    for i in range(min(data_size,n_pixels)):
        #row_pixel = (i & mask)
        #if row_pixel == 0:
        #    row += 1
        #    cursor = (n_pixels - (row * width_in_pixels))

        #print(f"pixels[{cursor + row_pixel}] = data[{i}] {data[i]}")
        #pixel = cursor + (row_pixel)
        pixel = i
        pixels[pixel] = data[i]

    # Save the image as an EXR file
    #image.filepath_raw = "C:/Users/PouiposaurusRex/Pictures/generated_texture.exr"
    #image.file_format = 'OPEN_EXR'

    image.save_render(filepath)

    # Free the image from memory
    bpy.data.images.remove(image)

def fixed_size_array(size, default_value = 0):
    return [default_value for x in range(size)]

def generate_voyage_exr(verts, normals, uvs, triangles, filepath):
    X = 0
    Y = 1
    Z = 2
    W = 3
    A = 0
    B = 1
    C = 2
    VOY = 0x00564f59
    AGE = 0x00454741
    MetadataVersion  = 4
    MetadataVertices = 8
    MetadataNormals  = 9
    MetadataUvs      = 10
    MetadataIndices  = 11

    MetadataSize = 64

    metadata = fixed_size_array(MetadataSize)

    metadata[0] = VOY
    metadata[1] = AGE
    metadata[2] = float('nan')
    metadata[3] = float('infinity')

    n_verts = len(verts)
    n_normals = len(normals)
    n_uvs = len(uvs)
    n_indices = len(triangles) * 3

    metadata[MetadataVersion]  = 2
    metadata[MetadataVertices] = n_verts
    metadata[MetadataNormals]  = n_normals
    metadata[MetadataUvs]      = n_uvs
    metadata[MetadataIndices]  = n_indices
    
    data_size = n_verts * 4 + n_normals * 4 + n_uvs * 4 + n_indices
    data = fixed_size_array(data_size)
    cursor = 0
    for vert in verts:
        data[cursor+0] = vert[X]
        data[cursor+1] = vert[Y]
        data[cursor+2] = vert[Z]
        data[cursor+3] = 0
        cursor += 4
    for normal in normals:
        data[cursor+0] = normal[X]
        data[cursor+1] = normal[Y]
        data[cursor+2] = normal[Z]
        data[cursor+3] = 0
        cursor += 4
    for uv in uvs:
        data[cursor+0] = uv[X]
        data[cursor+1] = uv[Y]
        data[cursor+2] = 0
        data[cursor+3] = 0
        cursor += 4
    for triangle in triangles:
        data[cursor+0] = triangle[A]
        data[cursor+1] = triangle[B]
        data[cursor+2] = triangle[C]
        cursor += 3

    print("Metadata[0] : %x" % metadata[0])
    generate_exr_with_data(
        data = (metadata + data),
        filepath = filepath)
    return

def add_to_list(list, element):
    list.append(element)

def add_vertex(vertices, coordinates):
    add_to_list(vertices, [coordinates[0], coordinates[1], coordinates[2]])

def add_normal(normals, normal):
    add_to_list(normals, [normal[0], normal[1], normal[2]])

def set_uv(uvs, index, uv):
    uvs[index] = uv

def add_triangle(triangles, indices):
    add_to_list(triangles, [indices[0], indices[1], indices[2]])

def active_mesh_to_voyage_exr(filepath):
    so = bpy.context.active_object
    dep_graph = bpy.context.evaluated_depsgraph_get()

    modified_object = so.evaluated_get(dep_graph)

    verts = modified_object.data.vertices
    polys = modified_object.data.polygons
    uvs   = modified_object.data.uv_layers.active.data

    out_verts   = []
    out_normals = []
    out_uvs     = []

    out_triangles = []

    X = 0
    Y = 1
    Z = 2

    for i in range(len(verts)):
        vertex = verts[i]
        add_vertex(out_verts, vertex.co)
        add_normal(out_normals, vertex.normal)
        out_uvs.append((0,0))

    for i in range(len(polys)):
        poly = polys[i]
        indices = poly.vertices
        add_triangle(out_triangles, indices)
        
        for vert_idx, loop_idx in zip(indices, poly.loop_indices):
            set_uv(out_uvs, vert_idx, uvs[loop_idx].uv)
    
    print(out_verts)
    print(out_normals)
    print(out_uvs)
    print(out_triangles)
    
    generate_voyage_exr(
        verts     = out_verts,
        normals   = out_normals,
        uvs       = out_uvs,
        triangles = out_triangles,
        filepath  = filepath)

active_mesh_to_voyage_exr(
    "C:/Users/PouiposaurusRex/Pictures/dumped_mesh.exr")


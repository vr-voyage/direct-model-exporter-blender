import math
import mathutils
from timeit import default_timer as timer

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty

bl_info = {
    "author": "Voyage (VRSNS)",
    "name": "Voyage 'Direct Model Exporter' for VRChat",
    "description": "Encode any active mesh into an EXR file to recreate it inside VRChat",
    "location": "Object > (Voyage) Encode active mesh to EXR...",
    "category": "Import-Export",
    "support": "COMMUNITY",
    "version": (1, 1, 2),
    "blender": (3, 4, 0),
    "warning": "",
    "doc_url": "",
}

langs = {
    'ja_JP': {
        ('Operator', '(Voyage) Encode active mesh to EXR...'): '(Voyage) アクティブ・メッシュをEXRファイルに・・・',
        ('*', 'Encode any active mesh into an EXR file to recreate it inside VRChat'): 'VRCHATで再現出来るように、アクティブ・メッシュをEXRファイルにエンコードする',
        ('*', 'Object > (Voyage) Encode active mesh to EXR...'): 'オブジェクト > (Voyage) アクティブ・メッシュをEXRファイルに・・・'
    }
}

class VoyageDirectModelExporter(bpy.types.Operator, ExportHelper):
    """Tooltip"""
    bl_idname = "object.voyage_encode_model_to_exr"
    bl_label = "(Voyage) Encode active mesh to EXR..."
    bl_description = "Encode the current active mesh to an EXR file, which can be downloaded on VRChat to regenerate the Mesh"

    # ExportHelper mixin class uses this
    filename_ext = ".exr"

    filter_glob: StringProperty(
        default="*.exr",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def print_error(self, message):
        print(message)

    def best_texture_size_for(self, size, max_length_size=2048):
        error_value = [-1, -1]
        square_length = 1

        while square_length <= max_length_size:
            if (square_length * square_length) > size:
                return [square_length, square_length]
            square_length <<= 1
        return error_value
    
    def sum_subarrays_lengths(self, arr):
        return sum(map(len, arr))
    
    def align_on_4(self, num):
        return (num+3)&~3

    def generate_exr_with_data(self, data, filepath):
        #timer_start = self.timer_start()
        data_size = len(data)
        width, height = self.best_texture_size_for(data_size)

        if (width == -1):
            print(f"Can't store {data_size} bytes in a 2K texture")
            return False
        
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
        
        pixels = image.pixels

        pixels[0:data_size] = data

        image.save_render(filepath)
        bpy.data.images.remove(image)
        return True

    def fixed_size_array(self, size, default_value = 0):
        return [default_value for x in range(size)]

    def generate_voyage_exr(self, verts, normals, uvs, submeshes_indices, filepath):
        # Coordinates and Triangles accessors
        X = 0
        Y = 1
        Z = 2
        W = 3
        A = 0
        B = 1
        C = 2
        
        VOY = 0x00564f59
        AGE = 0x00454741
        VoyageFormatVersion = 3
        IndexVersion  = 4
        IndexVertices = 8
        IndexNormals  = 9
        IndexUvs      = 10
        IndexIndices  = 11
        IndexSubmeshesCount = 12

        MetadataSize = 64

        metadata = self.fixed_size_array(MetadataSize)

        metadata[0] = VOY
        metadata[1] = AGE
        metadata[2] = float('infinity')
        metadata[3] = float('nan')

        n_verts   = len(verts)
        n_normals = len(normals)
        n_uvs     = len(uvs)
        n_indices = self.sum_subarrays_lengths(submeshes_indices)
        n_submeshes = len(submeshes_indices)

        metadata[IndexVersion]  = VoyageFormatVersion
        metadata[IndexVertices] = n_verts
        metadata[IndexNormals]  = n_normals
        metadata[IndexUvs]      = n_uvs
        metadata[IndexIndices]  = n_indices
        metadata[IndexSubmeshesCount] = n_submeshes

        channels_per_color = 4

        print(n_verts)
        print(n_normals)
        print(n_uvs)
        print(n_indices)
        print(n_submeshes)

        data_size = (
            n_verts * channels_per_color
            + n_normals * channels_per_color
            + n_uvs * channels_per_color
            + self.align_on_4(n_indices)
            + n_submeshes * channels_per_color)
        data = self.fixed_size_array(data_size)
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
        for submesh_indices in submeshes_indices:
            for index in submesh_indices:
                data[cursor] = index
                cursor += 1
        cursor = self.align_on_4(cursor)
        current_start = 0
        for submesh_indices in submeshes_indices:
            submesh_indices_count = len(submesh_indices)
            data[cursor+0] = current_start
            data[cursor+1] = submesh_indices_count
            current_start += submesh_indices_count
            cursor += 4

        return self.generate_exr_with_data(
            data = (metadata + data),
            filepath = filepath)
        

    def add_to_list(self, list, element):
        list.append(element)

    def add_vertex(self, vertices, coordinates):
        self.add_to_list(vertices, [coordinates[0], coordinates[1], coordinates[2]])

    def add_normal(self, normals, normal):
        self.add_to_list(normals, [normal[0], normal[1], normal[2]])

    def set_uv(self, uvs, index, uv):
        uvs[index] = uv
    
    def add_uv(self, uvs, uv):
        self.add_to_list(uvs, [uv[0], uv[1]])

    def add_triangle(self, triangles, indices):
        triangles.append(indices[0])
        triangles.append(indices[1])
        triangles.append(indices[2])

    # FIXME : While this actually works, design-wise, it's broken.
    # We're passing way too much data to ensure that vertex duplication
    # works.
    # So we'll need to have a some State object that handles the
    # duplication for us at some moment, instead of doing everything
    # in some random method
    def set_uv_duplicate_vertex_if_needed(
        self,
        previously_found_uvs,
        uv_list,
        vertex_index,
        uv_coordinates,
        vertices,
        normals
        ):
        
        # We need to duplicate some vertices sharing
        # - multiple normals (Auto Smooth)
        # - multiple UV
        #
        # Let's take care of the UV first.
        # We'll only deal with multiples UV per vertex
        # on the first UV map for the moment.
        # (We'll have to deal with multiple UV maps
        # afterwards for lightmapping... But... Ugh...
        # let's do it later...)
        #
        # Custom normals also will be for another moment.
        #
        # We'll tackle this using a stupid method at
        # the moment, since I can't think about anything
        # smart.
        # * We'll preallocate an array of 'len(verts)'
        # * For each UV found, we'll check if anything was
        #   added at that array[uvVertexIndex]
        #   * If nothing is there, we'll a list in the form of :
        #      [(u, v), vertexIndex] 
        #   * If some UV are already there:
        #     * For each [(u,v), vertexIndex]
        #       * We check if the current (u, v) coordinates are the same
        #         in which case we use the vertexIndex.
        #     * If no matching (u, v) are found in the list
        #       * We add a new vertex in the 'verts' list, with
        #         the same coordinates as the current uvVertexIndex
        #       * We add [(u, v), newVertexIndex] to the list
        
        # First time we stumble on this UV.
        # Let's record it, save the UV in the list, and report which vertex index
        # we used
        uvs_and_indices = previously_found_uvs[vertex_index]
        if uvs_and_indices == None:
            previously_found_uvs[vertex_index] = [[uv_coordinates, vertex_index]]
            self.set_uv(uv_list, vertex_index, uv_coordinates)
            return vertex_index
    
        for uvs_and_index in uvs_and_indices:
            # We already encountered that UV
            # Return the vertex index associated
            if uv_coordinates == uvs_and_index[0]:
                return uvs_and_index[1]
        
        # We have new UVS
        vertex = vertices[vertex_index]
        # FIXME : Find another solution...
        # We need to duplicate this one too
        normal = normals[vertex_index]
        # Preempt the new vertex Index
        new_vertex_index = len(vertices)
        # Actually add the new vertex, so that index is valid
        self.add_vertex(vertices, vertex)
        self.add_normal(normals, normal)
        # The UV list must have the same size as the vertex list,
        # so the added uv should map correctly
        self.add_uv(uv_list, uv_coordinates)
        uvs_and_indices.append([uv_coordinates, new_vertex_index])
        return new_vertex_index
        

    def active_mesh_to_voyage_exr(self, filepath):
        active_object = bpy.context.active_object
        if active_object.type != 'MESH':
            self.print_error('Active element is not a Mesh')
            return
        modifiers = active_object.modifiers
        if len(modifiers) == 0 or type(modifiers[-1]) != bpy.types.TriangulateModifier:
            modifiers.new(name="Voyage Exporter Triangulation", type='TRIANGULATE')

        dep_graph = bpy.context.evaluated_depsgraph_get()

        modified_object = active_object.evaluated_get(dep_graph)

        modified_object_data = modified_object.data
        verts = modified_object_data.vertices
        polys = modified_object_data.polygons
        uvs   = modified_object_data.uv_layers.active.data

        out_verts   = []
        out_normals = []
        out_uvs     = []

        out_indices = []
        n_materials = len(modified_object_data.materials)
        for _ in range(n_materials):
            out_indices.append([])
            

        X = 0
        Y = 1
        Z = 2

        for i in range(len(verts)):
            vertex = verts[i]
            # Flipping the X axis for Unity compatibility
            self.add_vertex(out_verts, vertex.co * mathutils.Vector((-1,1,1)))
            self.add_normal(out_normals, vertex.normal)
            out_uvs.append((0,0))

        found_uvs = self.fixed_size_array(len(verts), None)

        for i in range(len(polys)):
            poly = polys[i]
            # Sometimes, Blender will output garbage materials indices.
            # I have no idea why and how to handle this at the moment.
            # So, meanwhile, let's just ignore polygons using these materials...
            if poly.material_index >= n_materials:
                continue
            indices = poly.vertices
            actual_indices = []

            
            # Reversing the winding order, to avoid wrong normals
            for vert_idx, loop_idx in zip(reversed(indices), reversed(poly.loop_indices)):
                actual_indices.append(
                    self.set_uv_duplicate_vertex_if_needed(
                        previously_found_uvs=found_uvs,
                        uv_list=out_uvs,
                        vertex_index=vert_idx,
                        uv_coordinates=uvs[loop_idx].uv,
                        vertices=out_verts,
                        normals=out_normals))
            
            
            self.add_triangle(out_indices[poly.material_index], actual_indices)
            
        
        return self.generate_voyage_exr(
            verts     = out_verts,
            normals   = out_normals,
            uvs       = out_uvs,
            submeshes_indices = out_indices,
            filepath  = filepath)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        if not self.filepath:
            return {'FINISHED'}
        self.active_mesh_to_voyage_exr(self.filepath)
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(VoyageDirectModelExporter.bl_idname, text=VoyageDirectModelExporter.bl_label)

def register():
    bpy.app.translations.register(__name__, langs)
    bpy.utils.register_class(VoyageDirectModelExporter)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(VoyageDirectModelExporter)
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    bpy.app.translations.unregister(__name__)

if __name__ == "__main__":
    register()
    
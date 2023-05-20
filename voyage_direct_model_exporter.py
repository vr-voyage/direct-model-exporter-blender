import math
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
    "version": (1, 0),
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

    def best_texture_size_for(self, size, max_length_size=2048):
        error_value = [-1, -1]
        square_length = 1

        while square_length < max_length_size:
            if (square_length * square_length) > size:
                return [square_length, square_length]
            square_length <<= 1
        return error_value
        

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
        n_pixels = len(pixels)

        #self.elapsed_time('Elapsed time generate_exr_with_data (before loop)', timer_start)
        pixels[0:data_size] = data

        image.save_render(filepath)
        bpy.data.images.remove(image)
        #self.elapsed_time('Elapsed time generate_exr_with_data (after save render)', timer_start)
        return True

    def fixed_size_array(self, size, default_value = 0):
        return [default_value for x in range(size)]

    def generate_voyage_exr(self, verts, normals, uvs, triangles, filepath):
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
        VoyageFormatVersion = 2
        IndexVersion  = 4
        IndexVertices = 8
        IndexNormals  = 9
        IndexUvs      = 10
        IndexIndices  = 11

        MetadataSize = 64

        metadata = self.fixed_size_array(MetadataSize)

        metadata[0] = VOY
        metadata[1] = AGE
        metadata[2] = float('nan')
        metadata[3] = float('infinity')

        n_verts = len(verts)
        n_normals = len(normals)
        n_uvs = len(uvs)
        n_indices = len(triangles) * 3

        metadata[IndexVersion]  = VoyageFormatVersion
        metadata[IndexVertices] = n_verts
        metadata[IndexNormals]  = n_normals
        metadata[IndexUvs]      = n_uvs
        metadata[IndexIndices]  = n_indices
        
        data_size = n_verts * 4 + n_normals * 4 + n_uvs * 4 + n_indices
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
        for triangle in triangles:
            data[cursor+0] = triangle[A]
            data[cursor+1] = triangle[B]
            data[cursor+2] = triangle[C]
            cursor += 3

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

    def add_triangle(self, triangles, indices):
        self.add_to_list(triangles, [indices[0], indices[1], indices[2]])

    def active_mesh_to_voyage_exr(self, filepath):
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
            self.add_vertex(out_verts, vertex.co)
            self.add_normal(out_normals, vertex.normal)
            out_uvs.append((0,0))

        for i in range(len(polys)):
            poly = polys[i]
            indices = poly.vertices
            self.add_triangle(out_triangles, indices)
            
            for vert_idx, loop_idx in zip(indices, poly.loop_indices):
                self.set_uv(out_uvs, vert_idx, uvs[loop_idx].uv)
        
        return self.generate_voyage_exr(
            verts     = out_verts,
            normals   = out_normals,
            uvs       = out_uvs,
            triangles = out_triangles,
            filepath  = filepath)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

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


import bpy,sys,pathlib,math
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=12;s.cycles.use_denoising=False
s.render.resolution_x=360;s.render.resolution_y=640;s.render.resolution_percentage=100
s.render.fps=12;s.frame_start=1;s.frame_end=48
s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.025,.04,.075,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.3
s.render.image_settings.file_format='PNG';s.render.filepath=str(pathlib.Path('renders/preview/frame_').resolve());pathlib.Path('renders/preview').mkdir(parents=True,exist_ok=True)
def mat(name,color,metal=0,rough=.3):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;return m
jade=mat('Jade ceramic',(.025,.36,.24),.3);gold=mat('Brushed gold',(.8,.4,.065),.7);dark=mat('Deep blue',(.018,.032,.06),.2)
def sphere(loc,scale,material):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc);o=bpy.context.object;o.scale=scale;o.data.materials.append(material);bpy.ops.object.shade_smooth();return o
bpy.ops.mesh.primitive_plane_add(size=200);bpy.context.object.data.materials.append(dark)
bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=1.65,depth=.18,location=(0,0,.1));bpy.context.object.data.materials.append(gold)
for i in range(10):
 a=i*math.tau/10;o=sphere((math.cos(a)*1.1,math.sin(a)*1.1,.55),(.18,.18,.4),jade)
 o.scale=(.18,.18,.08);o.keyframe_insert(data_path='scale',frame=1+i*2);o.scale=(.18,.18,.65);o.keyframe_insert(data_path='scale',frame=24+i*2)
o=sphere((0,0,1.35),(.32,.32,.42),gold);o.location.z=2.0;o.keyframe_insert(data_path='location',frame=1);o.location.z=1.2;o.keyframe_insert(data_path='location',frame=48)
for loc,energy,size,color in [((2,-3,6),1000,4,(1,.8,.55)),((-3,1,4),1100,3,(.3,.7,1))]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=energy;o.data.shape='DISK';o.data.size=size;o.data.color=color;o.rotation_euler=(Vector((0,0,.5))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;s.camera=cam;cam.data.lens=48
for frame,loc in [(1,(4.5,-7,4.6)),(48,(2.7,-6.3,3.7))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,0,.9))-cam.location).to_track_quat('-Z','Y').to_euler();cam.keyframe_insert(data_path='location',frame=frame);cam.keyframe_insert(data_path='rotation_euler',frame=frame)
# Default keyframe interpolation is retained for compatibility across Blender versions.
bpy.ops.wm.save_as_mainfile(filepath=str(pathlib.Path('renders/nova_preview.blend').resolve()))
bpy.ops.render.render(animation=True)

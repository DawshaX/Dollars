"""Blender 4.x scene prototype, unrendered. Run: blender -b -t 4 -P scenes/glass_garden.py
Creates a .blend project; it does NOT render or publish automatically.
"""
import bpy,math,pathlib
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=64
s.render.resolution_x=1080;s.render.resolution_y=1920;s.render.resolution_percentage=50
s.render.fps=24;s.frame_start=1;s.frame_end=144
s.world.color=(0.04,0.04,0.04)
def material(name,color,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=.24;return m
jade=material('NOVA jade',(.04,.5,.3),.25);gold=material('Warm gold',(.9,.45,.08),.65)
bpy.ops.mesh.primitive_plane_add(size=200);bpy.context.object.data.materials.append(material('Midnight',(.015,.025,.05)))
for i in range(12):
 angle=i*math.tau/12;x,y=math.cos(angle)*1.3,math.sin(angle)*1.3
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=(x,y,.25));o=bpy.context.object;o.data.materials.append(jade)
 o.scale=(.08,.08,.08);o.keyframe_insert(data_path='scale',frame=1+i*4)
 o.scale=(.22,.22,.65);o.keyframe_insert(data_path='scale',frame=65+i*4)
 bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_uv_sphere_add(location=(0,0,1.6));o=bpy.context.object;o.scale=(.3,.3,.4);o.data.materials.append(gold);bpy.ops.object.shade_smooth()
for loc,power,size in [((2,-3,5),1200,4),((-3,1,3),900,3)]:
 bpy.ops.object.light_add(type='AREA',location=loc);bpy.context.object.data.energy=power;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=size
bpy.ops.object.camera_add();cam=bpy.context.object;s.camera=cam;cam.data.lens=48
for frame,loc in [(1,(4,-7,4)),(144,(2,-5,3))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,0,.7))-cam.location).to_track_quat('-Z','Y').to_euler();cam.keyframe_insert(data_path='location',frame=frame);cam.keyframe_insert(data_path='rotation_euler',frame=frame)
pathlib.Path('renders').mkdir(exist_ok=True);s.render.filepath='//renders/frame_';bpy.ops.wm.save_as_mainfile(filepath=str(pathlib.Path('glass_garden.blend').resolve()))

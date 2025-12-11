#!/usr/bin/env python3
"""
main_fixed.py - Main table project with EGL/Mesa fixes applied
"""

import os
import sys

# === APPLY THE SAME FIXES THAT WORKED IN egl_test_fixed.py ===
scripts_dir = os.path.dirname(sys.executable)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add to DLL search path
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(scripts_dir)
    os.add_dll_directory(current_dir)

# Add to PATH environment variable  
os.environ['PATH'] = scripts_dir + os.pathsep + current_dir + os.pathsep + os.environ['PATH']

# Set Mesa environment variables
os.environ["PYGLET_GL_LIB"] = "EGL"
os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"
os.environ["MESA_GLSL_VERSION_OVERRIDE"] = "330"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "0"

print("="*60)
print("Table Project with EGL/Mesa Fixes")
print("="*60)
print(f"Using Mesa OpenGL via: {os.environ.get('PYGLET_GL_LIB')}")

# Now import the rest of your modules
import json
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import numpy as np
import pyglet
from pyglet.window import key, mouse
import moderngl
from moderngl import Context, Program, Buffer, VertexArray, Framebuffer
from pyrr import Matrix44, Vector3

# =============================================================================
# Your existing table project code below...
# =============================================================================

@dataclass(frozen=True)
class Vector3D:
    x: float; y: float; z: float
    
    @classmethod
    def from_list(cls, data: List[float]) -> 'Vector3D':
        return cls(data[0], data[1], data[2])
    
    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]

@dataclass
class LegConfig:
    key: str; size: Vector3D; offset: Vector3D
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LegConfig':
        return cls(
            key=str(data['key']),
            size=Vector3D.from_list(data['size']),
            offset=Vector3D.from_list(data['offset'])
        )

@dataclass
class TabletopConfig:
    size: Vector3D; position: Vector3D
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TabletopConfig':
        return cls(
            size=Vector3D.from_list(data['size']),
            position=Vector3D.from_list(data.get('position', [0.0, 0.0, 0.0]))
        )

@dataclass
class ShapesConfig:
    tabletop: TabletopConfig; legs: List[LegConfig]; light_pos: Vector3D
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapesConfig':
        return cls(
            tabletop=TabletopConfig.from_dict(data['tabletop']),
            legs=[LegConfig.from_dict(leg) for leg in data['legs']],
            light_pos=Vector3D.from_list(data.get('light_pos', [4.0, 8.0, 10.0]))
        )

def load_configuration(shapes_path: str, joints_path: str):
    """Load and validate configuration files"""
    with open(shapes_path, 'r', encoding='utf-8') as f:
        shapes_data = json.load(f)
    with open(joints_path, 'r', encoding='utf-8') as f:
        joints_data = json.load(f)
    
    shapes_config = ShapesConfig.from_dict(shapes_data)
    print(f"Loaded configuration: {len(shapes_config.legs)} legs")
    return shapes_config, joints_data

def create_cube_geometry() -> bytes:
    """Create unit cube vertex data"""
    vertices = np.array([
        -0.5,-0.5,0.5, 0.5,-0.5,0.5, 0.5,0.5,0.5, -0.5,-0.5,0.5, 0.5,0.5,0.5, -0.5,0.5,0.5,
        -0.5,-0.5,-0.5, -0.5,0.5,-0.5, 0.5,0.5,-0.5, -0.5,-0.5,-0.5, 0.5,0.5,-0.5, 0.5,-0.5,-0.5,
        -0.5,-0.5,-0.5, -0.5,-0.5,0.5, -0.5,0.5,0.5, -0.5,-0.5,-0.5, -0.5,0.5,0.5, -0.5,0.5,-0.5,
        0.5,-0.5,-0.5, 0.5,0.5,-0.5, 0.5,0.5,0.5, 0.5,-0.5,-0.5, 0.5,0.5,0.5, 0.5,-0.5,0.5,
        -0.5,0.5,-0.5, -0.5,0.5,0.5, 0.5,0.5,0.5, -0.5,0.5,-0.5, 0.5,0.5,0.5, 0.5,0.5,-0.5,
        -0.5,-0.5,-0.5, 0.5,-0.5,-0.5, 0.5,-0.5,0.5, -0.5,-0.5,-0.5, 0.5,-0.5,0.5, -0.5,-0.5,0.5,
    ], dtype='f4')
    return vertices.tobytes()

class TableRenderer:
    def __init__(self, ctx: Context, shapes: ShapesConfig, joints: Dict[str, Any]):
        self.ctx = ctx
        self.shapes = shapes
        self.joints = joints
        
        # Initialize joint angles
        self.joint_angles = {leg.key: {'x': 0.0, 'y': 0.0, 'z': 0.0} for leg in shapes.legs}
        self.selected_leg = shapes.legs[0].key if shapes.legs else None
        
        # Create GPU resources
        self.setup_geometry()
        self.setup_shaders()
        
        print("✅ Table renderer initialized successfully!")
    
    def setup_geometry(self):
        """Setup vertex buffers"""
        cube_data = create_cube_geometry()
        self.vbo = self.ctx.buffer(cube_data)
        self.vao = None
    
    def setup_shaders(self):
        """Compile shader programs"""
        vertex_shader = """
        #version 330
        in vec3 in_position;
        uniform mat4 mvp;
        uniform mat4 model;
        out vec3 frag_position;
        void main() {
            frag_position = (model * vec4(in_position, 1.0)).xyz;
            gl_Position = mvp * vec4(in_position, 1.0);
        }
        """
        
        fragment_shader = """
        #version 330
        in vec3 frag_position;
        uniform vec3 color;
        uniform vec3 light_position;
        out vec4 out_color;
        void main() {
            vec3 normal = normalize(cross(dFdx(frag_position), dFdy(frag_position)));
            vec3 light_dir = normalize(light_position - frag_position);
            float diffuse = max(dot(normal, light_dir), 0.0);
            vec3 ambient = color * 0.2;
            vec3 diffuse_color = color * diffuse * 0.8;
            out_color = vec4(ambient + diffuse_color, 1.0);
        }
        """
        
        self.prog = self.ctx.program(
            vertex_shader=vertex_shader,
            fragment_shader=fragment_shader
        )
    
    def render(self, width: int, height: int):
        """Render the scene"""
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.clear(0.1, 0.1, 0.12)
        
        # Camera setup
        aspect = width / height
        proj = Matrix44.perspective_projection(45.0, aspect, 0.1, 100.0)
        view = Matrix44.look_at(Vector3([6.0, 6.0, 6.0]), Vector3([0.0, 0.0, 0.0]), Vector3([0.0, 1.0, 0.0]))
        proj_view = proj * view
        
        self.vao = self.ctx.simple_vertex_array(self.prog, self.vbo, 'in_position')
        
        # Render tabletop
        tt = self.shapes.tabletop
        model_tt = Matrix44.from_translation(tt.position.to_list()) * Matrix44.from_scale(tt.size.to_list())
        mvp_tt = proj_view * model_tt
        
        self.prog['mvp'].write(mvp_tt.astype('f4').tobytes())
        self.prog['model'].write(model_tt.astype('f4').tobytes())
        self.prog['color'].value = (0.82, 0.6, 0.4)
        self.prog['light_position'].value = self.shapes.light_pos.to_list()
        self.vao.render()
        
        # Render legs
        for leg in self.shapes.legs:
            angles = self.joint_angles[leg.key]
            rx, ry, rz = math.radians(angles['x']), math.radians(angles['y']), math.radians(angles['z'])
            
            model_leg = (Matrix44.from_translation(self.shapes.tabletop.position.to_list()) *
                        Matrix44.from_translation([leg.offset.x, 0.0, leg.offset.z]) *
                        Matrix44.from_z_rotation(rz) * Matrix44.from_y_rotation(ry) * Matrix44.from_x_rotation(rx) *
                        Matrix44.from_translation([0.0, -leg.size.y/2.0, 0.0]) * Matrix44.from_scale(leg.size.to_list()))
            
            mvp_leg = proj_view * model_leg
            self.prog['mvp'].write(mvp_leg.astype('f4').tobytes())
            self.prog['model'].write(model_leg.astype('f4').tobytes())
            
            if leg.key == self.selected_leg:
                self.prog['color'].value = (0.98, 0.65, 0.25)
            else:
                self.prog['color'].value = (0.45, 0.38, 0.33)
            
            self.vao.render()
    
    def rotate_selected(self, axis: str, degrees: float):
        if not self.selected_leg:
            return
        
        limits = self.joints.get(self.selected_leg, {}).get(axis, {'min': -360.0, 'max': 360.0})
        current = self.joint_angles[self.selected_leg][axis]
        new_angle = max(limits['min'], min(limits['max'], current + degrees))
        self.joint_angles[self.selected_leg][axis] = new_angle
    
    def reset_joints(self):
        for leg_key in self.joint_angles:
            self.joint_angles[leg_key] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
    
    def select_next_leg(self):
        if not self.shapes.legs:
            return
        keys = [leg.key for leg in self.shapes.legs]
        if not self.selected_leg or self.selected_leg not in keys:
            self.selected_leg = keys[0]
        else:
            idx = keys.index(self.selected_leg)
            self.selected_leg = keys[(idx + 1) % len(keys)]

class TableWindow(pyglet.window.Window):
    def __init__(self, shapes_config: ShapesConfig, joints_config: dict):
        super().__init__(width=900, height=640, caption="Table Project - EGL/Mesa", resizable=True)
        
        self.ctx = moderngl.create_context()
        self.renderer = TableRenderer(self.ctx, shapes_config, joints_config)
        
        # Print OpenGL info
        from OpenGL import GL
        vendor = GL.glGetString(GL.GL_VENDOR)
        renderer_str = GL.glGetString(GL.GL_RENDERER)
        version = GL.glGetString(GL.GL_VERSION)
        
        print("OpenGL Info:")
        print(f"  Vendor: {vendor.decode() if vendor else 'Unknown'}")
        print(f"  Renderer: {renderer_str.decode() if renderer_str else 'Unknown'}")
        print(f"  Version: {version.decode() if version else 'Unknown'}")
        
        pyglet.clock.schedule_interval(self.update, 1/60.0)
    
    def update(self, dt):
        pass
    
    def on_draw(self):
        self.clear()
        width, height = self.get_framebuffer_size()
        self.ctx.viewport = (0, 0, width, height)
        self.renderer.render(width, height)
    
    def on_key_press(self, symbol, modifiers):
        if symbol in (key.Q, key.ESCAPE):
            print("Exiting...")
            self.close()
            pyglet.app.exit()
        
        elif symbol == key.N:
            self.renderer.select_next_leg()
            print(f"Selected: {self.renderer.selected_leg}")
        
        elif symbol == key.R:
            self.renderer.reset_joints()
            print("Reset all joints")
        
        elif symbol in (key.X, key.Y, key.Z):
            axis = chr(symbol).lower()
            delta = -5.0 if (modifiers & key.MOD_SHIFT) else 5.0
            self.renderer.rotate_selected(axis, delta)
            if self.renderer.selected_leg:
                angles = self.renderer.joint_angles[self.renderer.selected_leg]
                print(f"Rotated {self.renderer.selected_leg} {axis}: {angles[axis]:.1f}°")
    
    def on_resize(self, width, height):
        super().on_resize(width, height)
        self.ctx.viewport = (0, 0, width, height)

def main():
    if len(sys.argv) != 3:
        print("Usage: python main_fixed.py shapes.json joints.json")
        sys.exit(1)
    
    try:
        shapes_config, joints_config = load_configuration(sys.argv[1], sys.argv[2])
        window = TableWindow(shapes_config, joints_config)
        
        print("\nControls:")
        print("  N: Select next leg")
        print("  X/Y/Z: Rotate selected leg (+5°)")
        print("  Shift+X/Y/Z: Rotate selected leg (-5°)")
        print("  R: Reset all joint angles")
        print("  Q/ESC: Quit")
        
        pyglet.app.run()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
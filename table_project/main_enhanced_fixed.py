#!/usr/bin/env python3
"""
main_enhanced_fixed.py - Table project with mouse controls and compatible shaders
"""

import os
import sys

# === APPLY THE SAME FIXES THAT WORKED ===
scripts_dir = os.path.dirname(sys.executable)
current_dir = os.path.dirname(os.path.abspath(__file__))

if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(scripts_dir)
    os.add_dll_directory(current_dir)

os.environ['PATH'] = scripts_dir + os.pathsep + current_dir + os.pathsep + os.environ['PATH']
os.environ["PYGLET_GL_LIB"] = "EGL"
os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"
os.environ["MESA_GLSL_VERSION_OVERRIDE"] = "330"

import json
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
import pyglet
from pyglet.window import key, mouse
import moderngl
from moderngl import Context, Program, Buffer, VertexArray
from pyrr import Matrix44, Vector3

# =============================================================================
# Enhanced Data Models with Adjustable Properties
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
    original_size: Vector3D = field(init=False)
    
    def __post_init__(self):
        self.original_size = Vector3D(self.size.x, self.size.y, self.size.z)
    
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

# =============================================================================
# Arcball Camera Controller
# =============================================================================

class ArcballCamera:
    """Arcball camera for 3D navigation with mouse controls"""
    
    def __init__(self, window_width: int, window_height: int):
        self.window_size = (window_width, window_height)
        
        # Camera parameters
        self.distance = 12.0
        self.min_distance = 3.0
        self.max_distance = 30.0
        
        # Rotation (spherical coordinates)
        self.azimuth = math.radians(45.0)  # Horizontal angle
        self.elevation = math.radians(30.0)  # Vertical angle
        self.min_elevation = math.radians(-89.0)
        self.max_elevation = math.radians(89.0)
        
        # Mouse state
        self.is_rotating = False
        self.last_mouse_pos = (0, 0)
        
        # Target point to orbit around
        self.target = Vector3([0.0, 1.5, 0.0])
    
    def get_view_matrix(self) -> Matrix44:
        """Calculate view matrix based on current camera state"""
        # Calculate eye position from spherical coordinates
        eye_x = self.distance * math.cos(self.elevation) * math.sin(self.azimuth)
        eye_y = self.distance * math.sin(self.elevation)
        eye_z = self.distance * math.cos(self.elevation) * math.cos(self.azimuth)
        
        eye = Vector3([eye_x, eye_y, eye_z]) + self.target
        up = Vector3([0.0, 1.0, 0.0])
        
        return Matrix44.look_at(eye, self.target, up)
    
    def get_eye_position(self) -> Vector3:
        """Get current camera eye position"""
        eye_x = self.distance * math.cos(self.elevation) * math.sin(self.azimuth)
        eye_y = self.distance * math.sin(self.elevation)
        eye_z = self.distance * math.cos(self.elevation) * math.cos(self.azimuth)
        return Vector3([eye_x, eye_y, eye_z]) + self.target
    
    def handle_mouse_drag(self, x: int, y: int, dx: int, dy: int, button: int):
        """Handle mouse drag for camera rotation"""
        if button == mouse.RIGHT or (button == mouse.LEFT and self.is_rotating):
            # Convert pixel movement to rotation angles
            sensitivity = 0.01
            self.azimuth -= dx * sensitivity
            self.elevation += dy * sensitivity
            
            # Clamp elevation to avoid flipping
            self.elevation = max(self.min_elevation, min(self.max_elevation, self.elevation))
    
    def handle_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        """Handle mouse scroll for zooming"""
        zoom_sensitivity = 1.2
        if scroll_y > 0:
            self.distance /= zoom_sensitivity
        elif scroll_y < 0:
            self.distance *= zoom_sensitivity
        
        self.distance = max(self.min_distance, min(self.max_distance, self.distance))
    
    def handle_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        """Handle mouse button press"""
        if button == mouse.LEFT and modifiers & key.MOD_CTRL:
            self.is_rotating = True
            self.last_mouse_pos = (x, y)
        elif button == mouse.RIGHT:
            self.is_rotating = True
            self.last_mouse_pos = (x, y)
    
    def handle_mouse_release(self, x: int, y: int, button: int, modifiers: int):
        """Handle mouse button release"""
        if button in (mouse.LEFT, mouse.RIGHT):
            self.is_rotating = False

# =============================================================================
# Enhanced Table Renderer with Compatible Shaders
# =============================================================================

class EnhancedTableRenderer:
    def __init__(self, ctx: Context, shapes: ShapesConfig, joints: Dict[str, Any]):
        self.ctx = ctx
        self.shapes = shapes
        self.joints = joints
        
        # Initialize joint angles
        self.joint_angles = {leg.key: {'x': 0.0, 'y': 0.0, 'z': 0.0} for leg in shapes.legs}
        self.selected_leg = shapes.legs[0].key if shapes.legs else None
        
        # Tabletop adjustment
        self.tabletop_scale = Vector3([1.0, 1.0, 1.0])
        self.leg_scale = Vector3([1.0, 1.0, 1.0])
        
        # Create GPU resources
        self.setup_geometry()
        self.setup_shaders()
        
        print("✅ Enhanced table renderer initialized!")
    
    def setup_geometry(self):
        """Setup vertex buffers with positions and normals"""
        # Create cube vertices with pre-computed normals
        # Each face has its own normal
        vertices = []
        normals = []
        
        # Front face (Z+)
        face_vertices = [
            -0.5, -0.5,  0.5,  0.5, -0.5,  0.5,  0.5,  0.5,  0.5,
            -0.5, -0.5,  0.5,  0.5,  0.5,  0.5, -0.5,  0.5,  0.5,
        ]
        face_normal = [0.0, 0.0, 1.0]  # Z+
        vertices.extend(face_vertices)
        normals.extend(face_normal * 6)  # 6 vertices per face
        
        # Back face (Z-)
        face_vertices = [
            -0.5, -0.5, -0.5, -0.5,  0.5, -0.5,  0.5,  0.5, -0.5,
            -0.5, -0.5, -0.5,  0.5,  0.5, -0.5,  0.5, -0.5, -0.5,
        ]
        face_normal = [0.0, 0.0, -1.0]  # Z-
        vertices.extend(face_vertices)
        normals.extend(face_normal * 6)
        
        # Left face (X-)
        face_vertices = [
            -0.5, -0.5, -0.5, -0.5, -0.5,  0.5, -0.5,  0.5,  0.5,
            -0.5, -0.5, -0.5, -0.5,  0.5,  0.5, -0.5,  0.5, -0.5,
        ]
        face_normal = [-1.0, 0.0, 0.0]  # X-
        vertices.extend(face_vertices)
        normals.extend(face_normal * 6)
        
        # Right face (X+)
        face_vertices = [
            0.5, -0.5, -0.5,  0.5,  0.5, -0.5,  0.5,  0.5,  0.5,
            0.5, -0.5, -0.5,  0.5,  0.5,  0.5,  0.5, -0.5,  0.5,
        ]
        face_normal = [1.0, 0.0, 0.0]  # X+
        vertices.extend(face_vertices)
        normals.extend(face_normal * 6)
        
        # Top face (Y+)
        face_vertices = [
            -0.5,  0.5, -0.5, -0.5,  0.5,  0.5,  0.5,  0.5,  0.5,
            -0.5,  0.5, -0.5,  0.5,  0.5,  0.5,  0.5,  0.5, -0.5,
        ]
        face_normal = [0.0, 1.0, 0.0]  # Y+
        vertices.extend(face_vertices)
        normals.extend(face_normal * 6)
        
        # Bottom face (Y-)
        face_vertices = [
            -0.5, -0.5, -0.5,  0.5, -0.5, -0.5,  0.5, -0.5,  0.5,
            -0.5, -0.5, -0.5,  0.5, -0.5,  0.5, -0.5, -0.5,  0.5,
        ]
        face_normal = [0.0, -1.0, 0.0]  # Y-
        vertices.extend(face_vertices)
        normals.extend(face_normal * 6)
        
        # Convert to numpy arrays
        vertices = np.array(vertices, dtype='f4')
        normals = np.array(normals, dtype='f4')
        
        # Interleave vertices and normals
        interleaved = np.empty((len(vertices) // 3, 6), dtype='f4')
        interleaved[:, 0:3] = vertices.reshape(-1, 3)
        interleaved[:, 3:6] = normals.reshape(-1, 3)
        
        self.vbo = self.ctx.buffer(interleaved.tobytes())
        self.vao = None
    
    def setup_shaders(self):
        """Compile compatible shader programs (no dFdx/dFdy)"""
        vertex_shader = """
        #version 330
        in vec3 in_position;
        in vec3 in_normal;
        uniform mat4 mvp;
        uniform mat4 model;
        out vec3 frag_position;
        out vec3 frag_normal;
        
        void main() {
            frag_position = (model * vec4(in_position, 1.0)).xyz;
            frag_normal = normalize(mat3(model) * in_normal);
            gl_Position = mvp * vec4(in_position, 1.0);
        }
        """
        
        fragment_shader = """
        #version 330
        in vec3 frag_position;
        in vec3 frag_normal;
        uniform vec3 color;
        uniform vec3 light_position;
        uniform vec3 view_position;
        out vec4 out_color;
        
        void main() {
            // Simple lighting without derivative functions
            vec3 normal = normalize(frag_normal);
            vec3 light_dir = normalize(light_position - frag_position);
            
            // Ambient
            vec3 ambient = color * 0.3;
            
            // Diffuse
            float diff = max(dot(normal, light_dir), 0.0);
            vec3 diffuse = diff * color * 0.7;
            
            // Simple specular (optional)
            vec3 view_dir = normalize(view_position - frag_position);
            vec3 reflect_dir = reflect(-light_dir, normal);
            float spec = pow(max(dot(view_dir, reflect_dir), 0.0), 16.0);
            vec3 specular = spec * vec3(0.2);
            
            out_color = vec4(ambient + diffuse + specular, 1.0);
        }
        """
        
        self.prog = self.ctx.program(
            vertex_shader=vertex_shader,
            fragment_shader=fragment_shader
        )
    
    def render(self, width: int, height: int, camera: ArcballCamera):
        """Render the scene with camera"""
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.clear(0.1, 0.1, 0.15)
        
        # Camera setup
        aspect = width / max(1.0, height)
        proj = Matrix44.perspective_projection(45.0, aspect, 0.1, 100.0)
        view = camera.get_view_matrix()
        proj_view = proj * view
        
        # Create vertex array with both position and normal attributes
        self.vao = self.ctx.vertex_array(
            self.prog,
            [
                (self.vbo, '3f 3f', 'in_position', 'in_normal')
            ]
        )
        
        # Get eye position for lighting
        eye_pos = camera.get_eye_position()
        self.prog['view_position'].value = tuple(eye_pos)
        self.prog['light_position'].value = self.shapes.light_pos.to_list()
        
        # Render tabletop with adjustable scale
        tt = self.shapes.tabletop
        scaled_size = [
            tt.size.x * self.tabletop_scale.x,
            tt.size.y * self.tabletop_scale.y, 
            tt.size.z * self.tabletop_scale.z
        ]
        
        model_tt = (Matrix44.from_translation(tt.position.to_list()) * 
                   Matrix44.from_scale(scaled_size))
        mvp_tt = proj_view * model_tt
        
        self.prog['mvp'].write(mvp_tt.astype('f4').tobytes())
        self.prog['model'].write(model_tt.astype('f4').tobytes())
        self.prog['color'].value = (0.82, 0.6, 0.4)  # Wood color
        self.vao.render()
        
        # Render legs with adjustable scale
        for leg in self.shapes.legs:
            angles = self.joint_angles[leg.key]
            rx, ry, rz = math.radians(angles['x']), math.radians(angles['y']), math.radians(angles['z'])
            
            # Apply tabletop scale to leg positions (so they stay at corners)
            scaled_offset = [
                leg.offset.x * self.tabletop_scale.x,
                leg.offset.y * self.tabletop_scale.y,
                leg.offset.z * self.tabletop_scale.z
            ]
            
            # Apply leg scale to leg size
            scaled_leg_size = [
                leg.size.x * self.leg_scale.x,
                leg.size.y * self.leg_scale.y,
                leg.size.z * self.leg_scale.z
            ]
            
            model_leg = (Matrix44.from_translation(self.shapes.tabletop.position.to_list()) *
                        Matrix44.from_translation(scaled_offset) *
                        Matrix44.from_z_rotation(rz) * Matrix44.from_y_rotation(ry) * Matrix44.from_x_rotation(rx) *
                        Matrix44.from_translation([0.0, -scaled_leg_size[1]/2.0, 0.0]) * 
                        Matrix44.from_scale(scaled_leg_size))
            
            mvp_leg = proj_view * model_leg
            self.prog['mvp'].write(mvp_leg.astype('f4').tobytes())
            self.prog['model'].write(model_leg.astype('f4').tobytes())
            
            if leg.key == self.selected_leg:
                self.prog['color'].value = (0.98, 0.65, 0.25)  # Highlight
            else:
                self.prog['color'].value = (0.45, 0.38, 0.33)  # Normal
            
            self.vao.render()
    
    # Tabletop adjustment methods
    def adjust_tabletop_size(self, axis: str, delta: float):
        """Adjust tabletop size along specific axis"""
        if axis == 'x':
            self.tabletop_scale.x = max(0.5, min(3.0, self.tabletop_scale.x + delta))
        elif axis == 'y':
            self.tabletop_scale.y = max(0.5, min(3.0, self.tabletop_scale.y + delta))
        elif axis == 'z':
            self.tabletop_scale.z = max(0.5, min(3.0, self.tabletop_scale.z + delta))
    
    def adjust_leg_size(self, axis: str, delta: float):
        """Adjust leg size along specific axis"""
        if axis == 'x':
            self.leg_scale.x = max(0.3, min(2.0, self.leg_scale.x + delta))
        elif axis == 'y':
            self.leg_scale.y = max(0.3, min(2.0, self.leg_scale.y + delta))
        elif axis == 'z':
            self.leg_scale.z = max(0.3, min(2.0, self.leg_scale.z + delta))
    
    def reset_tabletop(self):
        """Reset tabletop to original size"""
        self.tabletop_scale = Vector3([1.0, 1.0, 1.0])
        self.leg_scale = Vector3([1.0, 1.0, 1.0])
    
    # Existing leg control methods
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

# =============================================================================
# Enhanced Window with Mouse Controls
# =============================================================================

class EnhancedTableWindow(pyglet.window.Window):
    def __init__(self, shapes_config: ShapesConfig, joints_config: dict):
        super().__init__(width=1000, height=700, caption="3D Table - Mouse Controls", resizable=True)
        
        self.ctx = moderngl.create_context()
        self.camera = ArcballCamera(self.width, self.height)
        self.renderer = EnhancedTableRenderer(self.ctx, shapes_config, joints_config)
        
        # UI state
        self.show_help = True
        self.help_display_time = 5.0  # Show help for 5 seconds
        
        # Set up event scheduling
        pyglet.clock.schedule_interval(self.update, 1/60.0)
        
        print("🎮 Enhanced table window initialized!")
        self.print_controls()
    
    def print_controls(self):
        """Print control instructions"""
        print("\n" + "="*60)
        print("🎮 MOUSE CONTROLS:")
        print("="*60)
        print("Right-click + drag: Rotate camera around table")
        print("Mouse wheel: Zoom in/out")
        print("Ctrl + Left-click + drag: Also rotate camera")
        print("\n⌨️  KEYBOARD CONTROLS:")
        print("N: Select next leg")
        print("X/Y/Z: Rotate selected leg (+5°)")
        print("Shift+X/Y/Z: Rotate selected leg (-5°)")
        print("R: Reset all joint angles")
        print("T: Reset tabletop size")
        print("1/2: Increase/decrease tabletop WIDTH (X)")
        print("3/4: Increase/decrease tabletop HEIGHT (Y)")
        print("5/6: Increase/decrease tabletop DEPTH (Z)")
        print("7/8: Increase/decrease leg WIDTH (X)")
        print("9/0: Increase/decrease leg HEIGHT (Y)")
        print("-/=: Increase/decrease leg DEPTH (Z)")
        print("H: Toggle help display")
        print("Q/ESC: Quit")
        print("="*60)
    
    def update(self, dt):
        """Update game state"""
        self.help_display_time -= dt
        if self.help_display_time < 0:
            self.show_help = False
    
    def on_draw(self):
        """Render the scene"""
        self.clear()
        width, height = self.get_framebuffer_size()
        self.ctx.viewport = (0, 0, width, height)
        
        # Update camera window size if resized
        if (width, height) != self.camera.window_size:
            self.camera.window_size = (width, height)
        
        self.renderer.render(width, height, self.camera)
        
        # Display help text
        if self.show_help:
            self.draw_help_text()
    
    def draw_help_text(self):
        """Draw help text on screen"""
        help_text = [
            "CONTROLS:",
            "Right-click + drag: Rotate camera",
            "Mouse wheel: Zoom",
            "N: Next leg, X/Y/Z: Rotate leg",
            "1-6: Adjust tabletop, 7-0: Adjust legs",
            "H: Hide help"
        ]
        
        batch = pyglet.graphics.Batch()
        labels = []
        
        for i, text in enumerate(help_text):
            label = pyglet.text.Label(
                text, font_size=12, x=10, y=self.height - 30 - i*20,
                color=(255, 255, 255, 255), batch=batch
            )
            labels.append(label)
        
        batch.draw()
    
    # Mouse event handlers
    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.camera.handle_mouse_drag(x, y, dx, dy, buttons)
    
    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera.handle_mouse_scroll(x, y, scroll_x, scroll_y)
    
    def on_mouse_press(self, x, y, button, modifiers):
        self.camera.handle_mouse_press(x, y, button, modifiers)
    
    def on_mouse_release(self, x, y, button, modifiers):
        self.camera.handle_mouse_release(x, y, button, modifiers)
    
    # Keyboard event handlers
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
            print("Reset all joint angles")
        
        elif symbol == key.T:
            self.renderer.reset_tabletop()
            print("Reset tabletop to original size")
        
        elif symbol == key.H:
            self.show_help = not self.show_help
            print("Help display:", "ON" if self.show_help else "OFF")
        
        # Tabletop adjustment keys
        elif symbol == key._1:  # Increase tabletop width
            self.renderer.adjust_tabletop_size('x', 0.1)
            print(f"Tabletop width: {self.renderer.tabletop_scale.x:.1f}")
        
        elif symbol == key._2:  # Decrease tabletop width
            self.renderer.adjust_tabletop_size('x', -0.1)
            print(f"Tabletop width: {self.renderer.tabletop_scale.x:.1f}")
        
        elif symbol == key._3:  # Increase tabletop height
            self.renderer.adjust_tabletop_size('y', 0.1)
            print(f"Tabletop height: {self.renderer.tabletop_scale.y:.1f}")
        
        elif symbol == key._4:  # Decrease tabletop height
            self.renderer.adjust_tabletop_size('y', -0.1)
            print(f"Tabletop height: {self.renderer.tabletop_scale.y:.1f}")
        
        elif symbol == key._5:  # Increase tabletop depth
            self.renderer.adjust_tabletop_size('z', 0.1)
            print(f"Tabletop depth: {self.renderer.tabletop_scale.z:.1f}")
        
        elif symbol == key._6:  # Decrease tabletop depth
            self.renderer.adjust_tabletop_size('z', -0.1)
            print(f"Tabletop depth: {self.renderer.tabletop_scale.z:.1f}")
        
        # Leg adjustment keys
        elif symbol == key._7:  # Increase leg width
            self.renderer.adjust_leg_size('x', 0.1)
            print(f"Leg width: {self.renderer.leg_scale.x:.1f}")
        
        elif symbol == key._8:  # Decrease leg width
            self.renderer.adjust_leg_size('x', -0.1)
            print(f"Leg width: {self.renderer.leg_scale.x:.1f}")
        
        elif symbol == key._9:  # Increase leg height
            self.renderer.adjust_leg_size('y', 0.1)
            print(f"Leg height: {self.renderer.leg_scale.y:.1f}")
        
        elif symbol == key._0:  # Decrease leg height
            self.renderer.adjust_leg_size('y', -0.1)
            print(f"Leg height: {self.renderer.leg_scale.y:.1f}")
        
        elif symbol == key.MINUS:  # Increase leg depth
            self.renderer.adjust_leg_size('z', 0.1)
            print(f"Leg depth: {self.renderer.leg_scale.z:.1f}")
        
        elif symbol == key.EQUAL:  # Decrease leg depth
            self.renderer.adjust_leg_size('z', -0.1)
            print(f"Leg depth: {self.renderer.leg_scale.z:.1f}")
        
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

def load_configuration(shapes_path: str, joints_path: str):
    """Load and validate configuration files"""
    with open(shapes_path, 'r', encoding='utf-8') as f:
        shapes_data = json.load(f)
    with open(joints_path, 'r', encoding='utf-8') as f:
        joints_data = json.load(f)
    
    shapes_config = ShapesConfig.from_dict(shapes_data)
    print(f"Loaded configuration: {len(shapes_config.legs)} legs")
    return shapes_config, joints_data

def main():
    if len(sys.argv) != 3:
        print("Usage: python main_enhanced_fixed.py shapes.json joints.json")
        sys.exit(1)
    
    try:
        shapes_config, joints_config = load_configuration(sys.argv[1], sys.argv[2])
        window = EnhancedTableWindow(shapes_config, joints_config)
        pyglet.app.run()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
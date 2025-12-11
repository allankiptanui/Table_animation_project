# renderer.py
"""
Table rendering and GPU resource management.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

import moderngl
from moderngl import Context, Program, Buffer, VertexArray, Framebuffer
from pyrr import Matrix44, Vector3

from models import ShapesConfig, Vector3D, LegConfig  # Changed from types to models
from shaders import VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC, PICKING_SHADER_SRC
from utilities import create_cube_geometry

# ... rest of renderer.py remains the same ..._geometry

class GPUResourceManager:
    """Manages GPU resource lifecycle with proper cleanup"""
    
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self._resources: List[Any] = []
    
    @contextmanager
    def buffer(self, data: bytes, **kwargs: Any) -> Buffer:
        """Context manager for buffer creation and cleanup"""
        buffer = self.ctx.buffer(data, **kwargs)
        self._resources.append(buffer)
        try:
            yield buffer
        except Exception:
            buffer.release()
            raise
    
    @contextmanager
    def program(self, vertex_shader: str, fragment_shader: str) -> Program:
        """Context manager for shader program creation"""
        prog = self.ctx.program(
            vertex_shader=vertex_shader,
            fragment_shader=fragment_shader
        )
        self._resources.append(prog)
        try:
            yield prog
        except Exception:
            prog.release()
            raise
    
    def cleanup(self) -> None:
        """Release all managed resources"""
        for resource in self._resources:
            if hasattr(resource, 'release'):
                resource.release()
        self._resources.clear()

class TableRenderer:
    """Handles rendering of the table hierarchy"""
    
    def __init__(self, ctx: Context, shapes: ShapesConfig, joints: Dict[str, Any]) -> None:
        self.ctx = ctx
        self.shapes = shapes
        self.joints = joints
        self.resources = GPUResourceManager(ctx)
        
        # Initialize joint angles
        self.joint_angles: Dict[str, Dict[str, float]] = {}
        for leg in shapes.legs:
            self.joint_angles[leg.key] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        
        self.selected_leg: Optional[str] = shapes.legs[0].key if shapes.legs else None
        self.pick_map: Dict[int, str] = {}
        
        # Create GPU resources
        self._setup_geometry()
        self._setup_shaders()
        self.pick_fbo: Optional[Framebuffer] = None
    
    def _setup_geometry(self) -> None:
        """Setup vertex buffers and arrays"""
        cube_data = create_cube_geometry()
        
        with self.resources.buffer(cube_data) as vbo:
            self.vbo = vbo
        
        self.vao: Optional[VertexArray] = None
    
    def _setup_shaders(self) -> None:
        """Compile shader programs"""
        with self.resources.program(VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC) as prog:
            self.main_program = prog
        
        with self.resources.program(VERTEX_SHADER_SRC, PICKING_SHADER_SRC) as prog:
            self.pick_program = prog
    
    def _ensure_pick_fbo(self, width: int, height: int) -> Framebuffer:
        """Ensure picking framebuffer exists and is correct size"""
        if self.pick_fbo is None or self.pick_fbo.size != (width, height):
            if self.pick_fbo:
                self.pick_fbo.release()
            self.pick_fbo = self.ctx.simple_framebuffer((width, height))
        return self.pick_fbo
    
    def _get_camera_matrices(self, width: int, height: int) -> Tuple[Matrix44, Matrix44, Vector3]:
        """Calculate projection and view matrices"""
        aspect = width / max(1.0, height)
        proj = Matrix44.perspective_projection(45.0, aspect, 0.1, 100.0)
        eye = Vector3([6.0, 6.0, 6.0])
        target = Vector3([0.0, 0.0, 0.0])
        up = Vector3([0.0, 1.0, 0.0])
        view = Matrix44.look_at(eye, target, up)
        return proj, view, eye
    
    def _create_leg_transform(self, leg: LegConfig) -> Matrix44:
        """Create transformation matrix for a leg"""
        angles = self.joint_angles[leg.key]
        rx = math.radians(angles['x'])
        ry = math.radians(angles['y']) 
        rz = math.radians(angles['z'])
        
        table_pos = self.shapes.tabletop.position
        
        transform = (Matrix44.from_translation(table_pos.to_list()) *
                    Matrix44.from_translation([leg.offset.x, 0.0, leg.offset.z]) *
                    Matrix44.from_z_rotation(rz) *
                    Matrix44.from_y_rotation(ry) * 
                    Matrix44.from_x_rotation(rx) *
                    Matrix44.from_translation([0.0, -leg.size.y / 2.0, 0.0]) *
                    Matrix44.from_scale(leg.size.to_list()))
        
        return transform
    
    def render(self, width: int, height: int) -> None:
        """Render the main scene"""
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.clear(0.1, 0.1, 0.12)
        
        proj, view, eye = self._get_camera_matrices(width, height)
        proj_view = proj * view
        
        self.vao = self.ctx.simple_vertex_array(self.main_program, self.vbo, 'in_position')
        
        # Render tabletop
        tt = self.shapes.tabletop
        model_tt = (Matrix44.from_translation(tt.position.to_list()) *
                   Matrix44.from_scale(tt.size.to_list()))
        mvp_tt = proj_view * model_tt
        
        self.main_program['mvp'].write(mvp_tt.astype('f4').tobytes())
        self.main_program['model'].write(model_tt.astype('f4').tobytes())
        self.main_program['color'].value = (0.82, 0.6, 0.4)
        self.main_program['light_position'].value = self.shapes.light_pos.to_list()
        
        if self.vao:
            self.vao.render()
        
        # Render legs
        for idx, leg in enumerate(self.shapes.legs, 1):
            model_leg = self._create_leg_transform(leg)
            mvp_leg = proj_view * model_leg
            
            self.main_program['mvp'].write(mvp_leg.astype('f4').tobytes())
            self.main_program['model'].write(model_leg.astype('f4').tobytes())
            self.main_program['light_position'].value = self.shapes.light_pos.to_list()
            
            if leg.key == self.selected_leg:
                self.main_program['color'].value = (0.98, 0.65, 0.25)
            else:
                self.main_program['color'].value = (0.45, 0.38, 0.33)
            
            if self.vao:
                self.vao.render()
    
    def pick(self, x: int, y: int, width: int, height: int) -> Optional[str]:
        """Perform color-based picking at screen coordinates"""
        if not self.shapes.legs:
            return None
        
        fbo = self._ensure_pick_fbo(width, height)
        fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 0.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        
        proj, view, eye = self._get_camera_matrices(width, height)
        proj_view = proj * view
        
        self.vao = self.ctx.simple_vertex_array(self.pick_program, self.vbo, 'in_position')
        self.pick_map.clear()
        
        # Render tabletop (black = not pickable)
        tt = self.shapes.tabletop
        model_tt = (Matrix44.from_translation(tt.position.to_list()) *
                   Matrix44.from_scale(tt.size.to_list()))
        mvp_tt = proj_view * model_tt
        
        self.pick_program['mvp'].write(mvp_tt.astype('f4').tobytes())
        self.pick_program['model'].write(model_tt.astype('f4').tobytes())
        self.pick_program['pick_color'].value = (0.0, 0.0, 0.0)
        
        if self.vao:
            self.vao.render()
        
        # Render legs with unique colors
        for idx, leg in enumerate(self.shapes.legs, 1):
            model_leg = self._create_leg_transform(leg)
            mvp_leg = proj_view * model_leg
            
            self.pick_program['mvp'].write(mvp_leg.astype('f4').tobytes())
            self.pick_program['model'].write(model_leg.astype('f4').tobytes())
            
            r = ((idx >> 0) & 0xFF) / 255.0
            g = ((idx >> 8) & 0xFF) / 255.0
            b = ((idx >> 16) & 0xFF) / 255.0
            
            self.pick_program['pick_color'].value = (r, g, b)
            self.pick_map[idx] = leg.key
            
            if self.vao:
                self.vao.render()
        
        pixel_data = fbo.read(viewport=(x, y, 1, 1), components=3)
        r, g, b = pixel_data[0], pixel_data[1], pixel_data[2]
        pick_id = r + (g << 8) + (b << 16)
        
        self.ctx.screen.use()
        
        return self.pick_map.get(pick_id, None)
    
    def rotate_selected(self, axis: str, degrees: float) -> None:
        """Rotate selected leg around specified axis"""
        if not self.selected_leg:
            return
        
        limits = self.joints.get(self.selected_leg, {}).get(axis, {'min': -360.0, 'max': 360.0})
        min_limit = limits.get('min', -360.0)
        max_limit = limits.get('max', 360.0)
        
        current = self.joint_angles[self.selected_leg][axis]
        new_angle = max(min_limit, min(max_limit, current + degrees))
        self.joint_angles[self.selected_leg][axis] = new_angle
    
    def reset_joints(self) -> None:
        """Reset all joint angles to zero"""
        for leg_key in self.joint_angles:
            self.joint_angles[leg_key] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
    
    def select_next_leg(self) -> None:
        """Select next leg in sequence"""
        if not self.shapes.legs:
            return
        
        keys = [leg.key for leg in self.shapes.legs]
        if not self.selected_leg or self.selected_leg not in keys:
            self.selected_leg = keys[0]
            return
        
        current_idx = keys.index(self.selected_leg)
        next_idx = (current_idx + 1) % len(keys)
        self.selected_leg = keys[next_idx]
    
    def select_previous_leg(self) -> None:
        """Select previous leg in sequence"""
        if not self.shapes.legs:
            return
        
        keys = [leg.key for leg in self.shapes.legs]
        if not self.selected_leg or self.selected_leg not in keys:
            self.selected_leg = keys[0]
            return
        
        current_idx = keys.index(self.selected_leg)
        prev_idx = (current_idx - 1) % len(keys)
        self.selected_leg = keys[prev_idx]
    
    def cleanup(self) -> None:
        """Clean up all GPU resources"""
        if self.vao:
            self.vao.release()
        if self.pick_fbo:
            self.pick_fbo.release()
        self.resources.cleanup()
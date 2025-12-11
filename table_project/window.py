# window.py
"""
Main application window and event handling.
"""

import os
import pyglet
from pyglet.window import key, mouse

from models import ShapesConfig  # Changed from types to models
from renderer import TableRenderer

# ... rest of window.py remains the same ...

# Platform-specific OpenGL setup
if os.name == 'posix':
    os.environ.setdefault("PYGLET_GL_LIB", "EGL")
else:
    os.environ.pop("PYGLET_GL_LIB", None)

class TableWindow(pyglet.window.Window):
    """Main application window"""
    
    def __init__(self, shapes_config: ShapesConfig, joints_config: dict) -> None:
        super().__init__(
            width=900, 
            height=640,
            caption="ModernGL Table Project",
            resizable=True,
            config=pyglet.gl.Config(double_buffer=True, depth_size=24)
        )
        
        # Create ModernGL context
        try:
            import moderngl
            self.ctx = moderngl.create_context()
            self.renderer = TableRenderer(self.ctx, shapes_config, joints_config)
        except Exception as e:
            print(f"Failed to create OpenGL context: {e}")
            print("This application requires OpenGL 3.3 support.")
            self.close()
            raise
        
        self._print_gl_info()
        pyglet.clock.schedule_interval(self._update, 1/60.0)
    
    def _print_gl_info(self) -> None:
        """Print OpenGL context information"""
        from OpenGL import GL
        try:
            vendor = GL.glGetString(GL.GL_VENDOR)
            renderer_str = GL.glGetString(GL.GL_RENDERER)
            version = GL.glGetString(GL.GL_VERSION)
            
            print("OpenGL Information:")
            print(f"  Vendor:   {vendor.decode() if vendor else 'Unknown'}")
            print(f"  Renderer: {renderer_str.decode() if renderer_str else 'Unknown'}")
            print(f"  Version:  {version.decode() if version else 'Unknown'}")
        except Exception as e:
            print(f"Could not retrieve OpenGL info: {e}")
    
    def _update(self, dt: float) -> None:
        """Window update callback"""
        pass
    
    def on_draw(self) -> None:
        """Render the scene"""
        self.clear()
        width, height = self.get_framebuffer_size()
        self.ctx.viewport = (0, 0, width, height)
        self.renderer.render(width, height)
    
    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        """Handle mouse clicks for picking"""
        if button == mouse.LEFT:
            width, height = self.get_framebuffer_size()
            pick_y = height - y - 1
            picked = self.renderer.pick(x, pick_y, width, height)
            
            if picked:
                print(f"Selected leg: {picked}")
                self.renderer.selected_leg = picked
            else:
                print("Selected: None (tabletop or background)")
                self.renderer.selected_leg = None
    
    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Handle keyboard input"""
        ROTATION_STEP = 5.0
        
        if symbol in (key.Q, key.ESCAPE):
            print("Exiting application...")
            self.close()
            pyglet.app.exit()
            return
        
        elif symbol == key.N:
            self.renderer.select_next_leg()
            print(f"Selected: {self.renderer.selected_leg}")
        
        elif symbol == key.P:
            self.renderer.select_previous_leg()
            print(f"Selected: {self.renderer.selected_leg}")
        
        elif symbol == key.R:
            self.renderer.reset_joints()
            print("Reset all joint angles")
        
        elif symbol in (key.X, key.Y, key.Z):
            axis = chr(symbol).lower()
            direction = -1.0 if (modifiers & key.MOD_SHIFT) else 1.0
            degrees = ROTATION_STEP * direction
            
            self.renderer.rotate_selected(axis, degrees)
            if self.renderer.selected_leg:
                angles = self.renderer.joint_angles[self.renderer.selected_leg]
                print(f"Rotated {self.renderer.selected_leg} {axis}: {angles[axis]:.1f}°")
    
    def on_resize(self, width: int, height: int) -> None:
        """Handle window resize"""
        super().on_resize(width, height)
        self.ctx.viewport = (0, 0, width, height)
    
    def on_close(self) -> None:
        """Clean up resources on window close"""
        self.renderer.cleanup()
        super().on_close()
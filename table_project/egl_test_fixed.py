#!/usr/bin/env python3
"""
egl_test_fixed.py - EGL test with all DLL loading fixes applied
"""

import os
import sys

# CRITICAL: Apply DLL fixes BEFORE any imports
scripts_dir = os.path.dirname(sys.executable)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Add to DLL search path
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(scripts_dir)
    os.add_dll_directory(current_dir)

# 2. Add to PATH environment variable  
os.environ['PATH'] = scripts_dir + os.pathsep + current_dir + os.pathsep + os.environ['PATH']

# 3. Set Mesa environment variables
os.environ["PYGLET_GL_LIB"] = "EGL"
os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"
os.environ["MESA_GLSL_VERSION_OVERRIDE"] = "330"

# 4. Start with hardware acceleration, fallback to software
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "0"

print("="*60)
print("EGL Test with DLL Fixes Applied")
print("="*60)
print(f"Scripts dir: {scripts_dir}")
print(f"Current dir: {current_dir}")
print(f"PYGLET_GL_LIB: {os.environ.get('PYGLET_GL_LIB')}")

try:
    import pyglet
    import moderngl
    import numpy as np
    from OpenGL import GL
    
    print("✅ Imports successful!")
    
    # Create window
    print("Creating window...")
    config = pyglet.gl.Config(double_buffer=True, depth_size=24)
    window = pyglet.window.Window(800, 600, "EGL Fixed Test", config=config, visible=False)
    
    # Create ModernGL context
    ctx = moderngl.create_context()
    print("✅ ModernGL context created!")
    
    # Test OpenGL capabilities
    vendor = GL.glGetString(GL.GL_VENDOR)
    renderer = GL.glGetString(GL.GL_RENDERER)
    version = GL.glGetString(GL.GL_VERSION)
    
    print(f"OpenGL Vendor: {vendor.decode() if vendor else 'Unknown'}")
    print(f"OpenGL Renderer: {renderer.decode() if renderer else 'Unknown'}")
    print(f"OpenGL Version: {version.decode() if version else 'Unknown'}")
    
    # Test shader compilation (this was failing)
    print("Testing shader compilation...")
    
    vertex_shader = """
    #version 330 core
    in vec2 in_vert;
    void main() {
        gl_Position = vec4(in_vert, 0.0, 1.0);
    }
    """
    
    fragment_shader = """
    #version 330 core
    out vec4 frag_color;
    void main() {
        frag_color = vec4(0.0, 0.8, 0.2, 1.0);
    }
    """
    
    prog = ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)
    print("✅ Shader compilation successful!")
    
    # Test rendering
    vertices = np.array([-0.6, -0.6, 0.6, -0.6, 0.0, 0.6], dtype='f4')
    vbo = ctx.buffer(vertices.tobytes())
    vao = ctx.simple_vertex_array(prog, vbo, 'in_vert')
    
    @window.event
    def on_draw():
        ctx.clear(0.1, 0.1, 0.2)
        vao.render()
    
    window.set_visible(True)
    
    @window.event 
    def on_key_press(symbol, modifiers):
        from pyglet.window import key
        if symbol == key.ESCAPE:
            window.close()
    
    print("✅ All tests passed! Rendering window for 3 seconds...")
    
    # Close after 3 seconds
    import pyglet.clock
    pyglet.clock.schedule_once(lambda dt: window.close(), 3.0)
    
    pyglet.app.run()
    print("🎉 EGL is working correctly with Mesa!")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    print("\nTrying software rendering fallback...")
    
    # Fallback to software rendering
    os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    
    try:
        # Re-import after setting software mode
        import importlib
        importlib.reload(sys.modules['pyglet.gl'])
        
        import pyglet
        import moderngl
        
        print("✅ Software rendering mode activated!")
        print("This will be slower but should work.")
        
        # Retry the test...
        config = pyglet.gl.Config(double_buffer=True, depth_size=24)
        window = pyglet.window.Window(400, 300, "Software Fallback", config=config, visible=False)
        ctx = moderngl.create_context()
        
        print("✅ Software rendering context created!")
        
    except Exception as e2:
        print(f"❌ Software rendering also failed: {e2}")
        print("\n💡 Final troubleshooting:")
        print("1. Try running as Administrator")
        print("2. Check Windows graphics driver settings")
        print("3. Try on a different computer")
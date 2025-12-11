#!/usr/bin/env python3
"""
egl_test.py - Minimal EGL + ModernGL test to verify OpenGL 2.0+ support
"""

import os
import sys

# CRITICAL: Set EGL before any pyglet imports
os.environ["PYGLET_GL_LIB"] = "EGL"

def test_egl_context():
    """Test if we can create a modern OpenGL context"""
    try:
        import pyglet
        from pyglet.window import key
        import moderngl
        from moderngl import Context
        from OpenGL import GL
        
        print("=" * 60)
        print("EGL/Mesa Test Program")
        print("=" * 60)
        
        # Try to create a window with EGL
        print("1. Creating pyglet window with EGL backend...")
        config = pyglet.gl.Config(double_buffer=True, depth_size=24)
        window = pyglet.window.Window(800, 600, "EGL Test", config=config, visible=False)
        
        print("2. Creating ModernGL context...")
        ctx = moderngl.create_context()
        
        print("3. Querying OpenGL information...")
        vendor = GL.glGetString(GL.GL_VENDOR)
        renderer = GL.glGetString(GL.GL_RENDERER)
        version = GL.glGetString(GL.GL_VERSION)
        
        print(f"   Vendor:   {vendor.decode() if vendor else 'Unknown'}")
        print(f"   Renderer: {renderer.decode() if renderer else 'Unknown'}")
        print(f"   Version:  {version.decode() if version else 'Unknown'}")
        
        # Test shader compilation (the failing operation)
        print("4. Testing shader compilation...")
        
        # Minimal shaders
        vertex_shader = """
        #version 330 core
        in vec2 in_vert;
        void main() {
            gl_Position = vec4(in_vert, 0.0, 1.0);
        }
        """
        
        fragment_shader = """
        #version 330 core
        out vec4 fragColor;
        void main() {
            fragColor = vec4(1.0, 0.0, 0.0, 1.0);
        }
        """
        
        # This is where the original error occurs
        prog = ctx.program(
            vertex_shader=vertex_shader,
            fragment_shader=fragment_shader
        )
        print("   ✅ Shader compilation SUCCESSFUL!")
        
        # Test rendering a simple triangle
        print("5. Testing simple geometry rendering...")
        vertices = np.array([-0.6, -0.6, 0.6, -0.6, 0.0, 0.6], dtype='f4')
        vbo = ctx.buffer(vertices)
        vao = ctx.simple_vertex_array(prog, vbo, 'in_vert')
        
        @window.event
        def on_draw():
            ctx.clear(0.1, 0.1, 0.1)
            vao.render()
        
        print("6. Showing window briefly...")
        window.set_visible(True)
        
        @window.event
        def on_key_press(symbol, modifiers):
            if symbol == key.ESCAPE:
                window.close()
        
        # Run for 2 seconds then close
        pyglet.clock.schedule_once(lambda dt: window.close(), 2.0)
        pyglet.app.run()
        
        print("✅ All tests PASSED! EGL is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def test_dll_loading():
    """Test which OpenGL DLLs are being loaded"""
    print("\n" + "=" * 60)
    print("DLL Loading Test")
    print("=" * 60)
    
    try:
        import ctypes
        from ctypes import wintypes
        
        # List of OpenGL-related DLLs to check
        opengl_dlls = [
            "opengl32.dll",
            "libEGL.dll", 
            "libGLESv2.dll",
            "gdi32.dll",
            "user32.dll"
        ]
        
        for dll_name in opengl_dlls:
            try:
                handle = ctypes.windll.kernel32.GetModuleHandleW(dll_name)
                if handle:
                    path = ctypes.create_unicode_buffer(260)
                    if ctypes.windll.kernel32.GetModuleFileNameW(handle, path, 260):
                        print(f"✅ {dll_name}: {path.value}")
                    else:
                        print(f"❓ {dll_name}: Loaded but path unknown")
                else:
                    print(f"❌ {dll_name}: Not loaded")
            except Exception as e:
                print(f"⚠️  {dll_name}: Error checking - {e}")
                
    except Exception as e:
        print(f"DLL test failed: {e}")

def copy_mesa_dlls_to_local():
    """Copy Mesa DLLs to local directory to ensure they're loaded first"""
    print("\n" + "=" * 60)
    print("Mesa DLL Setup")
    print("=" * 60)
    
    import shutil
    import glob
    
    # DLLs we need
    mesa_dlls = ["opengl32.dll", "libEGL.dll", "libGLESv2.dll", "dxil.dll"]
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"Looking for Mesa DLLs in: {scripts_dir}")
    
    copied_count = 0
    for dll in mesa_dlls:
        src_path = os.path.join(scripts_dir, dll)
        dst_path = os.path.join(current_dir, dll)
        
        if os.path.exists(src_path):
            try:
                shutil.copy2(src_path, dst_path)
                print(f"✅ Copied: {dll}")
                copied_count += 1
            except Exception as e:
                print(f"❌ Failed to copy {dll}: {e}")
        else:
            print(f"⚠️  Not found: {dll}")
    
    if copied_count > 0:
        print(f"\n📁 Copied {copied_count} DLLs to: {current_dir}")
        print("Windows will load these local DLLs first!")
    else:
        print("❌ No Mesa DLLs found to copy")
    
    return copied_count > 0

if __name__ == "__main__":
    # We need numpy for the geometry test
    try:
        import numpy as np
    except ImportError:
        print("Installing numpy...")
        os.system(f"{sys.executable} -m pip install numpy")
        import numpy as np
    
    print("Testing EGL/OpenGL configuration...")
    
    # Test 1: Check DLL loading
    test_dll_loading()
    
    # Test 2: Try copying Mesa DLLs to local directory
    dlls_copied = copy_mesa_dlls_to_local()
    
    if dlls_copied:
        print("\n🔁 Restarting test with local Mesa DLLs...")
        print("=" * 60)
    
    # Test 3: Main EGL context test
    success = test_egl_context()
    
    if success:
        print("\n🎉 SUCCESS! Your EGL setup is working.")
        print("You can now run the table project with: python main.py shapes.json joints.json")
    else:
        print("\n💡 TROUBLESHOOTING TIPS:")
        print("1. Try running as Administrator (right-click Command Prompt -> Run as Administrator)")
        print("2. Check if your GPU drivers are up to date")
        print("3. Try the fallback software rendering:")
        print("   set MESA_GL_VERSION_OVERRIDE=3.3")
        print("   set MESA_GLSL_VERSION_OVERRIDE=330")
        print("   python egl_test.py")
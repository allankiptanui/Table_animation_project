#!/usr/bin/env python3
"""
fix_dll_loading.py - Force Windows to load Mesa DLLs instead of system OpenGL
"""

import os
import sys
import ctypes
from ctypes import wintypes

def add_dll_directory():
    """Add Mesa DLL directory to the DLL search path"""
    scripts_dir = os.path.dirname(sys.executable)
    
    # Add to DLL search path (Windows 8.1+)
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(scripts_dir)
        print(f"✅ Added to DLL path: {scripts_dir}")
    
    # Also set PATH environment variable
    os.environ['PATH'] = scripts_dir + os.pathsep + os.environ['PATH']
    print(f"✅ Added to PATH: {scripts_dir}")
    
    return scripts_dir

def verify_dll_loading():
    """Verify which DLLs are actually loaded"""
    print("\n" + "="*60)
    print("Verifying DLL Loading")
    print("="*60)
    
    scripts_dir = os.path.dirname(sys.executable)
    
    # Check if Mesa DLLs exist and are accessible
    mesa_dlls = ["opengl32.dll", "libEGL.dll", "libGLESv2.dll"]
    for dll in mesa_dlls:
        dll_path = os.path.join(scripts_dir, dll)
        if os.path.exists(dll_path):
            print(f"✅ {dll} exists at: {dll_path}")
            
            # Try to load the DLL to verify it's valid
            try:
                handle = ctypes.WinDLL(dll_path)
                print(f"   ✓ DLL is loadable")
            except Exception as e:
                print(f"   ❌ DLL load failed: {e}")
        else:
            print(f"❌ {dll} not found at: {dll_path}")

def test_egl_with_fixes():
    """Test EGL with all fixes applied"""
    print("\n" + "="*60)
    print("Testing EGL with DLL fixes")
    print("="*60)
    
    # Apply all fixes
    scripts_dir = add_dll_directory()
    
    # Set environment variables for Mesa
    os.environ["PYGLET_GL_LIB"] = "EGL"
    os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"
    os.environ["MESA_GLSL_VERSION_OVERRIDE"] = "330"
    
    # For Windows, we might need to force specific Mesa behavior
    os.environ["LIBGL_ALWAYS_SOFTWARE"] = "0"  # Try hardware first
    os.environ["GALLIUM_DRIVER"] = "llvmpipe"  # Use LLVM pipe
    
    try:
        import pyglet
        import moderngl
        from OpenGL import GL
        
        print("Creating test window...")
        config = pyglet.gl.Config(double_buffer=True, depth_size=24)
        window = pyglet.window.Window(400, 300, "DLL Fix Test", config=config, visible=False)
        
        ctx = moderngl.create_context()
        
        # Test OpenGL version
        vendor = GL.glGetString(GL.GL_VENDOR)
        renderer = GL.glGetString(GL.GL_RENDERER)
        version = GL.glGetString(GL.GL_VERSION)
        
        print(f"✅ OpenGL Context Created!")
        print(f"   Vendor: {vendor.decode() if vendor else 'Unknown'}")
        print(f"   Renderer: {renderer.decode() if renderer else 'Unknown'}")
        print(f"   Version: {version.decode() if version else 'Unknown'}")
        
        # Test shader compilation
        vertex_shader = "#version 330\nin vec2 vert;void main(){gl_Position=vec4(vert,0,1);}"
        fragment_shader = "#version 330\nout vec4 color;void main(){color=vec4(1,0,0,1);}"
        
        prog = ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)
        print("✅ Shader compilation successful!")
        
        window.close()
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def nuclear_option():
    """Last resort: Copy DLLs to local directory and force load"""
    print("\n" + "="*60)
    print("Nuclear Option: Local DLL Copy")
    print("="*60)
    
    import shutil
    
    scripts_dir = os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    dlls_to_copy = ["opengl32.dll", "libEGL.dll", "libGLESv2.dll", "dxil.dll"]
    
    for dll in dlls_to_copy:
        src = os.path.join(scripts_dir, dll)
        dst = os.path.join(current_dir, dll)
        
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
                print(f"✅ Copied {dll} to current directory")
            except Exception as e:
                print(f"❌ Failed to copy {dll}: {e}")
        else:
            print(f"⚠️  Source not found: {dll}")
    
    # Now test from current directory
    os.environ['PATH'] = current_dir + os.pathsep + os.environ['PATH']
    print(f"✅ Current directory added to PATH: {current_dir}")

if __name__ == "__main__":
    print("Fixing Mesa DLL Loading Issues")
    print("="*60)
    
    # First, verify what we have
    verify_dll_loading()
    
    # Try the standard fixes
    if test_egl_with_fixes():
        print("\n🎉 Standard fixes worked!")
    else:
        print("\n💢 Standard fixes failed. Trying nuclear option...")
        nuclear_option()
        
        # Test again after nuclear option
        if test_egl_with_fixes():
            print("\n🎉 Nuclear option worked!")
        else:
            print("\n💢 All fixes failed. Trying software rendering fallback...")
            
            # Ultimate fallback: software rendering
            os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
            os.environ["GALLIUM_DRIVER"] = "softpipe"
            
            if test_egl_with_fixes():
                print("\n🎉 Software rendering works (will be slow)")
            else:
                print("\n❌ Complete failure. System may not support OpenGL.")
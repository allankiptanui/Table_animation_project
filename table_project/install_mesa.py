#!/usr/bin/env python3
"""
install_mesa.py - Install Mesa DLLs into your virtual environment
"""

import os
import sys
import urllib.request
import zipfile
import shutil
import platform

def download_mesa_windows():
    """Download Mesa3D for Windows and extract the DLLs"""
    print("Downloading Mesa3D for Windows...")
    
    # Mesa version compatible with Python/ModernGL
    mesa_url = "https://github.com/pal1000/mesa-dist-win/releases/download/23.1.6/mesa3d-23.1.6-release-msvc.7z"
    temp_file = "mesa_temp.7z"
    
    try:
        # Download Mesa
        urllib.request.urlretrieve(mesa_url, temp_file)
        print("✅ Downloaded Mesa3D")
        
        # Extract using 7z (Windows usually has this)
        import subprocess
        scripts_dir = os.path.dirname(sys.executable)
        
        # Extract to scripts directory
        subprocess.run(["7z", "x", temp_file, f"-o{scripts_dir}"], check=True)
        print("✅ Extracted Mesa DLLs to virtual environment")
        
        # Clean up
        os.remove(temp_file)
        return True
        
    except Exception as e:
        print(f"❌ Failed to download/extract Mesa: {e}")
        return False

def manual_mesa_install():
    """Manual method if automatic download fails"""
    print("\n🔧 MANUAL MESA INSTALLATION REQUIRED")
    print("=" * 50)
    print("1. Download from: https://github.com/pal1000/mesa-dist-win/releases")
    print("2. Download: mesa3d-23.1.6-release-msvc.7z")
    print("3. Extract the 7z file")
    print("4. Copy these files to your venv Scripts folder:")
    print("   - opengl32.dll")
    print("   - libEGL.dll") 
    print("   - libGLESv2.dll")
    print("   - dxil.dll")
    print(f"5. Your venv Scripts folder: {os.path.dirname(sys.executable)}")
    print("6. Run this script again")
    return False

def verify_mesa_install():
    """Check if Mesa DLLs are now available"""
    scripts_dir = os.path.dirname(sys.executable)
    required_dlls = ["opengl32.dll", "libEGL.dll", "libGLESv2.dll"]
    
    print(f"\nChecking {scripts_dir} for Mesa DLLs...")
    
    found_all = True
    for dll in required_dlls:
        dll_path = os.path.join(scripts_dir, dll)
        if os.path.exists(dll_path):
            print(f"✅ {dll}")
        else:
            print(f"❌ {dll} - MISSING")
            found_all = False
    
    return found_all

def main():
    print("Mesa3D OpenGL Installation")
    print("=" * 50)
    
    if platform.system() != "Windows":
        print("This script is for Windows only.")
        return
    
    # Check current installation
    if verify_mesa_install():
        print("\n✅ Mesa DLLs are already installed!")
        return
    
    print("\nMesa DLLs not found. Installing...")
    
    # Try automatic download
    if download_mesa_windows():
        if verify_mesa_install():
            print("\n🎉 Mesa installation successful!")
            print("You can now run: python egl_test.py")
        else:
            manual_mesa_install()
    else:
        manual_mesa_install()

if __name__ == "__main__":
    main()
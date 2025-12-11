"""
Main entry point for the table project.
"""

import sys
import pyglet

from config import load_configuration
from window import TableWindow

def main() -> None:
    """Main application entry point"""
    if len(sys.argv) != 3:
        print("Usage: python main.py shapes.json joints.json")
        sys.exit(1)
    
    try:
        # Load configuration
        shapes_config, joints_config = load_configuration(sys.argv[1], sys.argv[2])
        
        # Create and run application
        window = TableWindow(shapes_config, joints_config)
        
        print("\nControls:")
        print("  Left Click: Select leg")
        print("  N/P: Select next/previous leg") 
        print("  x/X, y/Y, z/Z: Rotate selected leg (±5°)")
        print("  R: Reset all joint angles")
        print("  Q/ESC: Quit")
        
        pyglet.app.run()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
    
    print("Application terminated successfully.")

if __name__ == "__main__":
    main()
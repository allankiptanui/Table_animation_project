# config.py
"""
Configuration loading and validation.
"""

import json
import sys
from typing import Dict, Any, Tuple
from models import ShapesConfig  # Changed from types to models

def load_configuration(shapes_path: str, joints_path: str) -> Tuple[ShapesConfig, Dict[str, Any]]:
    """Load and validate configuration files"""
    
    def load_json(filepath: str) -> Dict[str, Any]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise SystemExit(f"Error: File not found - {filepath}")
        except json.JSONDecodeError as e:
            raise SystemExit(f"Error: Invalid JSON in {filepath} - {e}")
    
    # Load raw JSON data
    shapes_data = load_json(shapes_path)
    joints_data = load_json(joints_path)
    
    # Basic validation
    if 'tabletop' not in shapes_data:
        raise SystemExit("Error: shapes.json must contain 'tabletop'")
    if 'legs' not in shapes_data or not isinstance(shapes_data['legs'], list):
        raise SystemExit("Error: shapes.json must contain 'legs' array")
    
    # Convert to typed configuration objects
    try:
        shapes_config = ShapesConfig.from_dict(shapes_data)
    except (KeyError, ValueError) as e:
        raise SystemExit(f"Error: Invalid shapes configuration - {e}")
    
    print(f"Loaded configuration: {len(shapes_config.legs)} legs")
    return shapes_config, joints_data
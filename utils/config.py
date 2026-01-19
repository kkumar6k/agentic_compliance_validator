"""
Configuration management
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    # Override with environment variables if present
    if os.getenv('ORCHESTRATOR_MODEL'):
        config['models']['orchestrator'] = os.getenv('ORCHESTRATOR_MODEL')
    if os.getenv('VALIDATOR_MODEL'):
        config['models']['validator'] = os.getenv('VALIDATOR_MODEL')
    
    # Add API keys
    config['api_keys'] = {
        'openai': os.getenv('OPENAI_API_KEY'),
        'anthropic': os.getenv('ANTHROPIC_API_KEY')
    }
    
    return config


def get_data_path(filename: str, config: Dict = None) -> Path:
    """Get path to data file"""
    
    if config is None:
        config = load_config()
    
    data_dir = Path(config.get('data', {}).get('dir', './data'))
    return data_dir / filename

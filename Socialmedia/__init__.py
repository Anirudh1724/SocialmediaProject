# socialmedia/__init__.py

import importlib
import os
from . import instagram
modules = [
    name for name in os.listdir(os.path.dirname(__file__))
    if os.path.isdir(os.path.join(os.path.dirname(__file__), name))
    and not name.startswith("__")
]
__all__ = ["instagram"]

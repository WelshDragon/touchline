"""Sphinx configuration for the Touchline project documentation."""

from __future__ import annotations

import os
import sys
from datetime import datetime

# Ensure the project root is discoverable for autodoc/autosummary imports.
PROJECT_ROOT = os.path.abspath(os.path.join(__file__, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

project = "Touchline Football Simulator"
author = "WelshDragon"
copyright = f"{datetime.now():%Y}, {author}"

# The full version, including alpha/beta/rc tags.
try:
    from touchline import __version__ as version
except Exception:  # pragma: no cover - docs build should not fail if import fails
    version = "0.1.0"
release = version

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autosummary_generate = True

templates_path = ["_templates"]
exclude_patterns: list[str] = ["_build", "Thumbs.db", ".DS_Store"]

# HTML output settings.
html_theme = "sphinx_rtd_theme"

# Keep type hints in the signature but move the description into the field list.
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True

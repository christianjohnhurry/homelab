"""Template configuration for Jinja2."""

from pathlib import Path

from fastapi.templating import Jinja2Templates


PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

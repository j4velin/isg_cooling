"""Make the integration's plain modules importable without Home Assistant.

custom_components/isg_cooling/__init__.py imports Home Assistant. The modules
tested here (isg_client, const, consumption_total) don't need it, so a stub
package with the same path makes them importable as isg_cooling.<module>
without running that __init__.py.
"""
import sys
import types
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.parent / "custom_components" / "isg_cooling"
FIXTURES = Path(__file__).parent / "fixtures"

_package = types.ModuleType("isg_cooling")
_package.__path__ = [str(PACKAGE_DIR)]
sys.modules.setdefault("isg_cooling", _package)


def read_fixture(name: str) -> str:
    """trimmed copy of an ISG page, see tests/fixtures"""
    return (FIXTURES / name).read_text(encoding="utf-8")

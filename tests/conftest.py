import sys
from pathlib import Path

# Make bin/ importable so tests can import generate_fusion_report directly
sys.path.insert(0, str(Path(__file__).parent.parent / "bin"))

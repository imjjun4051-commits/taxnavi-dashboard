"""테스트가 상위 폴더의 모듈을 import 할 수 있게 경로를 잡아 준다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

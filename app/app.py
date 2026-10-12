"""실행: 프로젝트 최상위에서 streamlit run app/app.py
앱 후보 B의 확정 실행 진입점이다.
데이터 경로는 app/candidates/app_minji.py가 파일 위치로부터 계산한다.
"""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "candidates" / "app_minji.py"), run_name="__main__")

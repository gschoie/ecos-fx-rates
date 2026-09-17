# -*- coding: utf-8 -*-
"""파이프라인 전역 설정. 환경변수로 재정의 가능."""
import os

# ── Telegram ──────────────────────────────────────────────────────────
CHANNEL = os.environ.get("TG_CHANNEL", "HI_GS")
TG_PREVIEW_URL = f"https://t.me/s/{CHANNEL}"

# 보고서 판별 핵심 문구 (변형 허용을 위해 핵심부만)
COMPLIANCE_PHRASE = "컴플라이언스 승인을 득한"

# ── Google Drive / Sheets ────────────────────────────────────────────
# 서비스 계정 JSON: 파일 경로 또는 JSON 문자열 자체
GDRIVE_SA_JSON = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", "")
# 사용자가 서비스 계정에 공유한 "Research Reports" 폴더의 ID (권장)
GDRIVE_ROOT_FOLDER_ID = os.environ.get("GDRIVE_ROOT_FOLDER_ID", "")
ROOT_FOLDER_NAME = os.environ.get("GDRIVE_ROOT_FOLDER_NAME", "Research Reports")
# Master Index 스프레드시트 ID (없으면 루트 폴더 안에 자동 생성)
MASTER_INDEX_SHEET_ID = os.environ.get("MASTER_INDEX_SHEET_ID", "")
MASTER_INDEX_NAME = "Report Master Index"
STATE_FILE_NAME = "_archive_state.json"

# ── AI 분석 ──────────────────────────────────────────────────────────
# 우선순위: ANTHROPIC_API_KEY(유료) > GEMINI_API_KEY(무료 등급 있음) > 휴리스틱
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ── 분류 ─────────────────────────────────────────────────────────────
INDUSTRIES = ["조선", "방산", "기계"]
FALLBACK_INDUSTRY = "기타"

# AI 미사용 시(또는 보조용) 기업명 → 산업 매핑
COMPANY_INDUSTRY_MAP = {
    # 조선
    "한화오션": "조선", "HD현대중공업": "조선", "삼성중공업": "조선",
    "HD한국조선해양": "조선", "HD현대미포": "조선", "현대미포조선": "조선",
    "HJ중공업": "조선", "케이조선": "조선", "대한조선": "조선",
    "HD현대마린솔루션": "조선", "HD현대마린엔진": "조선", "한화엔진": "조선",
    "STX엔진": "조선", "성광벤드": "조선", "태광": "조선", "동성화인텍": "조선",
    "세진중공업": "조선", "오리엔탈정공": "조선",
    # 방산
    "한화에어로스페이스": "방산", "LIG넥스원": "방산", "현대로템": "방산",
    "한국항공우주": "방산", "KAI": "방산", "풍산": "방산", "한화시스템": "방산",
    "SNT다이내믹스": "방산", "SNT모티브": "방산", "휴니드": "방산",
    "빅텍": "방산", "코츠테크놀로지": "방산", "STX중공업": "방산",
    # 기계
    "두산에너빌리티": "기계", "두산밥캣": "기계", "HD현대인프라코어": "기계",
    "HD현대건설기계": "기계", "HD현대일렉트릭": "기계", "효성중공업": "기계",
    "LS일렉트릭": "기계", "대동": "기계", "TYM": "기계", "디와이파워": "기계",
    "씨에스베어링": "기계", "씨에스윈드": "기계", "SK오션플랜트": "기계",
}

# ── 파일명 ───────────────────────────────────────────────────────────
MAX_FILENAME_LEN = 120          # 확장자 제외 최대 길이
MAX_KEYWORDS = 4
MIN_KEYWORDS = 2

# ── 다운로드 ─────────────────────────────────────────────────────────
HTTP_TIMEOUT = 60
MAX_PDF_MB = 150
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# ── Master Index 컬럼 ────────────────────────────────────────────────
INDEX_COLUMNS = [
    "Report ID", "발간일", "산업", "자료유형", "기업", "보고서 제목",
    "AI 핵심키워드", "투자의견", "Target Price", "이전 Target Price",
    "TP 변경 여부", "투자의견 변경 여부", "해당 기업 Page Range",
    "Telegram 원문 링크", "원본 보고서 URL", "Google Drive PDF 링크",
    "수집일", "처리 상태",
]

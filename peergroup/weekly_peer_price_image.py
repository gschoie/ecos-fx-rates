# -*- coding: utf-8 -*-
"""글로벌 피어그룹 주가 흐름 — 위클리에 바로 붙여넣는 PNG 생성기.

엑셀 대시보드(weekly_peergroup_price.py)와 달리 '그림 한 장'이 목적이다.
섹션(조선사·엔진/부품·오일·해운 …)별 표에 등락률 막대 + 주가 스파크라인을 그려
output/peer_price/ 아래에 저장한다.

  - 글로벌_피어그룹_주가흐름.png  : 전체 1페이지 (좌·우 2단)
  - 섹션별 PNG                     : 01_조선사.png … (한 섹션만 잘라 쓰고 싶을 때)

실행:
    python peergroup/weekly_peer_price_image.py                        # 조선·해운(기본) 야후 수집
    python peergroup/weekly_peer_price_image.py --universe defense      # 방산·항공우주 → output/peer_price_defense/
    python peergroup/weekly_peer_price_image.py --universe construction # 건설기계 → output/peer_price_construction/
    python peergroup/weekly_peer_price_image.py --demo                 # 가짜 데이터로 레이아웃만 확인

종목 구성은 아래 SHIP/DEFENSE/CONSTRUCTION_SECTIONS 만 고치면 된다. (그룹 라벨, 표시명, 야후 티커)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# =========================================================================
# 종목 구성: 섹션 → [(그룹 라벨, [(표시명, 야후 티커), ...]), ...]
#   column: 0 = 왼쪽 단, 1 = 오른쪽 단 (전체 페이지 배치)
#   market_cap=False 면 시총 칸을 비운다(지수·원자재)
# =========================================================================
SHIP_SECTIONS = [
    {
        "title": "지수 / 원자재", "column": 0, "market_cap": False,
        "groups": [
            ("유가", [("WTI", "CL=F"), ("Brent", "BZ=F")]),
            ("천연가스", [("Henry Hub(美)", "NG=F"), ("TTF(歐)", "TTF=F"), ("JKM(亞 LNG)", "JKM=F")]),
            ("운임", [("BDRY(BDI ETF)", "BDRY")]),
            ("환율", [("원/달러", "KRW=X")]),
        ],
    },
    {
        "title": "조선사", "column": 0,
        "groups": [
            ("한국조선", [("HD한국조선해양", "009540.KS"), ("HD현대중공업", "329180.KS"),
                         ("삼성중공업", "010140.KS"), ("한화오션", "042660.KS"),
                         ("대한조선", "439260.KS"), ("HJ중공업", "097230.KS")]),
            ("싱가포르", [("Seatrium", "5E2.SI")]),
            ("중국조선", [("CSSC", "600150.SS"), ("CSSC O&ME", "0317.HK"),
                         ("Yangzijiang", "BS6.SI")]),
            ("일본조선", [("Mitsubishi HI", "7011.T"), ("Mitsui E&S", "7003.T"),
                         ("Kawasaki HI", "7012.T"), ("Sumitomo HI", "6302.T"),
                         ("IHI", "7013.T"), ("Naikai Zosen", "7018.T")]),
            ("대만조선", [("CSBC Taiwan", "2208.TW")]),
            ("함정(美·歐·濠)", [("Huntington Ingalls", "HII"), ("Fincantieri", "FCT.MI"),
                            ("Austal", "ASB.AX")]),
        ],
    },
    {
        "title": "엔진 / 기자재", "column": 0,
        "groups": [
            ("엔진", [("Wartsila", "WRT1V.HE"), ("한화엔진", "082740.KS"),
                      ("HD현대마린엔진", "071970.KS"), ("STX엔진", "077970.KS")]),
            ("엔진부품", [("케이프", "064820.KQ"), ("인화정공", "101930.KQ")]),
            ("AM/전장", [("HD현대마린솔루션", "443060.KS"), ("에스엔시스", "0008Z0.KQ"),
                        ("Kongsberg", "KOG.OL")]),
            ("기자재", [("한국카본", "017960.KS"), ("동성화인텍", "033500.KQ"),
                       ("세진중공업", "075580.KS"), ("SK오션플랜트", "100090.KS"),
                       ("현대힘스", "460930.KQ"), ("한라IMS", "092460.KQ"),
                       ("대양전기공업", "108380.KQ"), ("오리엔탈정공", "014940.KQ"),
                       ("동방선기", "099410.KQ"), ("일승", "333430.KQ")]),
            ("피팅/밸브", [("성광벤드", "014620.KQ"), ("태광", "023160.KQ"),
                          ("하이록코리아", "013030.KQ"), ("비엠티", "086670.KQ")]),
        ],
    },
    {
        "title": "오일 / 해양", "column": 1,
        "groups": [
            ("RIG", [("Transocean", "RIG"), ("Noble", "NE"), ("Valaris", "VAL"),
                     ("Seadrill", "SDRL"), ("Borr Drilling", "BORR"),
                     ("Odfjell Drilling", "ODL.OL"), ("Dolphin Drilling", "DDRIL.OL")]),
            ("IOC/NOC", [("ExxonMobil", "XOM"), ("Shell", "SHEL"), ("BP", "BP"),
                         ("TotalEnergies", "TTE"), ("Chevron", "CVX"), ("ENI", "E"),
                         ("Equinor", "EQNR"), ("Petrobras", "PBR")]),
            ("FPSO", [("SBM Offshore", "SBMO.AS"), ("BW Offshore", "BWO.OL"),
                      ("MODEC", "6269.T"), ("Yinson", "7293.KL")]),
            ("ENG./EPC", [("TechnipFMC", "FTI"), ("Technip Energies", "TE.PA"),
                          ("Subsea7", "SUBC.OL"), ("Aker Solutions", "AKSO.OL"),
                          ("Saipem", "SPM.MI"), ("NOV", "NOV"), ("Worley", "WOR.AX")]),
            ("OSV", [("Tidewater", "TDW")]),
        ],
    },
    {
        "title": "해운", "column": 1,
        "groups": [
            ("컨테이너", [("Maersk", "MAERSK-B.CO"), ("Hapag-Lloyd", "HLAG.DE"),
                         ("COSCO Shipping", "1919.HK"), ("Evergreen", "2603.TW"),
                         ("ZIM", "ZIM"), ("HMM", "011200.KS")]),
            ("컨선 선주", [("Danaos", "DAC"), ("Costamare", "CMRE"),
                          ("Global Ship Lease", "GSL")]),
            ("탱커", [("Frontline", "FRO"), ("Scorpio Tankers", "STNG"),
                      ("Intl Seaways", "INSW"), ("DHT", "DHT"), ("Hafnia", "HAFN"),
                      ("Nordic American", "NAT"), ("CMB.TECH", "CMBT")]),
            ("벌크", [("Star Bulk", "SBLK"), ("팬오션", "028670.KS"),
                      ("대한해운", "005880.KS")]),
            ("LNG", [("Flex LNG", "FLNG"), ("Golar LNG", "GLNG")]),
            ("LPG", [("BW LPG", "BWLP"), ("Dorian LPG", "LPG"), ("Exmar", "EXM.BR")]),
            ("기타", [("SFL Corp", "SFL"), ("KNOT Offshore", "KNOP"),
                      ("Clarkson", "CKN.L")]),
        ],
    },
]


# 방산 · 항공우주 — 한국 체계/부체계/우주 + 미국 프라임·드론 + 유럽 + 기타(중동·인도·일본·중국·남미)
DEFENSE_SECTIONS = [
    {
        "title": "지수 / ETF", "column": 0, "market_cap": False, "file": "01_지수_ETF",
        "groups": [
            ("한국", [("PLUS K방산 ETF", "449450.KS")]),
            ("미국", [("iShares US A&D(ITA)", "ITA"), ("Global X Defense(SHLD)", "SHLD")]),
            ("유럽", [("Europe A&D(EUAD)", "EUAD")]),
            ("우주", [("Procure Space(UFO)", "UFO")]),
        ],
    },
    {
        "title": "한국 방산 · 항공우주", "column": 0, "file": "02_한국방산",
        "groups": [
            ("체계", [("한화에어로스페이스", "012450.KS"), ("한국항공우주", "047810.KS"),
                     ("LIG D&A(넥스원)", "079550.KS"), ("한화시스템", "272210.KS"),
                     ("현대로템", "064350.KS")]),
            ("탄약/기동", [("풍산", "103140.KS"), ("SNT다이내믹스", "003570.KS")]),
            ("부체계", [("엠앤씨솔루션", "484870.KS"), ("아이쓰리시스템", "214430.KQ"),
                       ("퍼스텍", "010820.KS"), ("휴니드", "005870.KS")]),
            ("항공부품", [("켄코아에어로스페이스", "274090.KQ"), ("아스트", "067390.KQ")]),
            ("우주", [("쎄트렉아이", "099320.KQ"), ("인텔리안테크", "189300.KQ"),
                     ("컨텍", "451760.KQ"), ("제노코", "361390.KQ")]),
        ],
    },
    {
        "title": "글로벌 우주 · 위성", "column": 0, "file": "06_우주위성",
        "groups": [
            ("발사체/탐사", [("Rocket Lab", "RKLB"), ("Firefly Aerospace", "FLY"),
                           ("Intuitive Machines", "LUNR")]),
            ("위성통신", [("AST SpaceMobile", "ASTS"), ("Iridium", "IRDM"), ("Viasat", "VSAT"),   # EchoStar SATS 는 야후 이력이 짧아 1M~1Y 공란(11/9)
                        ("Eutelsat", "ETL.PA"), ("SES", "SESG.PA")]),
            ("관측/데이터", [("Planet Labs", "PL"), ("MDA Space", "MDA.TO")]),
            ("부품/시스템", [("Redwire", "RDW"), ("Karman", "KRMN"), ("OHB", "OHB.DE")]),
            ("일본", [("ispace", "9348.T"), ("Astroscale", "186A.T")]),   # QPS 5595.T 는 야후 무응답(11/9)
        ],
    },
    {
        "title": "미국", "column": 1, "file": "04_미국",
        "groups": [
            ("프라임", [("Lockheed Martin", "LMT"), ("RTX", "RTX"), ("Northrop Grumman", "NOC"),
                       ("General Dynamics", "GD"), ("L3Harris", "LHX"), ("Boeing", "BA"),
                       ("Huntington Ingalls", "HII")]),
            ("드론/신흥", [("Kratos", "KTOS"), ("AeroVironment", "AVAV")]),
            ("엔진/부품", [("GE Aerospace", "GE"), ("Howmet", "HWM"), ("TransDigm", "TDG"),
                          ("Curtiss-Wright", "CW")]),
        ],
    },
    {
        "title": "유럽", "column": 1, "file": "05_유럽",
        "groups": [
            ("체계", [("Rheinmetall", "RHM.DE"), ("BAE Systems", "BA.L"), ("Thales", "HO.PA"),
                     ("Leonardo", "LDO.MI"), ("Saab", "SAAB-B.ST"), ("Hensoldt", "HAG.DE"),
                     ("Renk", "R3NK.DE"), ("Kongsberg", "KOG.OL")]),
            ("항공", [("Airbus", "AIR.PA"), ("Dassault Aviation", "AM.PA")]),
            ("엔진/부품", [("Rolls-Royce", "RR.L"), ("Safran", "SAF.PA"), ("MTU Aero", "MTX.DE")]),
        ],
    },
    {
        "title": "기타 (중동 · 인도 · 일본 · 중국 · 남미)", "column": 1, "file": "03_기타",
        "groups": [
            ("중동", [("Elbit Systems(이스라엘)", "ESLT"), ("Aselsan(튀르키예)", "ASELS.IS")]),
            ("인도", [("HAL(Hindustan Aero)", "HAL.NS"), ("Bharat Electronics", "BEL.NS")]),
            ("일본", [("Mitsubishi HI", "7011.T"), ("Kawasaki HI", "7012.T"), ("IHI", "7013.T")]),
            ("중국", [("AVIC Shenyang", "600760.SS"), ("AVIC Xi'an Aircraft", "000768.SZ")]),
            ("남미", [("Embraer", "EMBJ")]),   # 2025-11 티커 변경 ERJ→EMBJ(NYSE), B3 는 EMBJ3
        ],
    },
]

# 건설기계 — OEM(지역별) + 농기계/광산/렌탈·딜러(수요 지표) + 부품
CONSTRUCTION_SECTIONS = [
    {
        "title": "지수 / 원자재", "column": 0, "market_cap": False, "file": "01_지수_원자재",
        "groups": [
            ("인프라", [("PAVE(美 인프라 ETF)", "PAVE")]),
            ("원자재", [("구리", "HG=F"), ("WTI", "CL=F")]),
            ("환율", [("원/달러", "KRW=X")]),
        ],
    },
    {
        "title": "건설기계 OEM", "column": 0, "file": "02_건설기계OEM",
        "groups": [
            ("한국", [("HD건설기계", "267270.KS"), ("두산밥캣", "241560.KS")]),
            ("미국/유럽", [("Caterpillar", "CAT"), ("Volvo", "VOLV-B.ST"), ("Terex", "TEX"),
                          ("Oshkosh(JLG)", "OSK"), ("Manitowoc", "MTW"),
                          ("Wacker Neuson", "WAC.DE"), ("Manitou", "MTU.PA")]),
            ("일본", [("Komatsu", "6301.T"), ("Hitachi CM", "6305.T"), ("Kubota", "6326.T"),
                     ("Sumitomo HI", "6302.T"), ("Takeuchi", "6432.T"), ("Tadano", "6395.T")]),
            ("중국", [("SANY", "600031.SS"), ("XCMG", "000425.SZ"), ("Zoomlion", "1157.HK"),
                     ("LiuGong", "000528.SZ"), ("Lonking", "3339.HK")]),
            ("인도", [("Escorts Kubota", "ESCORTS.NS"), ("Action Construction", "ACE.NS"),
                     ("BEML", "BEML.NS")]),
        ],
    },
    {
        "title": "농기계 / 광산 / 렌탈 · 딜러", "column": 1, "file": "03_농기계_광산_렌탈딜러",
        "groups": [
            ("농기계", [("Deere", "DE"), ("CNH", "CNH"), ("AGCO", "AGCO"), ("대동", "000490.KS")]),
            ("광산장비", [("Sandvik", "SAND.ST"), ("Epiroc", "EPI-A.ST"), ("Metso", "METSO.HE"),
                         ("Weir", "WEIR.L")]),
            ("렌탈", [("United Rentals", "URI"), ("Sunbelt Rentals(舊Ashtead)", "SUNB"), ("Herc", "HRI")]),
            ("CAT 딜러", [("Finning", "FTT.TO"), ("Toromont", "TIH.TO")]),
        ],
    },
    {
        "title": "부품", "column": 1, "file": "04_부품",
        "groups": [
            ("한국", [("디와이파워", "210540.KS"), ("진성티이씨", "036890.KQ"), ("대창단조", "015230.KS"),
                     ("동일금속", "109860.KQ"), ("흥국", "010240.KQ"), ("우림피티에스", "101170.KQ")]),
            ("글로벌", [("KYB", "7242.T"), ("Hengli Hydraulic", "601100.SS")]),
        ],
    },
]

# 등락률·스파크라인 기준은 거래일 오프셋(커버리지 수급 페이지와 동일): 1W=5, 1M=21, 3M=63, 1Y=252
TRADING_DAYS = {"1W": 5, "1M": 21, "3M": 63, "1Y": 252}
# 스파크라인 기간(거래일). 63 = 3개월, 126 = 6개월
SPARK_DAYS = 63

# 표 열: (키, 헤더, 폭[행높이 대비 단위]). 순서·폭만 바꾸면 레이아웃이 따라온다.
COLUMNS = [
    ("group", "구분", 3.9),
    ("name", "회사명", 6.3),
    ("mcap", "시총\n($m)", 3.0),
    ("1W", "1W", 3.6),
    ("1M", "1M", 3.6),
    ("3M", "3M", 3.6),
    ("spark", "주가 ({})", 7.6),
    ("YTD", "YTD", 3.6),
    ("1Y", "1Y", 3.6),
]
BAR_KEYS = ["1W", "1M", "3M", "YTD", "1Y"]

# 서식
TITLE_TEXT = "글로벌 피어그룹 주가 흐름"
BRAND = "#A68A64"      # 상단·섹션 제목 바 (스크린샷 갈색)
HEAD_BG = "#DDEBF7"    # 열 헤더 배경
UP = "#D62728"         # 상승(빨강, 국내 관례)
DOWN = "#1F5FBF"       # 하락(파랑)
UP_BAR = "#F3A6A6"
DOWN_BAR = "#A9C4EC"
GRID = "#A6A6A6"
TEXT = "#000000"
MUTED = "#595959"

COL_IN = 0.225         # 가로 단위(inch) — 열 폭(COLUMNS)의 1단위
ROW_IN = 0.29          # 행 높이(inch) — 11/10 0.225→0.29: 스파크라인 흐름이 보이게(사용자). 가로는 COL_IN 으로 분리
DPI = 220

_OUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

# 유니버스(--universe): 섹션 구성·출력 폴더·전체 페이지 파일명·2페이지 분할본.
#   split: (파일명, 제목 꼬리, {섹션 제목: 단(0=왼쪽, 1=오른쪽)})
UNIVERSES = {
    "ship": {
        "sections": SHIP_SECTIONS, "out_dir": os.path.join(_OUT_ROOT, "peer_price"),
        "page_file": "글로벌_피어그룹_주가흐름.png",
        "split": [
            ("글로벌_피어그룹_주가흐름_p1_조선.png", "조선 · 기자재",
             {"지수 / 원자재": 0, "조선사": 0, "엔진 / 기자재": 1}),
            ("글로벌_피어그룹_주가흐름_p2_오일해운.png", "오일 · 해운",
             {"오일 / 해양": 0, "해운": 1}),
        ],
    },
    "defense": {
        "sections": DEFENSE_SECTIONS, "out_dir": os.path.join(_OUT_ROOT, "peer_price_defense"),
        "page_file": "글로벌_방산_주가흐름.png",
        "split": [
            ("글로벌_방산_주가흐름_p1_한국기타.png", "한국 · 우주",
             {"지수 / ETF": 0, "한국 방산 · 항공우주": 0, "글로벌 우주 · 위성": 1}),
            ("글로벌_방산_주가흐름_p2_미국유럽.png", "미국 · 유럽 · 기타",
             {"미국": 0, "유럽": 1, "기타 (중동 · 인도 · 일본 · 중국 · 남미)": 1}),
        ],
    },
    "construction": {
        "sections": CONSTRUCTION_SECTIONS, "out_dir": os.path.join(_OUT_ROOT, "peer_price_construction"),
        "page_file": "글로벌_건설기계_주가흐름.png",
        "split": [
            ("글로벌_건설기계_주가흐름_p1_OEM.png", "OEM",
             {"지수 / 원자재": 0, "건설기계 OEM": 1}),
            ("글로벌_건설기계_주가흐름_p2_수요부품.png", "농기계 · 광산 · 렌탈 · 부품",
             {"농기계 / 광산 / 렌탈 · 딜러": 0, "부품": 1}),
        ],
    },
}

# 모듈 전역 — select_universe() 가 채운다(기본 ship). 옛 import 호환.
SECTIONS = SHIP_SECTIONS
OUTPUT_DIR = UNIVERSES["ship"]["out_dir"]
PAGE_FILE = UNIVERSES["ship"]["page_file"]
SPLIT_PAGES = UNIVERSES["ship"]["split"]


def select_universe(name):
    global SECTIONS, OUTPUT_DIR, PAGE_FILE, SPLIT_PAGES
    u = UNIVERSES[name]
    SECTIONS, OUTPUT_DIR, PAGE_FILE, SPLIT_PAGES = u["sections"], u["out_dir"], u["page_file"], u["split"]
    return u


# =========================================================================
# 폰트
# =========================================================================
def setup_font():
    """보고서 서체 = 나눔스퀘어 Light. 러너는 fonts-nanum-extra(NanumSquareL.ttf)를 깔아
    그림에 직접 박는다(보는 PC 폰트와 무관). 본문은 Light(300), 굵게 지정한 제목은 같은
    가족의 Bold. Light 가 없는 환경은 종전 나눔고딕 등으로 폴백."""
    fl = font_manager.fontManager.ttflist
    have = {f.name for f in fl}
    if any(f.name == "NanumSquare" and f.weight in (300, "light") for f in fl):
        # 목록이면 글자 단위 폴백(matplotlib ≥3.6) — 나눔스퀘어에 없는 글자는 나눔고딕으로
        plt.rcParams["font.family"] = ["NanumSquare"] + [n for n in ("NanumGothic",) if n in have]
        plt.rcParams["font.weight"] = 300   # 숫자로 — "light" 는 findfont 경고가 줄줄이 난다
        for k in ("axes.titleweight", "axes.labelweight", "figure.titleweight"):
            plt.rcParams[k] = 300   # 기본값 normal(=Regular)이라 따로 내려준다; fontweight="bold" 지정분은 그대로 Bold
        plt.rcParams["axes.unicode_minus"] = False
        return
    wanted = ["Malgun Gothic", "NanumGothic", "NanumBarunGothic", "AppleGothic",
              "Noto Sans CJK KR", "Noto Sans KR", "WenQuanYi Zen Hei"]
    for name in wanted:
        if name in have:
            plt.rcParams["font.family"] = name
            break
    else:
        print("⚠️ 한글 폰트를 찾지 못했습니다 (fonts-nanum 설치 권장). 글자가 깨질 수 있습니다.")
    plt.rcParams["axes.unicode_minus"] = False


# =========================================================================
# 데이터
# =========================================================================
def all_tickers():
    out = []
    for sec in SECTIONS:
        for _, items in sec["groups"]:
            out += [t for _, t in items]
    return list(dict.fromkeys(out))


def fetch_prices(tickers):
    """{ticker: 종가 Series} — 4년치. 실패한 종목은 빠진다."""
    import yfinance as yf

    start = (datetime.today() - timedelta(days=4 * 365)).strftime("%Y-%m-%d")
    raw = yf.download(tickers, start=start, auto_adjust=True, group_by="ticker",
                      threads=True, progress=False)
    out = {}
    for t in tickers:
        try:
            s = raw[t]["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw["Close"]
        except KeyError:
            s = pd.Series(dtype=float)
        s = s.dropna()
        if s.empty:  # 배치에서 빠졌으면 개별 재시도
            try:
                s = yf.Ticker(t).history(start=start)["Close"].dropna()
            except Exception:
                s = pd.Series(dtype=float)
        if s.empty:
            print(f"⚠️ {t}: 가격 데이터 없음 — 건너뜀")
            continue
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        out[t] = s[~s.index.duplicated(keep="last")]
    return out


def fetch_market_caps_usd_m(tickers):
    """{ticker: 시총(백만달러)}. 통화는 야후 fast_info 기준으로 달러 환산."""
    import yfinance as yf

    fx = {"USD": 1.0}

    def to_usd(cur):
        # 영국(GBp)·이스라엘(ILA)·남아공(ZAc)은 보조단위 호가
        scale = 1.0
        if cur in ("GBp", "GBX"):
            cur, scale = "GBP", 0.01
        elif cur == "ILA":
            cur, scale = "ILS", 0.01
        elif cur == "ZAc":
            cur, scale = "ZAR", 0.01
        if cur not in fx:
            try:
                h = yf.Ticker(f"{cur}USD=X").history(period="5d")["Close"].dropna()
                fx[cur] = float(h.iloc[-1]) if not h.empty else np.nan
            except Exception:
                fx[cur] = np.nan
        return fx[cur] * scale

    out = {}
    for t in tickers:
        try:
            fi = yf.Ticker(t).fast_info
            mc = fi.get("marketCap") or fi.get("market_cap")
            cur = fi.get("currency") or "USD"
            if not mc:  # 싱가포르 등 일부 거래소는 fast_info에 시총이 없음 → info 폴백
                info = yf.Ticker(t).info
                mc = info.get("marketCap")
                cur = info.get("currency") or cur
            if mc:
                out[t] = mc * to_usd(cur) / 1e6
        except Exception as e:
            print(f"⚠️ {t}: 시총 조회 실패 ({e})")
    return out


def demo_data(tickers, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=datetime.today(), periods=4 * 261)
    prices, caps = {}, {}
    for t in tickers:
        drift = rng.normal(0.0004, 0.0008)
        vol = rng.uniform(0.012, 0.035)
        p = 100 * np.exp(np.cumsum(rng.normal(drift, vol, len(idx))))
        prices[t] = pd.Series(p, index=idx)
        caps[t] = float(rng.lognormal(8.5, 1.4))
    return prices, caps


def compute_metrics(s):
    last_d, last = s.index[-1], float(s.iloc[-1])

    def ret_since(n):
        """n 거래일 전 종가 대비 (해당 종목의 거래일 기준)."""
        return last / float(s.iloc[-1 - n]) - 1 if len(s) > n else np.nan

    prev_year = s.loc[s.index < datetime(last_d.year, 1, 1)]
    ytd = last / float(prev_year.iloc[-1]) - 1 if not prev_year.empty else np.nan
    return {
        **{k: ret_since(n) for k, n in TRADING_DAYS.items()},
        "YTD": ytd,
        "spark": s.iloc[-(SPARK_DAYS + 1):],
        "last_date": last_d,
    }


# =========================================================================
# 그리기
# =========================================================================
def section_rows(section, metrics):
    """섹션 → 행 리스트. 데이터가 없는 종목도 이름은 남긴다(빈 칸)."""
    rows = []
    for g, items in section["groups"]:
        for i, (name, t) in enumerate(items):
            rows.append({"group": g if i == 0 else "", "group_start": i == 0,
                         "name": name, "ticker": t, **metrics.get(t, {})})
    return rows


def section_height_units(section):
    n = sum(len(items) for _, items in section["groups"])
    return 1.25 + 1.7 + n  # 제목바 + 열헤더 + 행


def table_width_units():
    return sum(w for _, _, w in COLUMNS)


def fmt_pct(v):
    if v is None or not np.isfinite(v):
        return ""
    return f"{v * 100:+.1f}%" if abs(v) < 10 else f"{v * 100:+,.0f}%"


def draw_section(ax, section, rows, caps, col_scale):
    W = table_width_units()
    H = section_height_units(section)
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")

    # 섹션 제목 바
    ax.add_patch(Rectangle((0, 0.1), W, 1.0, color=BRAND, lw=0))
    ax.text(0.35, 0.6, section["title"], color="white", fontsize=13,
            fontweight="bold", va="center", ha="left")

    # 열 헤더
    y0 = 1.25
    ax.add_patch(Rectangle((0, y0), W, 1.7, color=HEAD_BG, lw=0))
    ax.plot([0, W], [y0 + 1.7, y0 + 1.7], color=TEXT, lw=1.1)
    xs = np.cumsum([0] + [w for _, _, w in COLUMNS])
    xpos = {k: (xs[i], w) for i, (k, _, w) in enumerate(COLUMNS)}
    spark_label = f"{SPARK_DAYS // 21}M" if SPARK_DAYS % 21 == 0 else f"{SPARK_DAYS}D"
    for k, label, w in COLUMNS:
        x, _ = xpos[k]
        txt = label.format(spark_label) if k == "spark" else label
        ha, tx = ("left", x + 0.25) if k in ("group", "name") else ("center", x + w / 2)
        ax.text(tx, y0 + 0.85, txt, fontsize=9.5, fontweight="bold", color=TEXT,
                ha=ha, va="center", linespacing=1.0)

    top = y0 + 1.7
    fig = ax.figure
    for i, r in enumerate(rows):
        yc = top + i + 0.5
        if r["group_start"] and i > 0:
            ax.plot([0, W], [top + i, top + i], color=GRID, lw=0.8)
        elif i > 0:
            ax.plot([xpos["name"][0], W], [top + i, top + i], color="#D9D9D9", lw=0.6)

        ax.text(xpos["group"][0] + 0.25, yc, r["group"], fontsize=9.5, color=TEXT,
                va="center", fontweight="bold")
        ax.text(xpos["name"][0] + 0.25, yc, r["name"], fontsize=9.5, color=TEXT, va="center")

        if section.get("market_cap", True):
            mc = caps.get(r["ticker"])
            if mc and np.isfinite(mc):
                x, w = xpos["mcap"]
                ax.text(x + w - 0.25, yc, f"{mc:,.0f}", fontsize=9.5, color=TEXT,
                        ha="right", va="center")

        for k in BAR_KEYS:
            v = r.get(k)
            if v is None or not np.isfinite(v):
                continue
            x, w = xpos[k]
            mid = x + w / 2
            half = w / 2 - 0.2
            frac = max(-1.0, min(1.0, v / col_scale[k])) if col_scale[k] > 0 else 0
            ax.add_patch(Rectangle((mid, yc - 0.32), frac * half, 0.64,
                                   color=UP_BAR if v >= 0 else DOWN_BAR, lw=0))
            ax.plot([mid, mid], [yc - 0.42, yc + 0.42], color="#8C8C8C", lw=0.6)
            ax.text(x + w / 2, yc, fmt_pct(v), fontsize=9.5, va="center", ha="center",
                    color=UP if v > 0 else DOWN if v < 0 else TEXT,
                    fontweight="bold")

        sp = r.get("spark")
        if sp is not None and len(sp) > 1:
            x, w = xpos["spark"]
            # 행 영역을 axes 비율 좌표로 변환해 작은 축을 얹는다
            (fx0, fy0) = ax.transAxes.inverted().transform(ax.transData.transform((x + 0.3, top + i + 0.92)))
            (fx1, fy1) = ax.transAxes.inverted().transform(ax.transData.transform((x + w - 0.3, top + i + 0.08)))
            sax = ax.inset_axes([fx0, fy0, fx1 - fx0, fy1 - fy0])
            vals = sp.values.astype(float)
            col = UP if vals[-1] >= vals[0] else DOWN
            sax.axhline(vals[0], color="#A0A0A0", lw=0.6, ls=(0, (2, 2)))
            sax.plot(np.arange(len(vals)), vals, color=col, lw=1.7)
            sax.plot(len(vals) - 1, vals[-1], "o", ms=2.6, color=col)
            pad = (vals.max() - vals.min()) * 0.08 or 1
            sax.set_ylim(vals.min() - pad, vals.max() + pad)
            sax.set_xlim(-1, len(vals))
            sax.axis("off")

    # 하단 마감선 + 세로 구분선
    bottom = top + len(rows)
    ax.plot([0, W], [bottom, bottom], color=TEXT, lw=1.1)
    for k in ("mcap", "1W", "spark", "YTD"):
        x, _ = xpos[k]
        ax.plot([x, x], [y0 + 0.15, bottom], color="#C8C8C8", lw=0.6)


def column_scales(all_rows):
    """막대 길이 기준: 열별 |값|의 90분위(이상치 한 종목이 막대를 다 먹지 않게)."""
    sc = {}
    for k in BAR_KEYS:
        vals = np.array([abs(r[k]) for r in all_rows
                         if r.get(k) is not None and np.isfinite(r[k])])
        sc[k] = float(np.quantile(vals, 0.9)) if len(vals) else 1.0
    return sc


def render_page(sections_rows, caps, scales, asof, path, layout=None, subtitle=""):
    """layout: {섹션 제목: 단} — 주면 그 섹션만 그 단에, 없으면 SECTIONS의 column 사용."""
    W_units = table_width_units()
    gap_units = 1.6
    cols = {0: [], 1: []}
    for sec, rows in sections_rows:
        if layout is None:
            cols[sec.get("column", 0)].append((sec, rows))
        elif sec["title"] in layout:
            cols[layout[sec["title"]]].append((sec, rows))
    col_h = {c: sum(section_height_units(s) for s, _ in lst) + gap_units * max(0, len(lst) - 1)
             for c, lst in cols.items()}

    margin, title_h, foot_h, mid_gap = 0.25, 0.0, 0.25, 0.3
    tw = W_units * COL_IN
    fig_w = 2 * margin + 2 * tw + mid_gap
    fig_h = margin + title_h + max(col_h.values()) * ROW_IN + foot_h + margin
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor("white")

    # 제목 바 없음(위클리에 바로 붙이는 용도) — 기준일은 하단 각주에
    for c, lst in cols.items():
        x_in = margin + c * (tw + mid_gap)
        y_in = margin + title_h
        for sec, rows in lst:
            h_in = section_height_units(sec) * ROW_IN
            ax = fig.add_axes([x_in / fig_w, 1 - (y_in + h_in) / fig_h, tw / fig_w, h_in / fig_h])
            draw_section(ax, sec, rows, caps, scales)
            y_in += h_in + gap_units * ROW_IN

    fig.text(margin / fig_w, (margin * 0.6) / fig_h,
             f"기준일 {asof:%Y.%m.%d}  |  자료: Yahoo Finance  |  등락률은 현지통화 종가 기준, 거래일 오프셋 1W=5·1M=21·3M=63·1Y=252, "
             "YTD=전년 마지막 종가 대비  |  시총은 USD 백만달러  |  "
             f"스파크라인: 최근 {SPARK_DAYS}거래일 (점선=기간 시작가)",
             fontsize=8.5, color=MUTED, va="bottom")
    save_fig(fig, path)


def save_fig(fig, path):
    """PNG + 같은 이름의 SVG(벡터). 엑셀/PPT에 SVG로 넣으면 확대해도 선명하다."""
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.rcParams["svg.fonttype"] = "path"   # 글꼴을 외곽선으로 박아 받는 쪽 폰트와 무관
    fig.savefig(os.path.splitext(path)[0] + ".svg", facecolor="white")
    plt.close(fig)


def render_single(sec, rows, caps, scales, path):
    W_units = table_width_units()
    pad = 0.08
    w = W_units * COL_IN + 2 * pad
    h = section_height_units(sec) * ROW_IN + 2 * pad
    fig = plt.figure(figsize=(w, h), dpi=DPI)
    ax = fig.add_axes([pad / w, pad / h, 1 - 2 * pad / w, 1 - 2 * pad / h])
    draw_section(ax, sec, rows, caps, scales)
    save_fig(fig, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="가짜 데이터로 레이아웃만 확인")
    ap.add_argument("--universe", default="ship", choices=sorted(UNIVERSES),
                    help="종목 구성: ship(조선·해운, 기본) / defense(방산·항공우주) / construction(건설기계)")
    ap.add_argument("--out", default=None, help="출력 폴더(기본: 유니버스별 output/peer_price*)")
    ap.add_argument("--no-split", action="store_true", help="2페이지 분할본(SPLIT_PAGES) 생성 생략")
    args = ap.parse_args()
    select_universe(args.universe)
    if args.out is None:
        args.out = OUTPUT_DIR

    setup_font()
    tickers = all_tickers()
    print(f"📈 [{args.universe}] {len(tickers)}개 종목 {'(데모)' if args.demo else '야후 수집'} 시작...")
    if args.demo:
        prices, caps = demo_data(tickers)
    else:
        prices = fetch_prices(tickers)
        caps = fetch_market_caps_usd_m([t for t in tickers if t in prices])

    metrics = {t: compute_metrics(s) for t, s in prices.items()}
    # 기준일 = 주식(시총 섹션) 가운데 평일 날짜의 최대. 선물·환율은 일요일 봉이 있고, 야후가 간혹 주말
    # 타임스탬프의 행을 섞어 주므로 max 를 그대로 쓰면 일요일 날짜가 찍힌다(11/8 실측). 주말 행은 로그로 남긴다.
    stock_t = {t for sec in SECTIONS if sec.get("market_cap", True) for _, items in sec["groups"] for _, t in items}
    weekend = {t: m["last_date"] for t, m in metrics.items() if m["last_date"].weekday() >= 5}
    if weekend:
        print("ℹ️ 주말 날짜 마지막 봉: " + ", ".join(f"{t} {d:%m/%d}" for t, d in weekend.items()))
    cands = [m["last_date"] for t, m in metrics.items() if t in stock_t and m["last_date"].weekday() < 5]
    asof = max(cands) if cands else max(m["last_date"] for m in metrics.values())

    sections_rows = [(sec, section_rows(sec, metrics)) for sec in SECTIONS]
    # 막대 스케일은 원자재(지수)를 빼고 주식만으로
    stock_rows = [r for sec, rows in sections_rows if sec.get("market_cap", True) for r in rows]
    scales = column_scales(stock_rows)

    os.makedirs(args.out, exist_ok=True)
    page = os.path.join(args.out, PAGE_FILE)
    render_page(sections_rows, caps, scales, asof, page)
    print(f"🖼  {page}")
    for fn, sub, layout in ([] if args.no_split else SPLIT_PAGES):
        path = os.path.join(args.out, fn)
        render_page(sections_rows, caps, scales, asof, path, layout=layout, subtitle=sub)
        print(f"🖼  {path}")
    for i, (sec, rows) in enumerate(sections_rows, 1):
        fn = sec.get("file") or f"{i:02d}_{sec['title'].replace(' / ', '_').replace('/', '_').replace(' ', '')}"
        fn += ".png"
        render_single(sec, rows, caps, scales, os.path.join(args.out, fn))
        print(f"🖼  {os.path.join(args.out, fn)}")

    missing = [t for t in tickers if t not in prices]
    if missing:
        print(f"⚠️ 데이터 없는 종목 {len(missing)}개: {', '.join(missing)}")
    print("✨ 완료")


if __name__ == "__main__":
    main()

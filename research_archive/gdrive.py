# -*- coding: utf-8 -*-
"""Google Drive 업로드 + Google Sheets Master Index + 상태(state) 저장.

서비스 계정 사용. 사용자가 만든 "Research Reports" 폴더를 서비스 계정
이메일에 '편집자'로 공유하고 GDRIVE_ROOT_FOLDER_ID 를 지정하는 방식 권장.
공유 드라이브(Shared Drive)도 지원(supportsAllDrives).
"""
from __future__ import annotations

import io
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _parse_sa_json(raw: str) -> dict:
    """서비스 계정 JSON 파싱. 복사 실수(앞뒤 누락/공백/BOM)를 최대한 복구."""
    s = raw.strip().lstrip("﻿")
    candidates = [s]
    if not s.startswith("{"):
        candidates.append("{" + s)          # 첫 줄 '{' 누락
    if not s.endswith("}"):
        candidates += [c + "}" for c in list(candidates)]  # 마지막 '}' 누락
    for c in candidates:
        try:
            d = json.loads(c)
            if isinstance(d, dict) and d.get("private_key"):
                return d
        except json.JSONDecodeError:
            continue
    raise RuntimeError(
        "GDRIVE_SERVICE_ACCOUNT_JSON 시크릿이 올바른 서비스 계정 JSON이 아닙니다. "
        "다운로드한 .json 키 파일을 메모장으로 열어 Ctrl+A(전체 선택) → Ctrl+C로 "
        "복사한 뒤, GitHub Secret을 삭제하고 다시 등록하세요. "
        "내용은 반드시 '{'로 시작해 '}'로 끝나야 합니다.")


def _credentials():
    # 사용자 OAuth 우선 (개인 Gmail: 서비스 계정은 저장용량 0이라 업로드 불가)
    if config.GDRIVE_OAUTH_REFRESH_TOKEN:
        from google.oauth2.credentials import Credentials as UserCredentials
        if not (config.GDRIVE_OAUTH_CLIENT_ID and config.GDRIVE_OAUTH_CLIENT_SECRET):
            raise RuntimeError(
                "GDRIVE_OAUTH_REFRESH_TOKEN을 쓰려면 GDRIVE_OAUTH_CLIENT_ID와 "
                "GDRIVE_OAUTH_CLIENT_SECRET도 함께 설정해야 합니다.")
        return UserCredentials(
            token=None,
            refresh_token=config.GDRIVE_OAUTH_REFRESH_TOKEN.strip(),
            client_id=config.GDRIVE_OAUTH_CLIENT_ID.strip(),
            client_secret=config.GDRIVE_OAUTH_CLIENT_SECRET.strip(),
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES)
    raw = config.GDRIVE_SA_JSON
    if not raw:
        raise RuntimeError(
            "Google 인증 정보가 없습니다. GDRIVE_OAUTH_* 3종(권장) 또는 "
            "GDRIVE_SERVICE_ACCOUNT_JSON을 설정하세요.")
    if os.path.isfile(raw):
        return service_account.Credentials.from_service_account_file(
            raw, scopes=SCOPES)
    return service_account.Credentials.from_service_account_info(
        _parse_sa_json(raw), scopes=SCOPES)


class DriveStore:
    def __init__(self):
        creds = _credentials()
        self.drive = build("drive", "v3", credentials=creds,
                           cache_discovery=False)
        self.sheets = build("sheets", "v4", credentials=creds,
                            cache_discovery=False)
        self._folder_cache: dict[tuple[str, str], str] = {}
        self.root_id = self._resolve_root()

    # ── 폴더 ─────────────────────────────────────────────────────────
    def _query(self, q: str) -> list[dict]:
        res = self.drive.files().list(
            q=q, fields="files(id,name,mimeType,webViewLink)",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
            pageSize=50).execute()
        return res.get("files", [])

    def _resolve_root(self) -> str:
        if config.GDRIVE_ROOT_FOLDER_ID:
            return config.GDRIVE_ROOT_FOLDER_ID
        files = self._query(
            f"name = '{config.ROOT_FOLDER_NAME}' and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false")
        if files:
            return files[0]["id"]
        raise RuntimeError(
            f"'{config.ROOT_FOLDER_NAME}' 폴더를 찾지 못했습니다. Drive에 폴더를 만들고 "
            "서비스 계정 이메일에 공유한 뒤 GDRIVE_ROOT_FOLDER_ID를 지정하세요.")

    def ensure_folder(self, parent_id: str, name: str) -> str:
        key = (parent_id, name)
        if key in self._folder_cache:
            return self._folder_cache[key]
        safe = name.replace("'", "\\'")
        files = self._query(
            f"name = '{safe}' and '{parent_id}' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false")
        if files:
            fid = files[0]["id"]
        else:
            meta = {"name": name, "parents": [parent_id],
                    "mimeType": "application/vnd.google-apps.folder"}
            fid = self.drive.files().create(
                body=meta, fields="id", supportsAllDrives=True).execute()["id"]
        self._folder_cache[key] = fid
        return fid

    def industry_year_folder(self, industry: str, year: str) -> str:
        ind_id = self.ensure_folder(self.root_id, industry)
        return self.ensure_folder(ind_id, year)

    # ── 파일 ─────────────────────────────────────────────────────────
    def upload_pdf(self, folder_id: str, filename: str, data: bytes) -> str:
        """업로드 후 webViewLink 반환. 같은 이름이 있으면 (2) 붙임."""
        safe = filename.replace("'", "\\'")
        if self._query(f"name = '{safe}' and '{folder_id}' in parents "
                       "and trashed = false"):
            stem, ext = os.path.splitext(filename)
            filename = f"{stem} (2){ext}"
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/pdf",
                                  resumable=True)
        f = self.drive.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media, fields="id,webViewLink",
            supportsAllDrives=True).execute()
        return f.get("webViewLink", f"https://drive.google.com/file/d/{f['id']}/view")

    # ── 상태 파일 ────────────────────────────────────────────────────
    def _find_state(self) -> str | None:
        files = self._query(
            f"name = '{config.STATE_FILE_NAME}' and '{self.root_id}' in parents "
            "and trashed = false")
        return files[0]["id"] if files else None

    def load_state(self) -> dict:
        fid = self._find_state()
        if not fid:
            return {}
        buf = io.BytesIO()
        req = self.drive.files().get_media(fileId=fid, supportsAllDrives=True)
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        try:
            return json.loads(buf.getvalue().decode("utf-8"))
        except Exception:
            return {}

    def save_state(self, state: dict) -> None:
        data = json.dumps(state, ensure_ascii=False, indent=1).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/json")
        fid = self._find_state()
        if fid:
            self.drive.files().update(fileId=fid, media_body=media,
                                      supportsAllDrives=True).execute()
        else:
            self.drive.files().create(
                body={"name": config.STATE_FILE_NAME, "parents": [self.root_id]},
                media_body=media, fields="id",
                supportsAllDrives=True).execute()

    # ── Master Index (Google Sheets) ─────────────────────────────────
    def ensure_index_sheet(self) -> str:
        if config.MASTER_INDEX_SHEET_ID:
            sid = config.MASTER_INDEX_SHEET_ID
        else:
            files = self._query(
                f"name = '{config.MASTER_INDEX_NAME}' and "
                f"'{self.root_id}' in parents and trashed = false and "
                "mimeType = 'application/vnd.google-apps.spreadsheet'")
            if files:
                sid = files[0]["id"]
            else:
                f = self.drive.files().create(body={
                    "name": config.MASTER_INDEX_NAME,
                    "parents": [self.root_id],
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                }, fields="id", supportsAllDrives=True).execute()
                sid = f["id"]
        self._ensure_header(sid)
        return sid

    def _ensure_header(self, sheet_id: str) -> None:
        res = self.sheets.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="A1:R1").execute()
        row = res.get("values", [[]])
        if not row or row[0] != config.INDEX_COLUMNS:
            self.sheets.spreadsheets().values().update(
                spreadsheetId=sheet_id, range="A1",
                valueInputOption="RAW",
                body={"values": [config.INDEX_COLUMNS]}).execute()

    def append_rows(self, sheet_id: str, rows: list[list[str]]) -> None:
        if not rows:
            return
        self.sheets.spreadsheets().values().append(
            spreadsheetId=sheet_id, range="A1",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": rows}).execute()

    def read_all_rows(self, sheet_id: str) -> list[list[str]]:
        res = self.sheets.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="A2:R100000").execute()
        return res.get("values", [])

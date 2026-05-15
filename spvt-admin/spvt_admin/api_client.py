from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import certifi
import requests
import urllib3


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class LoginResult:
    access_token: str
    role: str
    full_name: str
    username: str


class SpvtApiClient:
    def __init__(self, base_url: str, timeout: float = 60.0, *, verify_ssl: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: str | None = None
        self._session = requests.Session()
        if verify_ssl:
            self._session.verify = certifi.where()
        else:
            self._session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def token(self) -> str | None:
        return self._token

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _headers(self, json: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if json:
            headers["Content-Type"] = "application/json"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _raise_for_response(self, response: requests.Response) -> None:
        if response.ok:
            return
        detail = "Ошибка запроса"
        if response.status_code == 413:
            raise ApiError(
                "Файл слишком большой для сервера (лимит 25 МБ). "
                "Сожмите изображение или выберите файл меньшего размера.",
                response.status_code,
            )
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("detail"):
                detail = str(payload["detail"])
        except ValueError:
            text = (response.text or "").strip()
            if text and len(text) < 300 and "<html" not in text.lower():
                detail = text
        raise ApiError(detail, response.status_code)

    def login(self, username: str, password: str) -> LoginResult:
        response = self._session.post(
            self._url("/api/auth/login"),
            data={"username": username, "password": password},
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        data = response.json()
        self._token = data["access_token"]
        return LoginResult(
            access_token=data["access_token"],
            role=data["role"],
            full_name=data["full_name"],
            username=username,
        )

    def get_dashboard(self, shift_date: str | None = None) -> dict[str, Any]:
        params = {}
        if shift_date:
            params["shift_date"] = shift_date
        response = self._session.get(
            self._url("/api/manager/dashboard"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

    def export_powerbi_csv(self, shift_date: str | None = None) -> bytes:
        params = {}
        if shift_date:
            params["shift_date"] = shift_date
        response = self._session.get(
            self._url("/api/manager/export/powerbi"),
            params=params,
            headers={**self._headers(json=False), "Accept": "text/csv"},
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.content

    def reset_attempts(
        self, shift_date: str | None = None, username: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if shift_date:
            params["shift_date"] = shift_date
        if username:
            params["username"] = username
        response = self._session.post(
            self._url("/api/manager/reset-attempt"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

    def get_settings(self) -> dict[str, Any]:
        response = self._session.get(
            self._url("/api/admin/settings"),
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._session.put(
            self._url("/api/admin/settings"),
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

    def _file_upload_tuple(self, file_path: str) -> tuple[str, object, str]:
        path = Path(file_path)
        mime, _ = mimetypes.guess_type(path.name)
        if mime not in {"image/png", "image/jpeg", "image/webp"}:
            suffix = path.suffix.lower()
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }.get(suffix, "image/png")
        return path.name, path.open("rb"), mime

    def upload_background(self, file_path: str) -> dict[str, Any]:
        name, file_obj, mime = self._file_upload_tuple(file_path)
        try:
            response = self._session.post(
                self._url("/api/admin/upload/background"),
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                files={"file": (name, file_obj, mime)},
                timeout=self.timeout,
            )
        finally:
            file_obj.close()
        self._raise_for_response(response)
        return response.json()

    def upload_logo(self, file_path: str) -> dict[str, Any]:
        name, file_obj, mime = self._file_upload_tuple(file_path)
        try:
            response = self._session.post(
                self._url("/api/admin/upload/logo"),
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                files={"file": (name, file_obj, mime)},
                timeout=self.timeout,
            )
        finally:
            file_obj.close()
        self._raise_for_response(response)
        return response.json()

    def list_questions(self) -> list[dict[str, Any]]:
        response = self._session.get(
            self._url("/api/admin/questions"),
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

    def create_question(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._session.post(
            self._url("/api/admin/questions"),
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

    def update_question(self, question_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._session.put(
            self._url(f"/api/admin/questions/{question_id}"),
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

    def delete_question(self, question_id: int) -> dict[str, Any]:
        response = self._session.delete(
            self._url(f"/api/admin/questions/{question_id}"),
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        return response.json()

"""Small server-side Feishu Open Platform client.

Secrets and access tokens never leave the backend.  The client deliberately
keeps the integration surface narrow: login identity plus Contact user detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_REDIRECT_URI


FEISHU_API = "https://open.feishu.cn/open-apis"


class FeishuError(RuntimeError):
    pass


@dataclass
class FeishuIdentity:
    open_id: str
    union_id: str | None
    user_id: str | None
    name: str
    avatar_url: str | None
    department_ids: list[str]
    department_names: list[str]
    job_title_id: str | None
    job_title_name: str | None


def configured() -> bool:
    return bool(FEISHU_APP_ID and FEISHU_APP_SECRET and FEISHU_REDIRECT_URI)


def browser_login_url(state: str) -> str:
    if not configured():
        raise FeishuError("飞书应用尚未配置")
    return FEISHU_API + "/authen/v1/index?" + urlencode({
        "app_id": FEISHU_APP_ID,
        "redirect_uri": FEISHU_REDIRECT_URI,
        "state": state,
    })


def _post_json(client: httpx.Client, url: str, body: dict, headers: dict | None = None) -> dict:
    try:
        response = client.post(url, json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise FeishuError("飞书认证服务暂时不可用") from exc
    if payload.get("code", 0) != 0:
        raise FeishuError(payload.get("msg") or "飞书接口调用失败")
    return payload


def _app_access_token(client: httpx.Client) -> str:
    payload = _post_json(client, FEISHU_API + "/auth/v3/app_access_token/internal", {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    })
    token = payload.get("app_access_token")
    if not token:
        raise FeishuError("飞书未返回 app_access_token")
    return token


def _tenant_access_token(client: httpx.Client) -> str:
    payload = _post_json(client, FEISHU_API + "/auth/v3/tenant_access_token/internal", {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    })
    token = payload.get("tenant_access_token")
    if not token:
        raise FeishuError("飞书未返回 tenant_access_token")
    return token


def exchange_code(code: str) -> FeishuIdentity:
    if not configured():
        raise FeishuError("飞书应用尚未配置")
    if not code or len(code) > 2048:
        raise FeishuError("飞书授权码无效")

    with httpx.Client(timeout=12.0) as client:
        app_token = _app_access_token(client)
        token_payload = _post_json(
            client,
            FEISHU_API + "/authen/v1/access_token",
            {
                "grant_type": "authorization_code",
                "code": code,
                "app_id": FEISHU_APP_ID,
                "app_secret": FEISHU_APP_SECRET,
            },
            {"Authorization": "Bearer " + app_token},
        )
        user_token = (token_payload.get("data") or {}).get("access_token")
        if not user_token:
            raise FeishuError("飞书未返回 user_access_token")

        try:
            user_response = client.get(
                FEISHU_API + "/authen/v1/user_info",
                headers={"Authorization": "Bearer " + user_token},
            )
            user_response.raise_for_status()
            user_payload = user_response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FeishuError("无法读取飞书用户信息") from exc
        if user_payload.get("code", 0) != 0:
            raise FeishuError(user_payload.get("msg") or "无法读取飞书用户信息")
        user = user_payload.get("data") or {}
        open_id = user.get("open_id")
        if not open_id:
            raise FeishuError("飞书用户信息缺少 open_id")

        contact: dict = {}
        department_names: list[str] = []
        try:
            tenant_token = _tenant_access_token(client)
            contact_response = client.get(
                f"{FEISHU_API}/contact/v3/users/{open_id}",
                params={"user_id_type": "open_id"},
                headers={"Authorization": "Bearer " + tenant_token},
            )
            contact_response.raise_for_status()
            contact_payload = contact_response.json()
            if contact_payload.get("code", 0) == 0:
                contact = (contact_payload.get("data") or {}).get("user") or {}
        except (httpx.HTTPError, ValueError, FeishuError):
            # Login identity still works when the app has not yet been granted
            # Contact scope.  Such a user maps to no role until scope is fixed.
            contact = {}

        avatar = user.get("avatar_url") or contact.get("avatar", {}).get("avatar_240")
        job_title_name = contact.get("job_title") or user.get("job_title")
        return FeishuIdentity(
            open_id=open_id,
            union_id=user.get("union_id") or contact.get("union_id"),
            user_id=user.get("user_id") or contact.get("user_id"),
            name=contact.get("name") or user.get("name") or "飞书用户",
            avatar_url=avatar,
            department_ids=[str(value) for value in contact.get("department_ids") or []],
            department_names=department_names,
            job_title_id=contact.get("job_title_id"),
            job_title_name=job_title_name,
        )

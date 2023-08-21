from typing import Annotated, Dict, Literal, Optional, Union
from pydantic import BaseModel, Field, parse_obj_as
from urllib.parse import urlencode
from base64 import b64decode, b64encode
import json
import jwt
import requests
from google.oauth2 import id_token
import google.auth.transport
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from fastapi.security.utils import get_authorization_scheme_param


from splitgraph_chatgpt_plugin.config import (
    GOOGLE_AUTH_FLOW_COMPLETE_PATH,
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    PLUGIN_DOMAIN,
    get_oauth_client_id_openai,
    get_plugin_jwt_secret,
)


class OAuthContext(BaseModel):
    state: str
    redirect_uri: str


class GoogleIDTokenPayload(BaseModel):
    # JWT claim descriptions from: https://developers.google.com/identity/openid-connect/openid-connect#an-id-tokens-payload
    # An identifier for the user, unique among all Google accounts and never reused. A Google account can have multiple email addresses at different points in time, but the sub value is never changed. Use sub within your application as the unique-identifier key for the user. Maximum length of 255 case-sensitive ASCII characters.
    sub: str
    # The user's email address. This value may not be unique to this user and is not suitable for use as a primary key. Provided only if your scope included the email scope value.
    email: str
    # True if the user's e-mail address has been verified; otherwise false.
    email_verified: str
    name: Optional[str]
    picture: Optional[str]
    given_name: Optional[str]
    family_name: Optional[str]
    locale: Optional[str]  # eg: "en"


class GoogleAuthResult(BaseModel):
    access_token: str
    refresh_token: Optional[str]
    id_token_payload: GoogleIDTokenPayload


TokenGrant = Literal["code", "access", "refresh"]


class PluginTokenPayload(BaseModel):
    sub: str
    iss: str
    aud: str
    iat: int
    exp: int
    nbf: int
    email: str
    grant: TokenGrant


class OpenAIAuthorizationCodeRequest(BaseModel):
    grant_type: Literal["authorization_code"]
    client_id: str
    client_secret: str
    code: str
    redirect_uri: str


class OpenAIAuthorizationRefreshRequest(BaseModel):
    grant_type: Literal["refresh_token"]
    refresh_token: str
    client_id: str
    client_secret: str


OpenAIAuthorizationRequest = Annotated[
    Union[OpenAIAuthorizationCodeRequest, OpenAIAuthorizationRefreshRequest],
    Field(discriminator="grant_type"),
]


def parse_openai_authorization_request(
    request: Dict[str, str]
) -> OpenAIAuthorizationRequest:
    return parse_obj_as(OpenAIAuthorizationRequest, request)  # type: ignore


# source: https://platform.openai.com/docs/plugins/authentication/oauth
# The authorization_url endpoint should return a response that looks like: { "access_token": "example_token", "token_type": "bearer", "refresh_token": "example_token", "expires_in": 59 }
# During the user sign in process, ChatGPT makes a request to your authorization_url using the specified authorization_content_type, we expect to get back an access token and optionally a refresh token which we use to periodically fetch a new access token.
class OpenAIAuthorizationResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    refresh_token: str
    expires_in: int


def serialize_auth_context(oauth_context: OAuthContext) -> str:
    return b64encode(json.dumps(oauth_context.dict()).encode("ascii")).decode("ascii")


def deserialize_auth_context(oauth_context_str: str) -> OAuthContext:
    return OAuthContext.parse_obj(
        json.loads(b64decode(oauth_context_str).decode("ascii"))
    )


def get_google_auth_flow_complete_redirect_uri():
    return f"https://{PLUGIN_DOMAIN}{GOOGLE_AUTH_FLOW_COMPLETE_PATH}"


def get_google_sign_in_url(client_id: str, scope: str, state: str):
    # based on: https://developers.google.com/identity/protocols/oauth2/web-server#redirecting
    qs = urlencode(
        {
            "response_type": "code",
            "access_type": "offline",
            "client_id": client_id,
            "redirect_uri": get_google_auth_flow_complete_redirect_uri(),
            "scope": scope,
            "state": state,
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"


def get_openai_oauth_callback_url(code: str, state: str) -> str:
    oauth_context = deserialize_auth_context(state)
    qs = urlencode({"code": code, "state": oauth_context.state})
    return f"{oauth_context.redirect_uri}?{qs}"


# based on: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token#using-a-google-api-client-library
def parse_id_token(id_token_str, client_id) -> Dict[str, str]:
    return id_token.verify_oauth2_token(
        id_token_str, google.auth.transport.requests.Request(), client_id
    )


# based on: https://developers.google.com/identity/protocols/oauth2/web-server#exchange-authorization-code
def get_google_auth_result(
    code: str, client_id: str, client_secret: str
) -> GoogleAuthResult:
    response: Dict[str, str] = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": f"https://{PLUGIN_DOMAIN}{GOOGLE_AUTH_FLOW_COMPLETE_PATH}",
            "grant_type": "authorization_code",
        },
    ).json()

    assert response["token_type"] == "Bearer"
    parsed_id_token = parse_id_token(response["id_token"], client_id)
    return GoogleAuthResult(
        access_token=response.get("access_token"),
        refresh_token=response.get("refresh_token"),
        id_token_payload=GoogleIDTokenPayload.parse_obj(parsed_id_token),
    )


def encode_jwt_token(
    sub: str,
    email: str,
    grant: TokenGrant,
    expiration=JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    creation_timestamp: Optional[datetime] = None,
    aud=get_oauth_client_id_openai(),
    secret=get_plugin_jwt_secret(),
) -> str:
    now = creation_timestamp or datetime.now(tz=timezone.utc)
    payload = PluginTokenPayload(
        sub=sub,
        iss=PLUGIN_DOMAIN,
        aud=aud,
        iat=now.timestamp(),
        exp=(now + timedelta(seconds=expiration)).timestamp(),
        nbf=(now + timedelta(seconds=-2)).timestamp(),
        grant=grant,
        email=email,
    )
    return jwt.encode(payload=payload.dict(), key=secret, algorithm="HS256")


def decode_jwt_token(
    token: str, aud=get_oauth_client_id_openai(), secret=get_plugin_jwt_secret()
) -> PluginTokenPayload:
    return PluginTokenPayload.parse_obj(
        jwt.decode(
            token, key=secret, audience=aud, issuer=PLUGIN_DOMAIN, algorithms=["HS256"]
        )
    )


# inspired by: https://testdriven.io/blog/fastapi-jwt-auth/
def assert_authorized(request: Request) -> PluginTokenPayload:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=403, detail="Missing Authorization header.")
    scheme, token = get_authorization_scheme_param(authorization)
    if not scheme == "Bearer":
        raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
    try:
        return decode_jwt_token(token)
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=403, detail="Invalid token or expired token.")

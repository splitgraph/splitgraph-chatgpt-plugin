from pydantic import BaseModel
from urllib.parse import urlencode
from base64 import b64decode, b64encode
import json
import jwt
import requests

from splitgraph_chatgpt_plugin.config import GOOGLE_AUTH_FLOW_COMPLETE_PATH, PLUGIN_DOMAIN

class OAuthContext(BaseModel):
    state: str
    redirect_uri: str

class TokenPayload(BaseModel):
    # JWT claim descriptions from: https://developers.google.com/identity/openid-connect/openid-connect#an-id-tokens-payload
    # An identifier for the user, unique among all Google accounts and never reused. A Google account can have multiple email addresses at different points in time, but the sub value is never changed. Use sub within your application as the unique-identifier key for the user. Maximum length of 255 case-sensitive ASCII characters.
    sub: str
    # The user's email address. This value may not be unique to this user and is not suitable for use as a primary key. Provided only if your scope included the email scope value.
    email: str
    # True if the user's e-mail address has been verified; otherwise false.
    email_verified: str


def serialize_auth_context(oauth_context:OAuthContext)->str:
    return b64encode(json.dumps(oauth_context.dict()).encode('ascii')).decode('ascii')

def deserialize_auth_context(oauth_context_str:str)->OAuthContext:
    return OAuthContext.parse_obj(json.loads(b64decode(oauth_context_str).decode('ascii')))

def get_google_auth_flow_complete_redirect_uri():
    return f"https://{PLUGIN_DOMAIN}{GOOGLE_AUTH_FLOW_COMPLETE_PATH}"

def get_google_sign_in_url(client_id: str, scope:str, state:str):
    # based on: https://developers.google.com/identity/protocols/oauth2/web-server#redirecting
    qs = urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': get_google_auth_flow_complete_redirect_uri(),
        'scope': scope,
        'state': state
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"

def get_openai_oauth_callback_url(code:str, state:str)->str:
    oauth_context = deserialize_auth_context(state)
    qs = urlencode({
        'code': code,
        'state': oauth_context.state
    })
    return f"{oauth_context.redirect_uri}?{qs}"

def get_google_oauth_token(code:str, client_id: str, client_secret:str):
    response = requests.post('https://oauth2.googleapis.com/token', data={
      'code': code,
      'client_id': client_id,
      'client_secret': client_secret,
      'redirect_uri': get_google_auth_flow_complete_redirect_uri(),
      'grant_type': 'authorization_code'
    }).json()


def make_jwt_token(secret: str, payload:TokenPayload)->str:
    return jwt.encode(
    payload=payload.dict(),
    key=secret
)

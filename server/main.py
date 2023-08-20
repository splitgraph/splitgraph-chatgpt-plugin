# This is a version of the main.py file found in ../../../server/main.py for testing the plugin locally.
# Use the command `poetry run dev` to run this.
from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from starlette.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware
from .auth import (
    OAuthContext,
    OpenAIAuthorizationResponse,
    decode_jwt_token,
    deserialize_auth_context,
    get_google_auth_result,
    get_google_sign_in_url,
    get_openai_oauth_callback_url,
    encode_jwt_token,
    parse_openai_authorization_request,
    serialize_auth_context,
)
from splitgraph_chatgpt_plugin.config import (
    GOOGLE_AUTH_FLOW_COMPLETE_PATH,
    DOCUMENT_COLLECTION_NAME,
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    JWT_REFRESH_TOKEN_LIFETIME_SECONDS,
    get_oauth_client_id_google,
    get_oauth_client_id_openai,
    get_oauth_client_secret_google,
    get_openai_api_key,
    get_db_connection_string,
    get_plugin_jwt_secret,
)
from splitgraph_chatgpt_plugin.ddn import get_table_infos, run_sql as _run_sql
from splitgraph_chatgpt_plugin.models import FindRelevantTablesResponse, RunSQLResponse

from splitgraph_chatgpt_plugin.persistence import (
    connect,
    find_repos,
    get_embedding_store_pgvector,
)
from langchain.vectorstores import VectorStore

app = FastAPI()
PORT = 3333

origins = [
    f"http://localhost:{PORT}",
    "https://chat.openai.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vstore: Optional[VectorStore] = None


@app.route("/.well-known/ai-plugin.json")
async def get_manifest(request):
    file_path = "./server/ai-plugin.json"
    simple_headers = {}
    simple_headers["Access-Control-Allow-Private-Network"] = "true"
    return FileResponse(file_path, media_type="text/json", headers=simple_headers)


@app.route("/.well-known/logo.png")
async def get_logo(request):
    file_path = "./server/logo.png"
    return FileResponse(file_path, media_type="image/png")


@app.route("/.well-known/openapi.json")
async def get_openapi(request):
    file_path = "./server/openapi.json"
    return FileResponse(file_path, media_type="text/json")


@app.get("/find_relevant_tables", response_model=FindRelevantTablesResponse)
async def find_relevant_tables(prompt: Optional[str] = None):
    global vstore
    try:
        if prompt is None:
            raise Exception("Prompt is None")
        if vstore is not None:
            repositories = find_repos(vstore, prompt)
            return FindRelevantTablesResponse(
                tables=get_table_infos(
                    repositories, use_fully_qualified_table_names=True
                )
            )
        raise Exception("vstore uninitialized")
    except Exception as e:
        import traceback

        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.get("/run_sql", response_model=RunSQLResponse)
async def run_sql(query: Optional[str] = None):
    global vstore
    try:
        if query is None:
            raise Exception("No sql query provided")
        response = _run_sql(query)
        return response
    except Exception as e:
        import traceback

        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Service Error")


# Step 1: Start of auth flow, initial request made by ChatGPT to authenticate user upon plugin installation
# Request URL parameters documented at: https://platform.openai.com/docs/plugins/authentication/oauth
@app.get("/auth/init_auth_flow")
async def init_auth_flow(
    response_type: str, client_id: str, redirect_uri: str, scope: str, state: str
):
    # response_type should be "code"
    assert response_type == "code"
    assert client_id == get_oauth_client_id_openai()
    # We'll need redirect_uri and state on the final callback to OpenAI,
    # so we need encode these in the state parameter passed to Google.
    auth_context = OAuthContext(state=state, redirect_uri=redirect_uri)
    # Redirect the browser to Google sign in page
    return RedirectResponse(
        get_google_sign_in_url(
            client_id=get_oauth_client_id_google(),
            scope=scope,
            state=serialize_auth_context(auth_context),
        )
    )


# Step 2 is the Google signin consent screen, which -upon success- redirects to:


# Step 3: the completion of the Google OAuth signin flow
@app.get(GOOGLE_AUTH_FLOW_COMPLETE_PATH)
async def oauth_callback_from_google(code: str, state: str):
    # redirect to the next step, the OpenAI callback URL
    # The code returned to OpenAI is not the same code we got from google.
    auth_result = get_google_auth_result(
        code, get_oauth_client_id_google(), get_oauth_client_secret_google()
    )
    print(auth_result)
    openai_code = encode_jwt_token(
        auth_result.id_token_payload.sub, auth_result.id_token_payload.email, "code"
    )
    return RedirectResponse(get_openai_oauth_callback_url(openai_code, state))


# Step 4: OpenAI receives the callback with the OAuth authentication code and state variables.
# At this point OAuth authentication is complete since we have a code, but don't have an access token yet.

# Step 5: Exchange the OAuth code for an access token
# upon completion of the authentication flow, OpenAI makes a POST request with a JSON body to the
# the endpoint specified in ai-plugin.json's auth.authorization_url field to exchange the
# code for a JWT access token.


@app.post("/auth/oauth_exchange")
async def oauth_exchange(info: Request):
    raw_body = await info.json()
    print(raw_body)
    raw_body['grant_type'] = raw_body.get('grant_type', 'authorization_code')
    request = parse_openai_authorization_request(raw_body)
    if request.grant_type == "authorization_code":
        code_payload = decode_jwt_token(request.code)
        assert code_payload.grant == "code"
        return OpenAIAuthorizationResponse(
            token_type="bearer",
            access_token=encode_jwt_token(
                code_payload.sub, code_payload.email, "access"
            ),
            refresh_token=encode_jwt_token(
                code_payload.sub,
                code_payload.email,
                "refresh",
                JWT_REFRESH_TOKEN_LIFETIME_SECONDS,
            ),
            expires_in=JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
        )
    # if not authorization_code request, then it must be a refresh_token request
    assert request.grant_type == "refresh_token"
    refresh_payload = decode_jwt_token(request.refresh_token)
    assert refresh_payload.grant == "refresh"
    return OpenAIAuthorizationResponse(
        token_type="bearer",
        access_token=encode_jwt_token(
            refresh_payload.sub, refresh_payload.email, "access"
        ),
        refresh_token=encode_jwt_token(
            refresh_payload.sub,
            refresh_payload.email,
            "refresh",
            JWT_REFRESH_TOKEN_LIFETIME_SECONDS,
        ),
        expires_in=JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    )
    # TODO: if refresh token has expired

@app.on_event("startup")
async def startup():
    global openai_api_key
    global vstore
    openai_api_key = get_openai_api_key()
    vstore = get_embedding_store_pgvector(
        connect(get_db_connection_string()), DOCUMENT_COLLECTION_NAME, openai_api_key
    )


def start():
    uvicorn.run("server.main:app", host="localhost", port=PORT, reload=True)


if __name__ == "__main__":
    start()

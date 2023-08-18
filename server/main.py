# This is a version of the main.py file found in ../../../server/main.py for testing the plugin locally.
# Use the command `poetry run dev` to run this.
from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from starlette.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware
from .auth import OAuthContext, deserialize_auth_context, get_google_auth_flow_complete_redirect_uri, get_google_sign_in_url, get_openai_oauth_callback_url, serialize_auth_context
from splitgraph_chatgpt_plugin.config import (
    GOOGLE_AUTH_FLOW_COMPLETE_PATH,
    DOCUMENT_COLLECTION_NAME,
    get_openai_api_key,
    get_db_connection_string,
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
async def init_auth_flow(response_type: str, client_id: str, redirect_uri: str, scope:str, state:str):
    # response_type should be "code"
    assert response_type == "code"
    # We'll need redirect_uri and state on the final callback to OpenAI,
    # so we need encode these in the state parameter passed to Google.
    oauth_context = OAuthContext(state=state, redirect_uri=redirect_uri)
    # Redirect the browser to Google sign in page
    return RedirectResponse(get_google_sign_in_url(
        client_id=client_id,
        redirect_uri=get_google_sign_in_url(client_id, scope, state),
        scope=scope,
        state=serialize_auth_context(oauth_context)))

# Step 2 is the Google signin consent screen, which -upon success- redirects to:

# Step 3: the completion of the Google OAuth signin flow
@app.get(GOOGLE_AUTH_FLOW_COMPLETE_PATH)
async def oauth_callback_from_google(code:str, state:str):
    # redirect to the next step, the OpenAI callback URL
    return RedirectResponse(get_openai_oauth_callback_url(code, state))

# Step 4: OpenAI receives the callback with the OAuth authentication code and state variables.
# At this point OAuth authentication is complete (we have a code), but don't have an access token yet.

# Step 5: Exchange the OAuth code for an access token
# upon completion of the authentication flow, it makes a POST request with a JSON body to the
# the endpoint specified in ai-plugin.json's auth.authorization_url field to exchange the
# code for a JWT access token.

@app.post("/auth/oauth_exchange")
async def oauth_exchange(info: Request):
    request = info.json()
    import pprint
    pprint.pprint(request)
    if request["client_id"] != OPENAI_CLIENT_ID:
        raise RuntimeError("bad client ID")
    if request["client_secret"] != OPENAI_CLIENT_SECRET:
        raise RuntimeError("bad client secret")
    if request["code"] != OPENAI_CODE:
        raise RuntimeError("bad code")

    return {
        "access_token": OPENAI_TOKEN,
        "token_type": "bearer"
    }

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

# This is a version of the main.py file found in ../../../server/main.py for testing the plugin locally.
# Use the command `poetry run dev` to run this.
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Response

from starlette.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware
from splitgraph_chatgpt_plugin.config import DOCUMENT_COLLECTION_NAME, get_openai_api_key, get_db_connection_string
from splitgraph_chatgpt_plugin.ddn import run_sql
from splitgraph_chatgpt_plugin.models import FindRelevantTablesResponse, RunSQLResponse

from splitgraph_chatgpt_plugin.persistence import get_embedding_store
from splitgraph_chatgpt_plugin.query import generate_full_response
import pprint

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


@app.route("/.well-known/ai-plugin.json")
async def get_manifest(request):
    file_path = "./local_server/ai-plugin.json"
    simple_headers = {}
    simple_headers["Access-Control-Allow-Private-Network"] = "true"
    return FileResponse(file_path, media_type="text/json", headers=simple_headers)


@app.route("/.well-known/logo.png")
async def get_logo(request):
    file_path = "./local_server/logo.png"
    return FileResponse(file_path, media_type="text/json")


@app.route("/.well-known/openapi.json")
async def get_openapi(request):
    file_path = "./local_server/openapi.json"
    return FileResponse(file_path, media_type="text/json")


@app.get("/find_relevant_tables", response_model=FindRelevantTablesResponse)
async def query_main(prompt: str|None=None):
    global vstore
    try:
        response = generate_full_response(prompt, vstore)
        return response
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.get("/run_sql", response_model=RunSQLResponse)
async def query_main(query: str|None=None):
    global vstore
    try:
        response = run_sql(query)
        return response
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Service Error")

@app.on_event("startup")
async def startup():
    global openai_api_key
    global vstore
    openai_api_key = get_openai_api_key()
    vstore = get_embedding_store(DOCUMENT_COLLECTION_NAME, get_db_connection_string(), openai_api_key)


def start():
    uvicorn.run("local_server.main:app", host="localhost", port=PORT, reload=True)

if __name__ == '__main__':
    start()

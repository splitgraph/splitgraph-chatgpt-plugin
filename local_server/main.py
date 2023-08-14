# This is a version of the main.py file found in ../../../server/main.py for testing the plugin locally.
# Use the command `poetry run dev` to run this.
from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException

from starlette.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware
from splitgraph_chatgpt_plugin.config import (
    DOCUMENT_COLLECTION_NAME,
    get_openai_api_key,
    get_db_connection_string,
)
from splitgraph_chatgpt_plugin.ddn import get_table_infos, run_sql as _run_sql
from splitgraph_chatgpt_plugin.models import FindRelevantTablesResponse, RunSQLResponse

from splitgraph_chatgpt_plugin.persistence import connect, find_repos, get_embedding_store_pgvector
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
    file_path = "./local_server/ai-plugin.json"
    simple_headers = {}
    simple_headers["Access-Control-Allow-Private-Network"] = "true"
    return FileResponse(file_path, media_type="text/json", headers=simple_headers)


@app.route("/.well-known/logo.png")
async def get_logo(request):
    file_path = "./local_server/logo.png"
    return FileResponse(file_path, media_type="image/png")


@app.route("/.well-known/openapi.json")
async def get_openapi(request):
    file_path = "./local_server/openapi.json"
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
                tables=get_table_infos(repositories, use_fully_qualified_table_names=True)
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


@app.on_event("startup")
async def startup():
    global openai_api_key
    global vstore
    openai_api_key = get_openai_api_key()
    vstore = get_embedding_store_pgvector(
        connect(get_db_connection_string()), DOCUMENT_COLLECTION_NAME, openai_api_key
    )


def start():
    uvicorn.run("local_server.main:app", host="localhost", port=PORT, reload=True)


if __name__ == "__main__":
    start()

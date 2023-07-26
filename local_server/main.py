# This is a version of the main.py file found in ../../../server/main.py for testing the plugin locally.
# Use the command `poetry run dev` to run this.
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Response

from starlette.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware

from splitgraph_chatgpt_plugin.persistence import get_db_connection_string, get_embedding_store
from splitgraph_chatgpt_plugin.query import generate_full_response


app = FastAPI()
collection = "repository_embeddings"
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


@app.get("/query")
async def query_main(question: str|None=None):
    global openai_api_key
    global vstore
    try:
        return Response(content=generate_full_response(question, openai_api_key, vstore), media_type="text/plain")
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global openai_api_key
    global vstore
    openai_api_key = os.getenv("OPENAI_API_KEY")
    vstore = get_embedding_store(collection, get_db_connection_string())


def start():
    uvicorn.run("local_server.main:app", host="localhost", port=PORT, reload=True)

if __name__ == '__main__':
    start()

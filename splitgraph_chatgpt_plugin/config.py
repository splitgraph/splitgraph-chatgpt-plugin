import os


def get_db_connection_string():
    return os.environ["PG_CONN_STR"]


def get_openai_api_key():
    return os.getenv("OPENAI_API_KEY")


DOCUMENT_COLLECTION_NAME = "repository_embeddings"
SPLITGRAPH_WWW_URL_PREFIX = "https://www.splitgraph.com/"

import os


def get_db_connection_string():
    return os.getenv("PG_CONN_STR")

def get_openai_api_key():
    return os.getenv("OPENAI_API_KEY")

def get_oauth_client_id_openai():
    return os.getenv("OAUTH_OPENAI_CLIENT_ID")

def get_oauth_client_id_google():
    return os.getenv("OAUTH_GOOGLE_CLIENT_ID")

def get_oauth_client_secret_openai():
    return os.getenv("OAUTH_OPENAI_SECRET")

def get_oauth_client_secret_google():
    return os.getenv("OAUTH_GOOGLE_SECRET")

def get_plugin_jwt_secret():
    return os.getenv("OAUTH_PLUGIN_JWT_SECRET")



DOCUMENT_COLLECTION_NAME = "repository_embeddings"
SPLITGRAPH_WWW_URL_PREFIX = "https://www.splitgraph.com/"
PLUGIN_DOMAIN = "chatgpt.splitgraph.io"
GOOGLE_AUTH_FLOW_COMPLETE_PATH = "/auth/oauth/complete/google"
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = 60 * 5 # 5 minutes
JWT_REFRESH_TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 365 # 1 year

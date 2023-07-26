from typing import List, Tuple
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import VectorStore
import sqlalchemy
import os


def get_embedding_store_pgvector(
    collection: str, connection_string: str
) -> VectorStore:
    # description: https://supabase.com/blog/openai-embeddings-postgres-vector
    from langchain.vectorstores import PGVector
    from langchain.vectorstores.pgvector import DistanceStrategy

    return PGVector(
        embedding=OpenAIEmbeddings(),
        collection_name=collection,
        connection_string=connection_string,
        distance_strategy=DistanceStrategy.COSINE,
    )


def get_embedding_store_pgembedding(
    collection: str, connection_string: str
) -> VectorStore:
    # description: https://neon.tech/blog/pg-embedding-extension-for-vector-search
    from langchain.vectorstores import PGEmbedding

    db = PGEmbedding(
        embedding_function=OpenAIEmbeddings(),
        collection_name=collection,
        connection_string=connection_string,
    )
    # attempt to create index if it does not yet exist
    db.create_hnsw_index(
        max_elements=10000, dims=1536, m=8, ef_construction=16, ef_search=16
    )
    return db


def get_embedding_store(
    collection: str, connection_string: str, use_pgembedding=True
) -> VectorStore:
    if use_pgembedding:
        return get_embedding_store_pgembedding(collection, connection_string)
    return get_embedding_store_pgvector(collection, connection_string)


def find_repos(vstore: VectorStore, query: str, limit=4) -> List[Tuple[str, str]]:
    results = vstore.similarity_search_with_score(query, limit)
    # sort by relevance, returning most relevant repository first
    results.sort(key=lambda a: a[1], reverse=True)
    # deduplicate results
    return list(
        set(
            [(r[0].metadata["namespace"], r[0].metadata["repository"]) for r in results]
        )
    )


def connect(connection_string: str) -> sqlalchemy.engine.Connection:
    engine = sqlalchemy.create_engine(connection_string)
    return engine.connect()


def get_db_connection_string():
    return os.environ["PG_CONN_STR"]

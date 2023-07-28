from math import ceil, sqrt
from typing import List, Tuple
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import VectorStore
from langchain.vectorstores import PGVector
from langchain.vectorstores.pgvector import DistanceStrategy
import sqlalchemy
import os
from sqlalchemy.orm import Session


def create_pgvector_index(db: PGVector, max_elements: int):
    create_index_query = sqlalchemy.text(
        "CREATE INDEX IF NOT EXISTS langchain_pg_embedding_idx "
        "ON langchain_pg_embedding "
        "USING ivfflat (embedding vector_cosine_ops) "
        # from: https://supabase.com/blog/openai-embeddings-postgres-vector#indexing
        # "A good starting number of lists is 4 * sqrt(table_rows)"
        "WITH (lists = {});".format(ceil(4 * sqrt(max_elements)))
    )
    # Execute the queries
    try:
        with Session(db._conn) as session:
            # Create the HNSW index
            session.execute(create_index_query)
            session.commit()
        print("PGVector extension and index created successfully.")
    except Exception as e:
        print(f"Failed to create PGVector extension or index: {e}")


def get_embedding_store_pgvector(
    collection: str, connection_string: str, openai_api_key: str, max_elements: int
) -> VectorStore:
    # description: https://supabase.com/blog/openai-embeddings-postgres-vector

    db = PGVector(
        # MyPy chokes on this, see: https://github.com/langchain-ai/langchain/issues/2925
        embedding_function=OpenAIEmbeddings(openai_api_key=openai_api_key),  # type: ignore
        collection_name=collection,
        connection_string=connection_string,
        distance_strategy=DistanceStrategy.COSINE,
    )
    # create index
    create_pgvector_index(db, max_elements)
    return db


def get_embedding_store_pgembedding(
    collection: str, connection_string: str, openai_api_key: str, max_elements: int
) -> VectorStore:
    # description: https://neon.tech/blog/pg-embedding-extension-for-vector-search
    from langchain.vectorstores import PGEmbedding

    db = PGEmbedding(
        embedding_function=OpenAIEmbeddings(openai_api_key=openai_api_key),  # type: ignore
        collection_name=collection,
        connection_string=connection_string,
    )
    # attempt to create index if it does not yet exist
    db.create_hnsw_index(
        max_elements=max_elements, dims=1536, m=8, ef_construction=16, ef_search=16
    )
    return db


def get_embedding_store(
    collection: str,
    connection_string: str,
    openai_api_key: str,
    max_elements=10000,
    use_pgembedding=False,
) -> VectorStore:
    if use_pgembedding:
        return get_embedding_store_pgembedding(
            collection, connection_string, openai_api_key, max_elements
        )
    return get_embedding_store_pgvector(
        collection, connection_string, openai_api_key, max_elements
    )


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

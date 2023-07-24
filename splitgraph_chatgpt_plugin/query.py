# from: https://python.langchain.com/en/latest/modules/chains/examples/sqlite.html
import os
from typing import List, Tuple

from .markdown import (
    ddn_response_to_markdown,
    get_repository_urls_as_markdown,
    get_query_editor_url,
)

from .gpt import generate_gpt_prompt, get_generated_sql_with_explanation

from .persistence import find_repos, get_db_connection_string, get_embedding_store

from .ddn import DDNResponse, ddn_query

RESPONSE_TEMPLATE = """
Query:
"{question}"

Generated SQL:
{sql}

Explanation of SQL:
{explanation}

Query results:
{query_response}

Polish and rerun this query on Splitgraph at:
{query_editor_url}

Browse related repositories:
{repository_page_urls}

""".strip()


def generate_response_text(
    question: str,
    sql: str,
    explanation: str,
    query_response: DDNResponse,
    repositories: List[Tuple[str, str]],
) -> str:
    return RESPONSE_TEMPLATE.format(
        question=question,
        sql=sql,
        explanation=explanation,
        query_response=ddn_response_to_markdown(query_response),
        repository_page_urls="\n".join(get_repository_urls_as_markdown(repositories)),
        query_editor_url=get_query_editor_url(sql),
    )


# # Step 1: Select potentially useful repositories based on query
# Start by searching for available repos based on the query.
# This search uses pg_vector to compare the query expression's OpenAI
# embedding to the pre-calculated embeddings stored in PostgreSQL.
# Example query: 'How many hospitals are there in Chicago?'
# RepoSearcher expects a collection name, specified when indexing repos,
# which doesn't have to be a Splitgraph namespace. In this case,
# it's 'cityofchicago' because all of the indexed repositories are contained
# within that namespace.
collection = "repository_embeddings"
question = "What is the most expensive residential neighborhood in Chicago?"
openai_api_key = os.getenv("OPENAI_API_KEY")
connection_string = get_db_connection_string()
vstore = get_embedding_store(collection, connection_string)
repositories = find_repos(vstore, question)
prompt = generate_gpt_prompt(repositories, question)
sql, explanation = get_generated_sql_with_explanation(openai_api_key, prompt)
ddn_response = ddn_query(sql)
print(generate_response_text(question, sql, explanation, ddn_response, repositories))
# plugin_response = generate_response(query, explanation, ddn_results['rows'])

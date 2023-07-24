# from: https://python.langchain.com/en/latest/modules/chains/examples/sqlite.html
import os
from typing import List, Tuple

from .gpt_completion import GPT_FUNCTION_NAME, get_generated_sql_with_explanation

from .repo_to_md import table_info_to_markdown

from .persistence import find_repos, get_db_connection_string, get_embedding_store

from .ddn import get_repo_tables

GENERATE_SQL_PROMPT = """
You are a PostgreSQL expert. Create a syntactically correct PostgreSQL SQL query which answers the question,
"{question}"
Query for at most 5 results using the LIMIT clause as per PostgreSQL.
Never query for all columns from a table. You must query only the columns that are needed to answer the question.
Wrap each column name in double quotes (") to denote them as delimited identifiers.
Pay attention to use only the column names you can see in the tables below.
Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
Pay attention to use CURRENT_DATE function to get the current date, if the question involves "today".
Always use the fully qualified table name.
You may use only the following tables in your query:

{tables}

Call the {function_name} function with the generated SQL query, and an explanation of why this table was chosen for the query.
"""


def generate_gpt_prompt(repositories: List[Tuple[str, str]]) -> str:
    table_infos_markdown: List[str] = []
    for namespace, repository in repositories:
        for table_info in get_repo_tables(namespace, repository):
            table_infos_markdown.append(
                table_info_to_markdown(
                    namespace, repository, table_info, emit_header=False
                )
            )

    return GENERATE_SQL_PROMPT.format(
        question=question,
        tables="\n".join(table_infos_markdown),
        function_name=GPT_FUNCTION_NAME,
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
connection_string = get_db_connection_string()
vstore = get_embedding_store(collection, connection_string)
repositories = find_repos(vstore, question)
prompt = generate_gpt_prompt(repositories)
api_key = os.getenv("OPENAI_API_KEY")
query, explanation = get_generated_sql_with_explanation(api_key, prompt)
print(query)
print(explanation)

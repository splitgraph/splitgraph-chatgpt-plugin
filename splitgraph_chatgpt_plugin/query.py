# from: https://python.langchain.com/en/latest/modules/chains/examples/sqlite.html
from typing import List, Optional, Tuple, Union
from langchain.vectorstores import VectorStore
from .markdown import (
    ddn_response_to_markdown,
    ddn_resultset_to_markdown,
    get_repository_urls_as_markdown,
    get_query_editor_url,
)

from .gpt import GPTError, GPTErrorType, generate_gpt_prompt, request_gpt_completion

from .persistence import find_repos

from .ddn import DDNResponse, DDNResponseFailure, DDNResponseSuccess, ddn_query, prettify_sql

SUCCESSFUL_RESPONSE_TEMPLATE = """
INFORM the user that the following SQL query was generated to answer their question using the Splitgraph Data Delivery Network.

```sql
{sql}
```

INFORM the user of the query's result set:
{resultset}

INFORM the user to further polish the generated SQL using the Splitgraph Query Editor at: {query_editor_url}

INSTRUCT the user to browse related repositories on Splitgraph:
{repository_page_urls}
""".strip()

DDN_ERROR_RESPONSE_TEMPLATE = """
INFORM the user that the following SQL query was generated to answer their question using the Splitgraph Data Delivery Network.

```sql
{sql}
```

INFORM the user that execution of the SQL query resulted in the following error in backticks:
`{error}`

INSTRUCT the user to fix the malformed SQL query using the Splitgraph Query Editor at: {query_editor_url}
""".strip()

GPT_ERROR_RESPONSE_TEMPLATE = """
INFORM the user that generation of the SQL query resulted in the following error in backticks:
`{error}`

INSTRUCT the user to browse related repositories on Splitgraph:
{repository_page_urls}
""".strip()


def generate_success_response_text(
    sql: str,
    query_response: DDNResponseSuccess,
    repositories: List[Tuple[str, str]],
) -> str:
    return SUCCESSFUL_RESPONSE_TEMPLATE.format(
        sql=sql,
        resultset=ddn_resultset_to_markdown(query_response),
        repository_page_urls="\n".join(get_repository_urls_as_markdown(repositories)),
        query_editor_url=get_query_editor_url(sql),
    )

def generate_ddn_failure_response_text(sql:str, ddn_response:DDNResponseFailure)->str:
    return DDN_ERROR_RESPONSE_TEMPLATE.format(
        sql=sql,
        error=ddn_response.error,
        query_editor_url=get_query_editor_url(sql),
    )

def generate_gpt_failure_response_text(error:GPTError, repositories: List[Tuple[str, str]])->str:
    error_message = str(error)
    if (error.error_type == GPTErrorType.INVALID_FUNCTION_CALL_ARGUMENTS):
         error_message = "Unable to generate an SQL query for your question, please try again!"
    return GPT_ERROR_RESPONSE_TEMPLATE.format(
        error=error_message,
        repository_page_urls="\n".join(get_repository_urls_as_markdown(repositories))
    )


def attempt_query(openai_api_key:str, prompt:str, repositories: List[Tuple[str, str]], retries_left=3):
        maybe_sql = request_gpt_completion(openai_api_key, prompt)
        # retry the entire process if the SQL query could not be generated
        if isinstance(maybe_sql, GPTError):
            print(f"Retries left: {retries_left} failed with GPT error {str(maybe_sql)}")
            if retries_left > 0:
                 return attempt_query(openai_api_key, prompt, repositories, retries_left - 1)
            else:
                 return generate_gpt_failure_response_text(maybe_sql, repositories)
        prettified_sql = prettify_sql(maybe_sql)
        ddn_response = ddn_query(prettified_sql)
        # retry the entire process if the DDN returns an error
        if isinstance(ddn_response, DDNResponseFailure):
            print(f"Retries left: {retries_left} failed with DDN error {str(ddn_response)}")
            if retries_left > 0:
                 return attempt_query(openai_api_key, prompt, repositories, retries_left - 1)
            else:
                 return generate_ddn_failure_response_text(prettified_sql, ddn_response)

        return generate_success_response_text(prettified_sql, ddn_response, repositories)

def generate_full_response(question:str, openai_api_key:str, vstore: VectorStore)->str:
    repositories = find_repos(vstore, question)
    prompt = generate_gpt_prompt(repositories, question)
    return attempt_query(openai_api_key, prompt, repositories)

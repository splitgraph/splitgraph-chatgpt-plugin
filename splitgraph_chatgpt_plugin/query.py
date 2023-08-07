# from: https://python.langchain.com/en/latest/modules/chains/examples/sqlite.html
import json
import pprint
from typing import List, Optional, Tuple
from langchain.vectorstores import VectorStore

from .models import FindRelevantTablesResponse
from .markdown import (
    ddn_resultset_to_markdown,
    get_repository_urls_as_markdown,
)

from .gpt import (
    GPT_FUNCTION_NAME,
    FunctionCall,
    GPTError,
    GPTErrorType,
    GPTMessage,
    GPTMessageAssistant,
    GPTMessageFunction,
    GPTMessageUser,
    continue_gpt_session,
    generate_gpt_prompt,
)

from .persistence import find_repos

from .models import (
    DDNResponse,
    DDNResponseFailure,
    DDNResponseSuccess,
)

from .ddn import ddn_query, prettify_sql, get_table_infos, get_query_editor_url

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

GPT_GENERAL_ERROR_RESPONSE_TEMPLATE = """
INFORM the user that generation of the SQL query resulted in the following error in backticks:
`{error}`

INSTRUCT the user to browse related repositories on Splitgraph:
{repository_page_urls}
""".strip()

GPT_SQL_GENERATION_ERROR_RESPONSE_TEMPLATE = """
INFORM the user that generation of the SQL query was not possible due to the following:
{error}

INSTRUCT the user to try a different question.
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


def generate_ddn_failure_response_text(
    sql: str, ddn_response: DDNResponseFailure
) -> str:
    return DDN_ERROR_RESPONSE_TEMPLATE.format(
        sql=sql,
        error=ddn_response.error,
        query_editor_url=get_query_editor_url(sql),
    )


def generate_gpt_general_failure_response_text(
    error: GPTError, repositories: List[Tuple[str, str]]
) -> str:
    error_message = str(error)
    if error.error_type == GPTErrorType.INVALID_FUNCTION_CALL_ARGUMENTS:
        error_message = error.message
    return GPT_GENERAL_ERROR_RESPONSE_TEMPLATE.format(
        error=error_message,
        repository_page_urls="\n".join(get_repository_urls_as_markdown(repositories)),
    )


def generate_gpt_sql_generation_failure_response_text(error: GPTError) -> str:
    error_message = str(error)
    return GPT_SQL_GENERATION_ERROR_RESPONSE_TEMPLATE.format(
        error=error_message,
    )


DEFAULT_RETRY_ATTEMPTS = 3


def attempt_query(
    openai_api_key: str,
    prompt: str,
    repositories: List[Tuple[str, str]],
    messages: Optional[List[GPTMessage]] = None,
    retries_left=DEFAULT_RETRY_ATTEMPTS,
):
    pprint.pprint(messages)
    # If no messages were passed in, consider this attempt as starting a brand new GPT session
    if messages is None:
        messages = [GPTMessageUser(role="user", content=prompt)]
    maybe_sql = continue_gpt_session(openai_api_key, messages)
    if isinstance(maybe_sql, GPTError):
        print(f"Retries left: {retries_left} failed with GPT error {str(maybe_sql)}")
        # If we have run out of retry attempts, fail
        if retries_left < 1:
            return generate_gpt_general_failure_response_text(maybe_sql, repositories)
        # If GPT returned with a failure to generate a query (because eg. the query cannot be
        # fixed), then give up.
        if maybe_sql.error_type == GPTErrorType.SQL_GENERATION_FAILURE:
            return generate_gpt_sql_generation_failure_response_text(maybe_sql)
        # If this is a later iteration on a query and the context length has been exhausted
        # then later attempts will probably also overshoot
        if (
            len(messages) > 1
            and maybe_sql.error_type == GPTErrorType.CONTEXT_TOKENS_EXHAUSTED
        ):
            return generate_gpt_general_failure_response_text(maybe_sql, repositories)
        # Otherwise retry with a newly generated SQL query
        return attempt_query(
            openai_api_key, prompt, repositories, None, retries_left - 1
        )
    # DON'T attempt to pretty-print the SQL query using pglast
    prettified_sql = maybe_sql  # prettify_sql(maybe_sql)
    # Attempt to run the execute the generated sql query on the DDN
    ddn_response = ddn_query(prettified_sql)
    if isinstance(ddn_response, DDNResponseFailure):
        print(f"Retries left: {retries_left} failed with DDN error {str(ddn_response)}")
        if retries_left > 0:
            # If the DDN responds with an error message then add this error
            # to the GPT context so GPT will generate a new query and try again
            messages.extend(
                [
                    GPTMessageAssistant(
                        role="assistant",
                        content=None,
                        function_call=FunctionCall(
                            name="sql",
                            arguments=json.dumps({"query": maybe_sql}),
                        ),
                    ),
                    GPTMessageFunction(
                        role="function",
                        name=GPT_FUNCTION_NAME,
                        content=json.dumps({"error": ddn_response.error}),
                    ),
                    GPTMessageUser(
                        role="user",
                        content="Regenerate the SQL query fixing this error.",
                    ),
                ]
            )
            return attempt_query(
                openai_api_key, prompt, repositories, messages, retries_left - 1
            )
        else:
            return generate_ddn_failure_response_text(prettified_sql, ddn_response)
    return generate_success_response_text(prettified_sql, ddn_response, repositories)


def generate_full_response(
    prompt: str, vstore: VectorStore
) -> FindRelevantTablesResponse:
    repositories = find_repos(vstore, prompt)
    return FindRelevantTablesResponse(
        tables=get_table_infos(repositories, use_fully_qualified_table_names=True)
    )

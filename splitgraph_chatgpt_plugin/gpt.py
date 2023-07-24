import os
from typing import Any, List, Literal, Tuple

import openai
from pydantic import BaseModel, Json
from .markdown import table_info_to_markdown
from .ddn import get_repo_tables


class FunctionArguments(BaseModel):
    query: str
    explanation: str


class CompletionMessageFunctionCall(BaseModel):
    name: Literal["return_sql_query_with_explanation"]
    arguments: Json[FunctionArguments]


class CompletionMessage(BaseModel):
    function_call: CompletionMessageFunctionCall


class CompletionChoice(BaseModel):
    finish_reason: Literal["function_call"]
    message: CompletionMessage


class GPTCompletionResponse(BaseModel):
    choices: List[CompletionChoice]


GPT_FUNCTION_NAME = "return_sql_query_with_explanation"

FUNCTION_DESCRIPTION = {
    "name": GPT_FUNCTION_NAME,
    "description": "Accepts a PostgreSQL dialect SQL query and an explanation of how the query works",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A PostgreSQL dialect SQL query which provides the answer to the question",
            },
            "explanation": {
                "type": "string",
                "description": "Explanation of how the SQL query works",
            },
        },
        "required": ["query", "explanation"],
    },
}


def parse_completion_response(response: Any) -> Tuple[str, str]:
    parsed_response = GPTCompletionResponse.parse_obj(response)
    assert len(parsed_response.choices) == 1
    return (
        parsed_response.choices[0].message.function_call.arguments.query,
        parsed_response.choices[0].message.function_call.arguments.explanation,
    )


def get_generated_sql_with_explanation(api_key: str, prompt: str) -> Tuple[str, str]:
    return parse_completion_response(
        openai.ChatCompletion.create(
            api_key=api_key,
            model="gpt-3.5-turbo-0613",
            messages=[{"role": "user", "content": prompt}],
            functions=[FUNCTION_DESCRIPTION],
        )
    )


GENERATE_SQL_PROMPT = """
You are a PostgreSQL expert. Create a syntactically correct PostgreSQL SQL query which answers the question,
"{question}"
Query for at most 5 results using the LIMIT clause as per PostgreSQL.
Never query for all columns from a table. You must query only the columns that are needed to answer the question.
Wrap each column name in double quotes (") to denote them as delimited identifiers.
Pay attention to use only the column names you can see in the tables below.
Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
Pay attention to use CURRENT_DATE function to get the current date, if the question involves "today".
Always use the ENTIRE fully qualified table name, including the portion after the period, ("." character).
You may use only the following tables in your query:

{tables}

Call the {function_name} function with the generated SQL query, and an explanation of why this table was chosen for the query.
"""


def generate_gpt_prompt(repositories: List[Tuple[str, str]], question: str) -> str:
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

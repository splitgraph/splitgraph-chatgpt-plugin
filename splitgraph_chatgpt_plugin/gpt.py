from enum import Enum
import json
import os
from typing import Annotated, Any, List, Literal, Optional, Tuple, Union

import openai
from pydantic import BaseModel, Json, Field
from pydantic.error_wrappers import ValidationError
from .markdown import table_info_to_markdown
from .ddn import get_repo_tables
import pprint

GPT_MODEL = "gpt-4-0613"  # "gpt-3.5-turbo-0613"


class FunctionArguments(BaseModel):
    query: str


class FunctionCall(BaseModel):
    name: Literal["sql"]
    arguments: str


class GPTMessageUser(BaseModel):
    role: Literal["user"]
    content: str


class GPTMessageAssistant(BaseModel):
    role: Literal["assistant"]
    function_call: Optional[FunctionCall]
    content: Optional[str]


class GPTMessageFunction(BaseModel):
    role: Literal["function"]
    name: str
    content: str


GPTMessage = Annotated[
    Union[GPTMessageUser, GPTMessageAssistant, GPTMessageFunction],
    Field(discriminator="role"),
]


class CompletionChoice(BaseModel):
    finish_reason: str
    message: GPTMessage


class GPTCompletionResponse(BaseModel):
    choices: List[CompletionChoice]


GPT_FUNCTION_NAME = "sql"

FUNCTION_DESCRIPTION = {
    "name": GPT_FUNCTION_NAME,
    "description": "Accepts a PostgreSQL dialect SQL query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A PostgreSQL dialect SQL query.",
            }
        },
        "required": ["query"],
    },
}

GPTErrorType = Enum(
    "GPTErrorType",
    [
        "INVALID_FUNCTION_CALL_ARGUMENTS",
        "SQL_GENERATION_FAILURE",
        "CONTEXT_TOKENS_EXHAUSTED",
        "GPT_UNAVAILABLE",
        "RATE_LIMIT",
        "UNKNOWN",
    ],
)


class GPTError(Exception):
    message: str
    error_type: GPTErrorType

    def __init__(self, message: str, error_type: GPTErrorType):
        super().__init__(message)
        self.message = message
        self.error_type = error_type


def parse_completion_response(response: Any) -> Union[str, GPTError]:
    try:
        # it's useful during development to see the raw response from OpenAI
        pprint.pprint(response)
        parsed_response = GPTCompletionResponse.parse_obj(response)
        assert len(parsed_response.choices) == 1
        assert isinstance(parsed_response.choices[0].message, GPTMessageAssistant)
        # an sql query was generated, return it
        if (
            parsed_response.choices[0].finish_reason == "function_call"
            and parsed_response.choices[0].message.function_call is not None
        ):
            # attempt to parse function arguments as JSON
            try:
                # replace newlines with spaces since that's the #1 reason GPT returns invalid JSON after
                # context exhaustion
                arguments = json.loads(
                    parsed_response.choices[0].message.function_call.arguments.replace(
                        "\n", " "
                    )
                )
                return FunctionArguments.parse_obj(arguments).query
            except json.decoder.JSONDecodeError as json_error:
                return GPTError(
                    "Function arguments are not valid JSON",
                    GPTErrorType.INVALID_FUNCTION_CALL_ARGUMENTS,
                )
        if parsed_response.choices[0].finish_reason == "length":
            return GPTError(
                parsed_response.choices[0].message.content
                or "Maximum LLM context length exceeded",
                GPTErrorType.CONTEXT_TOKENS_EXHAUSTED,
            )
        if parsed_response.choices[0].finish_reason == "stop":
            return GPTError(
                parsed_response.choices[0].message.content
                or "Unable to generate SQL query",
                GPTErrorType.SQL_GENERATION_FAILURE,
            )
        # GPT failed to generate a query
        return GPTError(
            parsed_response.choices[0].message.content or "Unknown error occurred",
            GPTErrorType.UNKNOWN,
        )
    # pydantic validation error
    except ValidationError as validation_error:
        errors = validation_error.errors()
        return GPTError(", ".join([e["msg"] for e in errors]), GPTErrorType.UNKNOWN)
    # every other type of exception
    except Exception as other_error:
        pprint.pprint(other_error)
        return GPTError(str(other_error), GPTErrorType.UNKNOWN)


def gpt_completion(api_key: str, messages: List[GPTMessage]) -> Any:
    try:
        return openai.ChatCompletion.create(
            api_key=api_key,
            model=GPT_MODEL,
            # The OpenAI SDK expects to receive an array of dicts.
            messages=[json.loads(message.json()) for message in messages],
            functions=[FUNCTION_DESCRIPTION],
        )
    except openai.error.ServiceUnavailableError as e:
        return GPTError(str(e), GPTErrorType.GPT_UNAVAILABLE)
    except openai.error.InvalidRequestError as e:
        # TODO: this is typically CONTEXT_TOKENS_EXHAUSTED, but can be other
        # errors as well.
        return GPTError(str(e), GPTErrorType.CONTEXT_TOKENS_EXHAUSTED)
    except openai.error.RateLimitError as e:
        return GPTError(str(e), GPTErrorType.RATE_LIMIT)


def continue_gpt_session(
    api_key: str, messages: List[GPTMessage]
) -> Union[str, GPTError]:
    # The conversation begins with the "user" (which in this case is the plugin) announcing the prompt
    completion = gpt_completion(api_key, messages)
    if isinstance(completion, GPTError):
        return completion
    return parse_completion_response(completion)


RETRY_COUNT = 3

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

Call the {function_name} function with the generated SQL query.
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

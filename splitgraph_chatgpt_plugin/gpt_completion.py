import os
from typing import Any, Generator, List, Literal, Tuple

import openai
from pydantic import BaseModel, Json


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

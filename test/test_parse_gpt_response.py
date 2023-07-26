import unittest
from splitgraph_chatgpt_plugin.gpt import (
    parse_completion_response,
    GPTError,
    GPTErrorType,
)


class Testing(unittest.TestCase):
    def test_invalid_gpt_function_arguments(self):
        INTERRUPTED_FUNCTION_CALL_GPT_RESPONSE = {
            "id": "chatcmpl-7gVm4oh0R1XmDf5cLCKRlzBDShqIu",
            "object": "chat.completion",
            "created": 1690366272,
            "model": "gpt-3.5-turbo-0613",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "function_call": {
                            "name": "sql",
                            "arguments": '{\n  "query": "SELECT AVG(property_tax) AS average_property_tax FROM \\"cityofchicago/census-data-selected-socioeconomic-indicators-in-kn9c-c2s2\\".\\"census_data_selected_socioeconomic_indicators_in\\" WHERE community_area_name = \'CHICAGO\' AND per_capita_income_ IS NOT NULL AND per_capita_income_ > 0 AND percent_households_below_poverty IS NOT NULL AND percent_households_below_poverty > 0 AND percent_of_housing_crowded IS NOT NULL AND percent_of_housing_crowded > 0 AND percent_aged_under_18_or_over_64 IS NOT NULL AND percent',
                        },
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 3954,
                "completion_tokens": 143,
                "total_tokens": 4097,
            },
        }
        parsed_response = parse_completion_response(
            INTERRUPTED_FUNCTION_CALL_GPT_RESPONSE
        )
        assert isinstance(parsed_response, GPTError)
        assert parsed_response.error_type == GPTErrorType.CONTEXT_TOKENS_EXHAUSTED

    def test_sql_query_generation_failure(self):
        SQL_QUERY_GENERATION_FAILURE_GPT_RESPONSE = {
            "id": "chatcmpl-7gZeABc721vPKoVVB8EwLbxmme8jU",
            "object": "chat.completion",
            "created": 1690381158,
            "model": "gpt-3.5-turbo-0613",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": 'I apologize for the confusion, but I cannot generate the SQL query to compute the average property tax per homeowning family in Chicago in 2020 with the given tables. None of the provided tables have a column specifically named "property_tax".\n\nTo accurately calculate the average property tax per homeowning family, we would need the actual table that contains the property tax information. Please provide the correct table name and',
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 4014,
                "completion_tokens": 83,
                "total_tokens": 4097,
            },
        }
        parsed_response = parse_completion_response(
            SQL_QUERY_GENERATION_FAILURE_GPT_RESPONSE
        )
        assert isinstance(parsed_response, GPTError)
        assert parsed_response.error_type == GPTErrorType.CONTEXT_TOKENS_EXHAUSTED
        assert (
            parsed_response.message
            == SQL_QUERY_GENERATION_FAILURE_GPT_RESPONSE["choices"][0]["message"][
                "content"
            ]
        )

    def test_invalid_json_args(self):
        INVALID_JSON_ARGS = {
            "id": "chatcmpl-7gcyeLP58mtb8CHmY9G97Grqfl6QT",
            "object": "chat.completion",
            "created": 1690393960,
            "model": "gpt-3.5-turbo-0613",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "function_call": {
                            "name": "sql",
                            "arguments": '{\n  "query": "\n    SELECT \n      AVG(census_data_selected_socioeconomic_indicators_in.per_capita_income_) AS average_property_tax\n    FROM \n      \\"cityofchicago/census-data-selected-socioeconomic-indicators-in-kn9c-c2s2\\".\\"census_data_selected_socioeconomic_indicators_in\\"\n    WHERE \n      census_data_selected_socioeconomic_indicators_in.community_area_name = \'Chicago\'\n      AND census_data_selected_socioeconomic_indicators_in.ca = 2020\n    LIMIT 5;"\n}',
                        },
                    },
                    "finish_reason": "function_call",
                }
            ],
            "usage": {
                "prompt_tokens": 3954,
                "completion_tokens": 120,
                "total_tokens": 4074,
            },
        }
        parsed_response = parse_completion_response(INVALID_JSON_ARGS)
        assert isinstance(parsed_response, GPTError)
        assert (
            parsed_response.error_type == GPTErrorType.INVALID_FUNCTION_CALL_ARGUMENTS
        )

import unittest
from splitgraph_chatgpt_plugin.gpt import parse_completion_response, GPTError, GPTErrorType

INTERRUPTED_SQL_QUERY_GPT_RESPONSE = {
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
          "arguments": "{\n  \"query\": \"SELECT AVG(property_tax) AS average_property_tax FROM \\\"cityofchicago/census-data-selected-socioeconomic-indicators-in-kn9c-c2s2\\\".\\\"census_data_selected_socioeconomic_indicators_in\\\" WHERE community_area_name = 'CHICAGO' AND per_capita_income_ IS NOT NULL AND per_capita_income_ > 0 AND percent_households_below_poverty IS NOT NULL AND percent_households_below_poverty > 0 AND percent_of_housing_crowded IS NOT NULL AND percent_of_housing_crowded > 0 AND percent_aged_under_18_or_over_64 IS NOT NULL AND percent"
        }
      },
      "finish_reason": "length"
    }
  ],
  "usage": {
    "prompt_tokens": 3954,
    "completion_tokens": 143,
    "total_tokens": 4097
  }
}
class Testing(unittest.TestCase):
    def test_finish_reason_length(self):
        parsed_response = parse_completion_response(INTERRUPTED_SQL_QUERY_GPT_RESPONSE);
        assert isinstance(parsed_response, GPTError)
        assert parsed_response.error_type == GPTErrorType.INVALID_FUNCTION_CALL_ARGUMENTS

# based on: https://python.langchain.com/en/latest/modules/chains/examples/sqlite.html
import json
from typing import Any, Dict, List, Tuple
import requests
from pydantic import parse_obj_as

from .config import SPLITGRAPH_WWW_URL_PREFIX

from .models import (
    DDNResponse,
    DDNResponseFailure,
    RepositoryInfo,
    RunSQLResponse,
    TableColumn,
    TableInfo,
)
import itertools
import urllib.parse


# The constructor of the SQLDatabase base class calls SQLAlchemy's inspect()
# which fails on the DDN since some of the required introspection tables are
# not available.
# Creating a child class doesn't solve the issue, since the base constructor
# is still called, and for typing, we need an instance of SQLDatabase.
#
# The currents solution is to mock out the inspect() function to return a
# SplitgraphInspector instance

GRAPHQL_API_URL = "https://api.splitgraph.com/gql/cloud/unified/graphql"
SPLITGRAPH_DDN_URL = "https://data.splitgraph.com/sql/query/ddn"

GRAPHQL_QUERIES = {
    "GetNamespaceRepos": """
query GetNamespaceRepos($namespace: String!) {
  namespace(namespace: $namespace) {
    namespace
    repositoriesByNamespace {
      nodes {
        repository
        namespace
        externalMetadata
        repoProfileByNamespaceAndRepository {
          readme
          metadata
        }
        latestTables {
          nodes {
            tableName
            tableSchema
          }
        }
      }
    }
  }
}
""",
    "GetRepoTables": """
query GetRepoTables($namespace: String!, $repository: String!) {
  repository(namespace: $namespace, repository: $repository) {
    latestTables {
      nodes {
        tableName
        tableSchema
      }
    }
  }
}
""",
}


def graphql_request(operation: str, variables: Dict[Any, Any]) -> Any:
    return requests.post(
        GRAPHQL_API_URL,
        headers={
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://api.splitgraph.com",
        },
        data=json.dumps(
            {
                "operationName": operation,
                "query": GRAPHQL_QUERIES[operation],
                "variables": variables,
            }
        ),
    ).json()


def parse_table_column(graphql_table_column: Any) -> TableColumn:
    return TableColumn(
        name=graphql_table_column[1],
        postgresql_type=graphql_table_column[2],
        is_primary_key=graphql_table_column[3],
        comment=graphql_table_column[4],
    )


def get_repo_list(namespace: str) -> List[RepositoryInfo]:
    response = graphql_request("GetNamespaceRepos", {"namespace": namespace})
    if response["data"]["namespace"] is None:
        # the namespace has been removed
        return []
    return [
        RepositoryInfo(
            namespace=namespace,
            repository=repo["repository"],
            readme=repo["repoProfileByNamespaceAndRepository"]["readme"],
            tables=[
                TableInfo(
                    name=table["tableName"],
                    columns=[
                        parse_table_column(column) for column in table["tableSchema"]
                    ],
                )
                for table in repo["latestTables"]["nodes"]
            ],
        )
        for repo in response["data"]["namespace"]["repositoriesByNamespace"]["nodes"]
    ]


def get_repo_tables(
    namespace: str, repository: str, use_fully_qualified_table_names=False
) -> List[TableInfo]:
    graphql_response = graphql_request(
        "GetRepoTables", {"namespace": namespace, "repository": repository}
    )
    # Repositories deleted since the last embedding indexing will return an empty
    # repository in the graphql response.
    if graphql_response["data"]["repository"] is None:
        return []
    return [
        TableInfo(
            name=f'"{namespace}/{repository}"."{table["tableName"]}"'
            if use_fully_qualified_table_names
            else table["tableName"],
            columns=[parse_table_column(column) for column in table["tableSchema"]],
        )
        for table in graphql_response["data"]["repository"]["latestTables"]["nodes"]
    ]


DDN_ERROR_PREFIX = "error: "


def ddn_query(sql) -> DDNResponse:
    parsed_response: DDNResponse = parse_obj_as(
        DDNResponse,  # type: ignore
        requests.post(
            SPLITGRAPH_DDN_URL,
            headers={
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            data=json.dumps({"sql": sql}),
        ).json(),
    )
    # remove unnecessary "error: " prefix from errors when present
    if isinstance(
        parsed_response, DDNResponseFailure
    ) and parsed_response.error.startswith(DDN_ERROR_PREFIX):
        parsed_response.error = parsed_response.error[len(DDN_ERROR_PREFIX) :]
    return parsed_response


def get_table_infos(
    repositories: List[Tuple[str, str]], use_fully_qualified_table_names=False
) -> List[TableInfo]:
    return list(
        itertools.chain(
            *[
                get_repo_tables(namespace, repository, use_fully_qualified_table_names)
                for namespace, repository in repositories
            ]
        )
    )


def get_query_editor_url(sql: str) -> str:
    return f"{SPLITGRAPH_WWW_URL_PREFIX}query?sqlQuery={urllib.parse.quote_plus(sql)}"


def run_sql(query: str) -> RunSQLResponse:
    ddn_response = ddn_query(query)
    if isinstance(ddn_response, DDNResponseFailure):
        return RunSQLResponse(
            error=ddn_response.error, query_editor_url=get_query_editor_url(query)
        )
    return RunSQLResponse(
        rows=ddn_response.rows, query_editor_url=get_query_editor_url(query)
    )

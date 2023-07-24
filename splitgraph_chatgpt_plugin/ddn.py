# based on: https://python.langchain.com/en/latest/modules/chains/examples/sqlite.html
import json
from typing import Any, Dict, List, NamedTuple, Optional
import requests
from pydantic import BaseModel
from typing import TypedDict

# The constructor of the SQLDatabase base class calls SQLAlchemy's inspect()
# which fails on the DDN since some of the required introspection tables are
# not available.
# Creating a child class doesn't solve the issue, since the base constructor
# is still called, and for typing, we need an instance of SQLDatabase.
#
# The currents solution is to mock out the inspect() function to return a
# SplitgraphInspector instance

GRAPHQL_API_URL = "https://api.splitgraph.com/gql/cloud/unified/graphql"

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


class TableColumn(NamedTuple):
    ordinal: int
    name: str
    pg_type: str
    is_pk: bool
    comment: Optional[str] = None


class TableInfo(TypedDict):
    name: str
    schema: List[TableColumn]


class RepositoryInfo(TypedDict):
    namespace: str
    repository: str
    tables: List[TableInfo]
    readme: str


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


def get_repo_list(namespace: str) -> List[RepositoryInfo]:
    repos = graphql_request("GetNamespaceRepos", {"namespace": namespace})["data"][
        "namespace"
    ]["repositoriesByNamespace"]["nodes"]
    return [
        {
            "namespace": namespace,
            "repository": repo["repository"],
            "readme": repo["repoProfileByNamespaceAndRepository"]["readme"],
            "tables": [
                {
                    "name": table["tableName"],
                    "schema": [TableColumn(*column) for column in table["tableSchema"]],
                }
                for table in repo["latestTables"]["nodes"]
            ],
        }
        for repo in repos
    ]


def get_repo_tables(namespace: str, repository: str) -> List[TableInfo]:
    return [
        {
            "name": table["tableName"],
            "schema": [TableColumn(*column) for column in table["tableSchema"]],
        }
        for table in graphql_request(
            "GetRepoTables", {"namespace": namespace, "repository": repository}
        )["data"]["repository"]["latestTables"]["nodes"]
    ]

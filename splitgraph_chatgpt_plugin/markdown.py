from typing import Any, List, Set, Tuple

from .config import SPLITGRAPH_WWW_URL_PREFIX
from .models import (
    DDNResponse,
    DDNResponseSuccess,
    RepositoryInfo,
    TableColumn,
    TableInfo,
)


REPOSITORY_DESCRIPTION = """
# Repository: {namespace}/{repository}

## description
{readme}

## tables
{tables}
""".lstrip()

TABLE_HEADER = """
### {tablename}
""".lstrip()

TABLE_DESCRIPTION = """
The table with the full name "{namespace}/{repository}"."{tablename}" includes the following columns:
{columns}
""".lstrip()


def column_info_to_markdown(column_info: TableColumn) -> str:
    return f"* {column_info.name} (type {column_info.postgresql_type}) {column_info.comment}"


def table_info_to_markdown(
    namespace: str, repository: str, table_info: TableInfo, emit_header=False
) -> str:
    return (
        TABLE_HEADER.format(tablename=table_info.name) if emit_header else ""
    ) + TABLE_DESCRIPTION.format(
        namespace=namespace,
        repository=repository,
        tablename=table_info.name,
        columns="\n".join([column_info_to_markdown(c) for c in table_info.columns]),
    )


def repository_info_to_markdown(repo_info: RepositoryInfo) -> str:
    result = REPOSITORY_DESCRIPTION.format(
        namespace=repo_info.namespace,
        repository=repo_info.repository,
        readme=repo_info.readme,
        tables="\n\n".join(
            [
                table_info_to_markdown(
                    repo_info.namespace,
                    repo_info.repository,
                    table,
                    emit_header=True,
                )
                for table in repo_info.tables
            ]
        ),
    )
    return result


def print_table_row(row: List[Any]) -> str:
    return "|" + " |".join([str(e) for e in row]) + " |\n"


def ddn_resultset_to_markdown(result: DDNResponseSuccess) -> str:
    if result.rowCount == 0:
        return "No rows returned by the DDN in response to the query."
    column_names_set: Set[str] = set()
    for field in result.fields:
        column_names_set.add(field.name)
    column_names = sorted(column_names_set)
    response = print_table_row(column_names)
    response += print_table_row(["---" for _ in column_names])
    for row in result.rows:
        response += print_table_row([row.get(c, "") for c in column_names])
    return response


def ddn_response_to_markdown(response: DDNResponse) -> str:
    if isinstance(response, DDNResponseSuccess):
        return ddn_resultset_to_markdown(response)
    return f"An error occurred while attempting to execute the query: {response.error}"


def get_repository_urls_as_markdown(repositories: List[Tuple[str, str]]) -> List[str]:
    return [
        f"* [{namespace}/{repository}]({SPLITGRAPH_WWW_URL_PREFIX}{namespace}/{repository})"
        for namespace, repository in repositories
    ]

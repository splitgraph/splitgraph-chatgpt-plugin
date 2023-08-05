from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class TableColumn(BaseModel):
    ordinal: int
    name: str
    postgresql_type: str
    is_primary_key: bool
    comment: Optional[str] = None


class TableInfo(BaseModel):
    name: str
    columns: List[TableColumn]


class RepositoryInfo(BaseModel):
    namespace: str
    repository: str
    tables: List[TableInfo]
    readme: str

class DDNResponseField(BaseModel):
    name: str
    tableID: int
    columnID: int
    dataTypeID: int
    dataTypeSize: int
    dataTypeModifier: int
    format: str
    formattedType: str


class DDNResponseSuccess(BaseModel):
    success: Literal[True]
    command: str
    rowCount: int
    rows: List[Dict[str, Any]]
    fields: List[DDNResponseField]
    executionTime: str
    executionTimeHighRes: str


class DDNResponseFailure(BaseModel):
    success: Literal[False]
    error: str


DDNResponse = Annotated[
    Union[DDNResponseSuccess, DDNResponseFailure], Field(discriminator="success")
]

class FindRelevantTablesResponse(BaseModel):
    tables: List[TableInfo]

class RunSQLResponse(BaseModel):
    error: Optional[str]
    rows: Optional[List[Any]]
    query_editor_url: str

"""Selección explícita de documentos ya existentes; nunca es autorización."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class SeleccionPDF(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    ids: list[Annotated[StrictInt, Field(gt=0)]] = Field(min_length=1)

    @field_validator("ids")
    @classmethod
    def identidades_unicas(cls, ids):
        if len(ids) != len(set(ids)):
            raise ValueError("La selección contiene comprobantes repetidos")
        return ids

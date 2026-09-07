"""Structured-output schemas. The domain model IS the extraction schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Frequency = Literal["monthly", "quarterly", "semi-annual", "annual", "on-event", "once", "ongoing"]


class Obligation(BaseModel):
    citation: str = Field(description="Section number as written in the document, e.g. '2.1'")
    requirement: str = Field(description="One imperative sentence stating what must be done")
    frequency: Frequency
    responsible_party: str | None = Field(default=None, description="Role named in the document, if any")
    due_rule: str | None = Field(default=None, description="Deadline phrase as written, if any")

    @field_validator("responsible_party", "due_rule", mode="before")
    @classmethod
    def _none_strings(cls, v):
        # Some models return the literal string "null" or "" for an absent value.
        if isinstance(v, str) and v.strip().lower() in ("", "null", "none", "n/a"):
            return None
        return v


class ObligationList(BaseModel):
    obligations: list[Obligation]


STRUCTURED_OUTPUT_MODELS: dict[str, type[BaseModel]] = {"ObligationList": ObligationList}

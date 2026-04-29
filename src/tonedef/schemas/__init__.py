from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BaseResponse(BaseModel):
    """Strict base class for future structured LLM outputs."""

    model_config = ConfigDict(strict=True)


class ExtractedEntity(BaseResponse):
    """Example schema for Instructor-backed structured extraction."""

    name: str = Field(description="The entity name exactly as it appears in the source text.")
    category: str = Field(description="A short category label for the entity.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0 to 1.")

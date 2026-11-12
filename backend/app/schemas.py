from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictInt, StrictStr, model_validator

from ml.inference import FEATURES_BY_NAME, FEATURE_CONTRACT

EmailValue = Annotated[EmailStr, Field(max_length=320)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: StrictInt
    mileage: StrictInt
    trim: StrictStr
    transmission: StrictStr
    body_status: StrictStr
    color: StrictStr


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: Annotated[str, Field(min_length=1, max_length=200)]
    email: EmailValue
    password: Annotated[str, Field(min_length=12, max_length=256)]
    password_confirmation: Annotated[str, Field(min_length=12, max_length=256)]

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirmation:
            raise ValueError("Password confirmation does not match.")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailValue
    password: Annotated[str, Field(min_length=1, max_length=256)]


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: Annotated[str, Field(min_length=1, max_length=256)]
    new_password: Annotated[str, Field(min_length=12, max_length=256)]


class UserPasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: Annotated[str, Field(min_length=1, max_length=256)]
    new_password: Annotated[str, Field(min_length=12, max_length=256)]
    password_confirmation: Annotated[str, Field(min_length=12, max_length=256)]

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.password_confirmation:
            raise ValueError("Password confirmation does not match.")
        return self


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailValue


class UserProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    email: EmailValue | None = None

    @model_validator(mode="after")
    def require_profile_field(self):
        if self.full_name is None and self.email is None:
            raise ValueError("Provide full_name or email.")
        return self


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, Field(min_length=1, max_length=200)] = "New conversation"


class ConversationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, Field(min_length=1, max_length=200)]


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: Annotated[str, Field(min_length=1, max_length=12000)]


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class RefreshResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class PredictionResponse(BaseModel):
    id: uuid.UUID
    input_data: dict
    predicted_price: float
    prediction_unit: str
    model_version: str
    created_at: datetime


class PredictionPage(BaseModel):
    items: list[PredictionResponse]
    total: int
    page: int
    page_size: int


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    message_metadata: dict | None = None


ItemT = TypeVar("ItemT")


class ItemsResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]


class MessageSubmissionResponse(BaseModel):
    items: list[MessageResponse]
    assistant_response_available: bool


class ConversationDetailResponse(BaseModel):
    items: list[ConversationResponse]


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int


def get_public_feature_contract() -> dict:
    feature_fields = (
        "name",
        "display_label",
        "type",
        "required",
        "minimum",
        "maximum",
        "unit",
        "supported_values",
        "constraint_note",
    )
    return {
        "features": [
            {key: feature.get(key) for key in feature_fields}
            for feature in FEATURES_BY_NAME.values()
        ],
        "target": {
            "name": "price",
            "unit": None,
            "unit_note": FEATURE_CONTRACT["target"]["unit_note"],
        },
    }

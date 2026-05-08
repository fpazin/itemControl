from __future__ import annotations

from dataclasses import dataclass


class ItemControlError(Exception):
    """Base exception for domain and application errors."""


class ValidationError(ItemControlError):
    """Raised when user input violates a business rule."""


class NotFoundError(ItemControlError):
    """Raised when a referenced record does not exist."""


@dataclass(frozen=True)
class Country:
    id: int
    name: str


@dataclass(frozen=True)
class Location:
    id: int
    country_id: int
    name: str


@dataclass(frozen=True)
class Item:
    id: int
    serial: str
    name: str
    current_location_id: int | None
    status: str


@dataclass(frozen=True)
class Movement:
    id: int
    item_id: int
    movement_type: str
    from_location_id: int | None
    to_location_id: int | None
    note: str | None
    created_at: str

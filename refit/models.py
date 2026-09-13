"""Persistent data model.

Uses SQLModel/SQLAlchemy directly rather than Reflex's ``rx.Model``, which is
deprecated as of Reflex 0.9.2 in favor of using the ORM layer directly.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "app_user"

    id: int | None = Field(default=None, primary_key=True)
    firebase_uid: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class Recipe(SQLModel, table=True):
    __tablename__ = "recipe"

    id: int | None = Field(default=None, primary_key=True)
    created_by_id: int = Field(foreign_key="app_user.id")
    title: str
    goal_summary: str = ""
    ingredients: list[str] = Field(sa_column=Column(JSON))
    steps: list[str] = Field(sa_column=Column(JSON))
    prep_time_minutes: int = 0
    servings: int = 0
    calories_kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    notes: str = ""
    source: str = "ai_generated"  # "ai_generated" | "manual"
    is_saved: bool = False
    created_at: datetime = Field(default_factory=_utcnow)


class MealLog(SQLModel, table=True):
    __tablename__ = "meal_log"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id")
    recipe_id: int = Field(foreign_key="recipe.id")
    portion: float = 1.0
    logged_at: datetime = Field(default_factory=_utcnow)

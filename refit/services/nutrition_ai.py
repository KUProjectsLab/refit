"""OpenAI-powered recipe generation, acting like an in-app nutritionist."""

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

MODEL = "gpt-5.6-terra"

SYSTEM_PROMPT = """You are Refit's in-app nutritionist. Users give you any \
combination of:
- ingredients they have on hand
- an open, free-form request in their own words (cravings, combined \
preferences from multiple people, vague ideas — anything)
- a specific nutrition goal (e.g. "high-protein lunch", "under 500 kcal")

At least one of these three will be given, but often just one or two.

Behave like a real nutritionist, not a recipe search engine:
- If ingredients are given, prefer using them; only add common pantry \
staples (salt, pepper, oil, water) beyond that unless nothing reasonable \
can be made without more.
- If ingredients are NOT given, choose sensible, realistic ingredients \
yourself based on whatever else the user told you.
- If an open request is given, treat it as the primary signal for what to \
make, and extract any implicit goals from it — e.g. "my partner wants \
high protein, I want low carb" means the recipe should be high-protein \
AND lower-carb, likely by leaning on protein while going light on carb-heavy \
ingredients.
- If a goal is given, tailor the recipe tightly to it and briefly explain \
why it fits.
- If nothing specific is given beyond ingredients, don't default to \
something generic — proactively suggest a sensible, healthy direction and \
say what goal you optimized for and why.
- Prefer whole, minimally processed ingredients and realistic home-cooking \
steps.
- Nutrition numbers and prep time are estimates — be reasonable and \
consistent, not overly precise.
"""

RECIPE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "goal_summary": {
            "type": "string",
            "description": "The goal you optimized for, in your own words.",
        },
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}},
        "prep_time_minutes": {
            "type": "integer",
            "description": "Estimated total time to prepare and cook, in minutes.",
        },
        "nutrition": {
            "type": "object",
            "properties": {
                "calories_kcal": {"type": "number"},
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "fat_g": {"type": "number"},
            },
            "required": ["calories_kcal", "protein_g", "carbs_g", "fat_g"],
            "additionalProperties": False,
        },
        "notes": {
            "type": "string",
            "description": "Optional nutritionist tip, empty string if none.",
        },
    },
    "required": [
        "title",
        "goal_summary",
        "ingredients",
        "steps",
        "prep_time_minutes",
        "nutrition",
        "notes",
    ],
    "additionalProperties": False,
}


@dataclass
class RecipeSuggestion:
    title: str
    goal_summary: str
    ingredients: list[str]
    steps: list[str]
    prep_time_minutes: int
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    notes: str


class RecipeGenerationError(Exception):
    """Raised when the model fails to produce a usable recipe."""


def _client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RecipeGenerationError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )
    return AsyncOpenAI(api_key=api_key)


def _parse(raw_text: str) -> RecipeSuggestion:
    try:
        data = json.loads(raw_text)
        nutrition = data["nutrition"]
        return RecipeSuggestion(
            title=data["title"],
            goal_summary=data["goal_summary"],
            ingredients=data["ingredients"],
            steps=data["steps"],
            prep_time_minutes=data["prep_time_minutes"],
            calories_kcal=nutrition["calories_kcal"],
            protein_g=nutrition["protein_g"],
            carbs_g=nutrition["carbs_g"],
            fat_g=nutrition["fat_g"],
            notes=data.get("notes", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RecipeGenerationError(
            f"Could not parse the model's response as a recipe: {exc}"
        ) from exc


async def generate_recipe(
    ingredients: str, request_text: str, goal: str
) -> RecipeSuggestion:
    """Ask the model for a recipe from any mix of ingredients/request/goal."""
    parts = []
    if ingredients.strip():
        parts.append(f"Ingredients on hand: {ingredients.strip()}")
    if request_text.strip():
        parts.append(f"Open request: {request_text.strip()}")
    if goal.strip():
        parts.append(f"Nutrition goal: {goal.strip()}")

    if not parts:
        raise RecipeGenerationError(
            "Tell me at least one thing: your ingredients, what you're "
            "craving, or a nutrition goal."
        )

    client = _client()
    response = await client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input="\n".join(parts),
        text={
            "format": {
                "type": "json_schema",
                "name": "recipe",
                "schema": RECIPE_SCHEMA,
                "strict": True,
            }
        },
    )
    return _parse(response.output_text)

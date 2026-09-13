"""OpenAI-powered recipe generation, acting like an in-app nutritionist."""

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

MODEL = "gpt-5.6-terra"

SYSTEM_PROMPT = """You are Refit's in-app nutritionist. Users tell you what \
ingredients they have on hand and, optionally, a nutrition goal (e.g. \
"high-protein lunch", "under 500 kcal", "low-carb dinner").

Behave like a real nutritionist, not a recipe search engine:
- If the user gives a clear goal, tailor the recipe tightly to it and briefly \
explain why it fits (e.g. why it's high in protein).
- If the user gives no goal or a vague one, don't default to something \
generic — proactively suggest a sensible, healthy direction based on the \
ingredients available, and state what goal you optimized for and why.
- Prefer whole, minimally processed ingredients and realistic home-cooking \
steps.
- Only use ingredients the user listed, plus common pantry staples (salt, \
pepper, oil, water) unless nothing reasonable can be made without more.
- Nutrition numbers are estimates — be reasonable and consistent, not overly \
precise.
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


async def generate_recipe(ingredients: str, goal: str) -> RecipeSuggestion:
    """Ask the model to generate a recipe from ingredients and an optional goal."""
    if not ingredients.strip():
        raise RecipeGenerationError("Please list at least one ingredient.")

    user_content = f"Ingredients on hand: {ingredients.strip()}\n"
    user_content += (
        f"Nutrition goal: {goal.strip()}"
        if goal.strip()
        else "Nutrition goal: none given — use your judgment."
    )

    client = _client()
    response = await client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=user_content,
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

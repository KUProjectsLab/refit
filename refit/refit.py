"""re-fit: an AI nutritionist that turns what's in your kitchen into a recipe."""

import reflex as rx
from sqlmodel import select

from refit.db import create_db_and_tables, get_or_create_default_user, get_session
from refit.models import MealLog, Recipe
from refit.services.nutrition_ai import (
    RecipeGenerationError,
    generate_recipe,
    refine_recipe,
)

try:
    create_db_and_tables()
except RuntimeError as exc:
    print(f"[refit] Skipping DB setup: {exc}")


FONT_STYLESHEET = (
    "https://fonts.googleapis.com/css2?"
    "family=Fraunces:opsz,wght@9..144,500;9..144,600&"
    "family=Inter:wght@400;500;600&display=swap"
)
BODY_FONT = "Inter, sans-serif"
DISPLAY_FONT = "Fraunces, serif"


class RecipeState(rx.State):
    """State for the recipe generation flow."""

    ingredients: str = ""
    request_text: str = ""
    goal: str = ""
    servings: str = ""
    cuisine: str = ""
    is_loading: bool = False
    error: str = ""
    save_confirmation: str = ""

    has_recipe: bool = False
    current_recipe_id: int | None = None
    last_response_id: str | None = None
    follow_up_text: str = ""
    recipe_title: str = ""
    recipe_goal_summary: str = ""
    recipe_ingredients: list[str] = []
    recipe_steps: list[str] = []
    recipe_prep_time: int = 0
    recipe_servings: int = 0
    recipe_calories: float = 0
    recipe_protein: float = 0
    recipe_carbs: float = 0
    recipe_fat: float = 0
    recipe_notes: str = ""

    logged_meals: list[str] = []
    saved_recipes: list[str] = []

    def set_ingredients(self, value: str):
        self.ingredients = value

    def set_request_text(self, value: str):
        self.request_text = value

    def set_goal(self, value: str):
        self.goal = value

    def set_servings(self, value: str):
        self.servings = value

    def set_cuisine(self, value: str):
        self.cuisine = value

    def set_follow_up_text(self, value: str):
        self.follow_up_text = value

    @rx.event(background=True)
    async def generate(self):
        async with self:
            self.is_loading = True
            self.error = ""
            self.has_recipe = False
            self.current_recipe_id = None
            self.last_response_id = None
            self.follow_up_text = ""
            self.save_confirmation = ""
            ingredients = self.ingredients
            request_text = self.request_text
            goal = self.goal
            servings = self.servings
            cuisine = self.cuisine

        try:
            suggestion, response_id = await generate_recipe(
                ingredients, request_text, goal, servings, cuisine
            )
            async with self:
                self._apply_suggestion(suggestion)
                self.last_response_id = response_id
                self.has_recipe = True
        except RecipeGenerationError as exc:
            async with self:
                self.error = str(exc)
        finally:
            async with self:
                self.is_loading = False

    @rx.event(background=True)
    async def refine(self):
        async with self:
            if not self.has_recipe or self.last_response_id is None:
                return
            self.is_loading = True
            self.error = ""
            follow_up_text = self.follow_up_text
            previous_response_id = self.last_response_id

        try:
            suggestion, response_id = await refine_recipe(
                follow_up_text, previous_response_id
            )
            async with self:
                self._apply_suggestion(suggestion)
                self.last_response_id = response_id
                # A revised recipe is a new version -- logging/saving after
                # this creates a fresh row rather than overwriting history.
                self.current_recipe_id = None
                self.save_confirmation = ""
                self.follow_up_text = ""
        except RecipeGenerationError as exc:
            async with self:
                self.error = str(exc)
        finally:
            async with self:
                self.is_loading = False

    def _apply_suggestion(self, suggestion):
        self.recipe_title = suggestion.title
        self.recipe_goal_summary = suggestion.goal_summary
        self.recipe_ingredients = suggestion.ingredients
        self.recipe_steps = suggestion.steps
        self.recipe_prep_time = suggestion.prep_time_minutes
        self.recipe_servings = suggestion.servings
        self.recipe_calories = suggestion.calories_kcal
        self.recipe_protein = suggestion.protein_g
        self.recipe_carbs = suggestion.carbs_g
        self.recipe_fat = suggestion.fat_g
        self.recipe_notes = suggestion.notes

    def start_over(self):
        self.ingredients = ""
        self.request_text = ""
        self.goal = ""
        self.servings = ""
        self.cuisine = ""
        self.error = ""
        self.save_confirmation = ""
        self.has_recipe = False
        self.current_recipe_id = None
        self.last_response_id = None
        self.follow_up_text = ""

    def load_history(self):
        with get_session() as session:
            user = get_or_create_default_user(session)
            logged = session.exec(
                select(MealLog, Recipe)
                .join(Recipe, MealLog.recipe_id == Recipe.id)
                .where(MealLog.user_id == user.id)
                .order_by(MealLog.logged_at.desc())
            ).all()
            self.logged_meals = [
                f"{recipe.title} — {recipe.calories_kcal:g} kcal, "
                f"{recipe.protein_g:g} g protein"
                for _meal_log, recipe in logged
            ]
            saved = session.exec(
                select(Recipe)
                .where(Recipe.created_by_id == user.id, Recipe.is_saved == True)  # noqa: E712
                .order_by(Recipe.created_at.desc())
            ).all()
            self.saved_recipes = [
                f"{recipe.title} — {recipe.calories_kcal:g} kcal, "
                f"{recipe.protein_g:g} g protein"
                for recipe in saved
            ]

    def _get_or_create_recipe(self, session, user) -> Recipe:
        if self.current_recipe_id is not None:
            recipe = session.get(Recipe, self.current_recipe_id)
            if recipe is not None:
                return recipe
        recipe = Recipe(
            created_by_id=user.id,
            title=self.recipe_title,
            goal_summary=self.recipe_goal_summary,
            ingredients=self.recipe_ingredients,
            steps=self.recipe_steps,
            prep_time_minutes=self.recipe_prep_time,
            servings=self.recipe_servings,
            calories_kcal=self.recipe_calories,
            protein_g=self.recipe_protein,
            carbs_g=self.recipe_carbs,
            fat_g=self.recipe_fat,
            notes=self.recipe_notes,
        )
        session.add(recipe)
        session.commit()
        session.refresh(recipe)
        self.current_recipe_id = recipe.id
        return recipe

    def log_meal(self):
        if not self.has_recipe:
            return
        with get_session() as session:
            user = get_or_create_default_user(session)
            recipe = self._get_or_create_recipe(session, user)
            session.add(MealLog(user_id=user.id, recipe_id=recipe.id))
            session.commit()
        self.save_confirmation = "Logged."
        self.load_history()

    def save_recipe(self):
        if not self.has_recipe:
            return
        with get_session() as session:
            user = get_or_create_default_user(session)
            recipe = self._get_or_create_recipe(session, user)
            recipe.is_saved = True
            session.add(recipe)
            session.commit()
        self.save_confirmation = "Saved to your recipe book."
        self.load_history()


def recipe_card() -> rx.Component:
    return rx.cond(
        RecipeState.has_recipe,
        rx.card(
            rx.vstack(
                rx.heading(RecipeState.recipe_title, size="5"),
                rx.text(RecipeState.recipe_goal_summary, color="gray"),
                rx.heading("Ingredients", size="3"),
                rx.unordered_list(
                    rx.foreach(
                        RecipeState.recipe_ingredients,
                        lambda item: rx.list_item(item),
                    )
                ),
                rx.heading("Steps", size="3"),
                rx.ordered_list(
                    rx.foreach(
                        RecipeState.recipe_steps,
                        lambda step: rx.list_item(step),
                    )
                ),
                rx.hstack(
                    rx.badge(f"{RecipeState.recipe_prep_time} min prep"),
                    rx.badge(f"Serves {RecipeState.recipe_servings}"),
                    rx.badge(f"{RecipeState.recipe_calories} kcal"),
                    rx.badge(f"{RecipeState.recipe_protein} g protein"),
                    rx.badge(f"{RecipeState.recipe_carbs} g carbs"),
                    rx.badge(f"{RecipeState.recipe_fat} g fat"),
                    wrap="wrap",
                ),
                rx.cond(
                    RecipeState.recipe_notes,
                    rx.text(RecipeState.recipe_notes, font_style="italic"),
                ),
                rx.text(
                    "Missing an ingredient? Want something different?",
                    size="2",
                    weight="medium",
                    color="gray",
                ),
                rx.text_area(
                    placeholder=(
                        'e.g. "No paprika, what can I use instead?" or '
                        '"make it spicier"'
                    ),
                    value=RecipeState.follow_up_text,
                    on_change=RecipeState.set_follow_up_text,
                    width="100%",
                ),
                rx.button(
                    rx.cond(RecipeState.is_loading, "Updating...", "Update recipe"),
                    on_click=RecipeState.refine,
                    loading=RecipeState.is_loading,
                    variant="soft",
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        "New recipe", on_click=RecipeState.start_over, variant="soft"
                    ),
                    rx.button("Log this meal", on_click=RecipeState.log_meal),
                    rx.button(
                        "Save this recipe",
                        on_click=RecipeState.save_recipe,
                        variant="outline",
                    ),
                    wrap="wrap",
                ),
                rx.cond(
                    RecipeState.save_confirmation,
                    rx.text(RecipeState.save_confirmation, color="green"),
                ),
                spacing="3",
                align="start",
            ),
            width="100%",
        ),
    )


def history_list(title: str, items: rx.Var[list[str]]) -> rx.Component:
    return rx.cond(
        items,
        rx.vstack(
            rx.heading(title, size="4"),
            rx.foreach(items, lambda item: rx.text(item)),
            width="100%",
            align="start",
        ),
    )


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("re-fit", size="9", font_family=DISPLAY_FONT),
            rx.text(
                "Your AI nutritionist — a recipe built around what you have "
                "and what you need.",
                size="4",
            ),
            rx.text(
                "Start with your ingredients, a craving, or a goal below.",
                size="2",
                color="gray",
            ),
            rx.text_area(
                placeholder="Ingredients you have (e.g. zucchini, eggs, feta)",
                value=RecipeState.ingredients,
                on_change=RecipeState.set_ingredients,
                width="100%",
            ),
            rx.text("or", size="1", color="gray", align_self="center"),
            rx.text_area(
                placeholder=(
                    'No ingredients in mind? Just ask — e.g. "My partner wants '
                    'high-protein, I want low-carb — what should we make?"'
                ),
                value=RecipeState.request_text,
                on_change=RecipeState.set_request_text,
                width="100%",
            ),
            rx.text(
                "Preferences",
                size="2",
                weight="medium",
                color="gray",
                align_self="start",
                margin_top="0.5em",
            ),
            rx.input(
                placeholder="Nutrition goal (optional) — e.g. high-protein lunch",
                value=RecipeState.goal,
                on_change=RecipeState.set_goal,
                width="100%",
            ),
            rx.input(
                placeholder="Servings (optional) — e.g. 2",
                value=RecipeState.servings,
                on_change=RecipeState.set_servings,
                width="100%",
            ),
            rx.input(
                placeholder="Cuisine (optional) — e.g. Turkish, Thai, Italian",
                value=RecipeState.cuisine,
                on_change=RecipeState.set_cuisine,
                width="100%",
            ),
            rx.button(
                rx.cond(RecipeState.is_loading, "Thinking...", "Generate recipe"),
                on_click=RecipeState.generate,
                loading=RecipeState.is_loading,
                width="100%",
            ),
            rx.cond(
                RecipeState.error,
                rx.callout(RecipeState.error, color_scheme="red"),
            ),
            recipe_card(),
            history_list("Today's log", RecipeState.logged_meals),
            history_list("Saved recipes", RecipeState.saved_recipes),
            spacing="4",
            width="100%",
            max_width="640px",
            padding_y="2em",
        ),
        font_family=BODY_FONT,
    )


app = rx.App(stylesheets=[FONT_STYLESHEET, "/theme.css"])
app.add_page(index, title="re-fit", on_load=RecipeState.load_history)

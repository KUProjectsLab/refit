"""Refit: an AI nutritionist that turns what's in your kitchen into a recipe."""

import reflex as rx

from refit.services.nutrition_ai import RecipeGenerationError, generate_recipe


class RecipeState(rx.State):
    """State for the recipe generation flow."""

    ingredients: str = ""
    goal: str = ""
    is_loading: bool = False
    error: str = ""

    has_recipe: bool = False
    recipe_title: str = ""
    recipe_goal_summary: str = ""
    recipe_ingredients: list[str] = []
    recipe_steps: list[str] = []
    recipe_calories: float = 0
    recipe_protein: float = 0
    recipe_carbs: float = 0
    recipe_fat: float = 0
    recipe_notes: str = ""

    logged_meals: list[str] = []

    def set_ingredients(self, value: str):
        self.ingredients = value

    def set_goal(self, value: str):
        self.goal = value

    @rx.event(background=True)
    async def generate(self):
        async with self:
            self.is_loading = True
            self.error = ""
            self.has_recipe = False
            ingredients = self.ingredients
            goal = self.goal

        try:
            suggestion = await generate_recipe(ingredients, goal)
            async with self:
                self.recipe_title = suggestion.title
                self.recipe_goal_summary = suggestion.goal_summary
                self.recipe_ingredients = suggestion.ingredients
                self.recipe_steps = suggestion.steps
                self.recipe_calories = suggestion.calories_kcal
                self.recipe_protein = suggestion.protein_g
                self.recipe_carbs = suggestion.carbs_g
                self.recipe_fat = suggestion.fat_g
                self.recipe_notes = suggestion.notes
                self.has_recipe = True
        except RecipeGenerationError as exc:
            async with self:
                self.error = str(exc)
        finally:
            async with self:
                self.is_loading = False

    def log_meal(self):
        if self.has_recipe:
            summary = (
                f"{self.recipe_title} — {self.recipe_calories:g} kcal, "
                f"{self.recipe_protein:g} g protein"
            )
            self.logged_meals = [*self.logged_meals, summary]


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
                rx.button("Log this meal", on_click=RecipeState.log_meal),
                spacing="3",
                align="start",
            ),
            width="100%",
        ),
    )


def logged_meals_view() -> rx.Component:
    return rx.cond(
        RecipeState.logged_meals,
        rx.vstack(
            rx.heading("Today's log", size="4"),
            rx.foreach(
                RecipeState.logged_meals,
                lambda meal: rx.text(meal),
            ),
            width="100%",
            align="start",
        ),
    )


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Refit", size="9"),
            rx.text(
                "Tell me what you have and what you're aiming for.",
                color="gray",
            ),
            rx.text_area(
                placeholder="Ingredients you have (e.g. zucchini, eggs, feta)",
                value=RecipeState.ingredients,
                on_change=RecipeState.set_ingredients,
                width="100%",
            ),
            rx.input(
                placeholder="Nutrition goal (optional) — e.g. high-protein lunch",
                value=RecipeState.goal,
                on_change=RecipeState.set_goal,
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
            logged_meals_view(),
            spacing="4",
            width="100%",
            max_width="640px",
            padding_y="2em",
        ),
    )


app = rx.App()
app.add_page(index, title="Refit")

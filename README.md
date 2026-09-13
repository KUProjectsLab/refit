# re-fit

re-fit is an AI nutritionist for your kitchen. Tell it what ingredients you have and what you're aiming for — "high-protein lunch," "under 500 kcal," or nothing specific at all — and it generates a recipe tailored to that goal, with estimated calories, protein, carbs, and fat. Generated recipes can be logged to track what you've actually eaten.

Unlike typical calorie counters that only log food after the fact, re-fit helps you decide what to cook *before* you cook it, based on what's already in your kitchen and what you're trying to achieve nutritionally.

## Status

Early, private development. Built first for personal use; open-sourcing and a public launch are planned for a later phase. See the [Wiki](../../wiki) for architecture details and the roadmap, and [TODO/](TODO/) for deferred features.

## Tech stack

- **Language/framework:** Python, [Reflex](https://reflex.dev) (full-stack, no JS)
- **AI:** OpenAI API — generates recipes and estimates nutrition, prompted to behave like a nutritionist rather than a recipe search engine
- **Database:** [Neon](https://neon.tech) (serverless Postgres), planned via SQLModel
- **Auth:** Firebase Authentication, planned
- **Hosting:** [Reflex Cloud](https://reflex.dev/hosting/) free tier, planned

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in OPENAI_API_KEY
reflex init
reflex run
```

The app runs at `http://localhost:3000` by default.

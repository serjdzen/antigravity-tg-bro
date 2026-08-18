# Contributing to Antigravity Telegram Bot

Thank you for your interest in contributing! This project is open-source and welcomes contributions, bug reports, and feature requests.

## Development Setup

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/serjdzen/antigravity-tg-bro.git
   cd antigravity-tg-bro
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set up your environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your test Telegram Bot token and user ID
   ```

4. **Run offline tests**:
   ```bash
   pytest tests/
   ```

## Pull Request Guidelines

1. Create a new branch for your feature or bug fix: `git checkout -b feat/your-feature-name`.
2. Follow standard PEP 8 formatting.
3. Ensure no personal credentials or hardcoded paths are committed.
4. Add unit tests for new utility or engine functionality.
5. Open a Pull Request with a clear description of the changes.

## Code of Conduct

Please be respectful, collaborative, and constructive in all discussions and code reviews.

# Contributing

Thank you for your interest in Movilidad ESII. Contributions, bug reports, and suggestions are welcome.

## Reporting issues

Open an issue on GitHub describing:
- What you expected to happen.
- What actually happened (include any error messages or screenshots).
- Steps to reproduce.

## Submitting a pull request

1. Fork the repository and create a branch from `main`.
2. Set up the development environment (see [ 4 of the README](README.md#4-development-setup)).
3. Make your changes. Run the test suite before opening a PR:
   ```bash
   pytest -v
   ```
4. Open a pull request against `main` with a clear description of what changes and why.

## Code style

- Python 3.12, formatted with [Ruff](https://docs.astral.sh/ruff/) (same as the CI lint workflow).
- No new external dependencies without discussion first.

## Licence

By contributing you agree that your work will be released under the project's [CC BY-NC 4.0](LICENSE) licence.

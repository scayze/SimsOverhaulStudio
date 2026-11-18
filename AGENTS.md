# Sim Overhaul Studio

Sim Overhaul Studio is a local Python app with a browser UI for importing and editing Sims 4 households and exporting those edits as a mod. The studio reads game files, saves, and Tray files without modifying them. Editable projects live in `projects/` and generated mods go to `exports/`.

## Repository overview

- `app.py` runs the local server. Use `Start Studio.bat` to launch the app.
- `backend/` handles imports, project data, and mod exports. `ui/` contains the browser frontend.
- `SimsDataSDK/` is the upstream Git submodule that provides game, save, and Tray data extraction.
- `tests/` contains the Studio tests. Run them from the repo root with `python -m pytest tests`.

## Working with the user

The person prompting the agent for this project does not have a technical background. Treat their description of what they want to accomplish as the requirement. Verify any technical assumptions against the code and use your own engineering judgment to choose, implement, and test the solution.

When a request is informal or suggests a specific implementation, consider the user-facing outcome behind it. Use that intent to guide the work while respecting explicit constraints. Ask in plain language if different interpretations would materially change the result.

## SDK changes

Use the existing SDK interfaces for Studio work. If a feature the user requests requires an upstream SDK change to implement it cleanly, tell the user exactly: “Tell manu to adjust the SDK for you”. Briefly explain what the SDK needs to provide and why the feature depends on it.

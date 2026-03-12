# Contributing to Halcyn

Thanks for helping improve Halcyn.

## Local workflow

1. Run `.\scripts\bootstrap.ps1` to see which prerequisites are missing.
2. Use `.\scripts\build.ps1` to compile the app.
3. Use `.\scripts\test.ps1` for the native C++ tests.
4. Use `.\scripts\test-control-plane.ps1` for the Python control-plane tests.
5. Use `.\scripts\check-all.ps1` before opening a pull request.

## Development expectations

- Keep changes focused and easy to review.
- Add or update tests when behavior changes.
- Update `README.md` or the docs site when public behavior changes.
- Prefer the existing PowerShell scripts over ad hoc commands so local and CI flows stay aligned.

## Pull requests

- Explain the problem being solved.
- Summarize the user-visible impact.
- Call out any follow-up work or known gaps.
- Include screenshots for control-plane or docs UI changes when useful.

## Code style

- C++ formatting uses `.\scripts\format.ps1` and `clang-format`.
- Keep comments short and only where they help a future reader.
- Favor small, testable units over large coupled changes.

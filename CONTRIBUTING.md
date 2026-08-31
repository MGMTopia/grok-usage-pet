# Contributing

Grok Usage Pet is a small, local-first desktop utility. Focus changes on quota reliability, privacy, Windows packaging, animation quality, and maintainable skin support rather than expanding it into a general AI dashboard.

## Feedback

- Use a bug form for reproducible failures.
- Use a feature form or Discussions for ideas, questions, theme proposals, and polls.
- Use GitHub private vulnerability reporting for security issues.

Never post access or refresh tokens, `auth.json`, `state.vscdb`, quota snapshots, personal paths, email addresses, or full logs. Reduce logs to the smallest sanitized excerpt that reproduces the problem.

## Pull requests

Keep changes focused and explain the user-visible behavior. Run the offline test suite before opening a pull request:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-tests.ps1
```

New network endpoints require matching security documentation and offline mocked tests. New themes must use original or clearly redistributable artwork, stay inside `skins/<id>/`, include the required metadata, and pass atlas validation. Do not add new third-party character artwork without documented redistribution permission.

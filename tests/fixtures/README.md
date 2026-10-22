# ZIP test fixtures

These small data-only ZIP archives were generated with Python's standard `zipfile` module, using a fixed timestamp of 2026-10-22. They contain no executable files or user documents.

- `utf8-entry.zip`: UTF-8-flagged entry `报告😀.xml`, content `external UTF-8 archive`. This independently generated input checks that kernel reading follows the ZIP UTF-8 flag.
- `legacy-entry.zip`: unflagged ASCII entry `legacy.txt`, content `legacy entry`. This checks the legacy, non-UTF-8 read path; it does not establish cross-code-page compatibility for every historical OEM filename.

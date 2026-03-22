# Ingest notes

- Parsed 36 rows from raw Telegram paste.
- Column header mentioned supervisor, but no supervisor names were actually present in the provided rows; treated first text field after row number as project name.
- Preserved trailing anomalies like `Ver repositorio` and `Video 1mes` in `notes`.
- Tracks were split on commas only; multi-word track labels preserved.

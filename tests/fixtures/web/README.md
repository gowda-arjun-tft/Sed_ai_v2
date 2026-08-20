# Offline web fixtures

An empty fixture root intentionally returns no sources and exercises the `cannot be answered`
path without a model or network call.

To add a result, write `queries/<sha256-of-normalized-query>.json` as an array of objects containing
`url`, `title`, and optional `snippet`. Store its bytes at `pages/<sha256-of-url>.bin`; an optional
same-named `.json` may define `content_type`, `fetched_at`, `publisher`, and `publication_date`.

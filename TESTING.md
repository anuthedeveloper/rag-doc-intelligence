# Automated tests

Run the endpoint and feature tests locally without PostgreSQL, Redis, or calls
to the embedding and Anthropic APIs:

```bash
python run_tests.py
```

Pass standard Django test options or app labels to the script as needed, for
example `python run_tests.py documents`.

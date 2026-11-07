"""v0.6 web interface (docs/v0.6-web-interface-spec.md).

Keep this file free of imports: reader.py imports web.queries, and importing
a subpackage first runs its __init__.py. Importing FastAPI here would make
the standard-library-only reader depend on it.
"""

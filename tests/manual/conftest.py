"""Manual test scripts — not auto-discovered by pytest.

These are standalone development/preview scripts that require manual execution:
  python tests/manual/test_render_adviesrapport.py
  python tests/manual/test_render_pdf.py
  etc.
"""

collect_ignore_glob = ["test_*.py"]

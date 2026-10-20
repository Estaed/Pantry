"""A failing test file for the gate's self-check: tests/acceptance.py runs it the way it runs tests/test_*.py
and must report it as failed. It lives here, not in tests/, so it is never part of the suite."""
import sys

print("FAIL this file always fails (gate self-check fixture)")
sys.exit(1)

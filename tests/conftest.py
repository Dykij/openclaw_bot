"""Shared pytest configuration and fixtures for OpenClaw test suite."""

import sys
import os

# Ensure project root is on sys.path for all tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "destructive: tests that mutate source files (deselect with '-m \"not destructive\"')")

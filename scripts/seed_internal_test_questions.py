#!/usr/bin/env python3
"""
Idempotent seed of internal test (personality) questions only.
Used by Docker/Railway after migrations so production DB always has 40 active questions.

Full seed (roles, commission user): scripts/seed.py
"""

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

seed_path = ROOT / "scripts" / "seed.py"
spec = importlib.util.spec_from_file_location("invision_seed_internal_test", seed_path)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load scripts/seed.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.seed_questions()

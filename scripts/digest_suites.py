"""Refresh catalog fingerprints after editing the release suite."""
import json

from app.config import ROOT
from app.domain.content import suite_digest

folder = ROOT / "runner" / "quest_runner" / "suites"
catalog = folder / "catalog.json"
suites = json.loads(catalog.read_bytes())
for suite in suites:
    suite["digest"] = suite_digest((folder / suite.get("source", "m0.py")).read_bytes(), suite)
catalog.write_text(json.dumps(suites, indent=2) + "\n", encoding="utf-8")

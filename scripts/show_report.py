from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
for name in ("evaluation_metrics.json", "metrics.json", "benchmark.json", "thresholds.json"):
    path = root / "backend" / "artifacts" / name
    print(f"\n===== {name} =====")
    print(path.read_text(encoding="utf-8") if path.exists() else "missing")

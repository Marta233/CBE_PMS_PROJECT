"""Reset objective packages to a clean demo seed.

Run from Back_End/:
    python -m scripts.db.reset_demo
"""
from __future__ import annotations

from .init_db import ensure_demo_users, reset_demo_objective_sets


def main() -> None:
    ensure_demo_users()
    reset_demo_objective_sets()
    print("Cleared all objective packages.")
    print("  Org, demo users, and permissions are intact.")
    print("  No objectives were seeded - generate them yourself before the demo.")


if __name__ == "__main__":
    main()

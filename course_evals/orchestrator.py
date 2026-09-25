"""Public orchestration entry point for locked-run grading.

The compatibility implementation remains in ``grader.py`` while the original
single-case runtime is migrated. New callers should import from this module.
"""

from .grader import grade_run

__all__ = ["grade_run"]

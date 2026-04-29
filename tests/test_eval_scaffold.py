from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.eval


def test_live_eval_scaffold_is_explicitly_gated() -> None:
    if os.environ.get("RUN_LIVE_EVALS") != "1":
        pytest.skip("Set RUN_LIVE_EVALS=1 to run live evaluation scaffolds.")

    from deepeval.test_case import LLMTestCase

    test_case = LLMTestCase(input="What is this project?", actual_output="An AI project.")
    assert test_case.input

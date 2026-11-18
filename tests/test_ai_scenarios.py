"""Runs every reliability scenario from scenarios.py as an individual pytest case."""

import pytest

from pawpal_ai import PlanningAgent
from scenarios import SCENARIOS, TODAY

CASES = [(s, label, fn) for s in SCENARIOS for label, fn in s.expectations]


@pytest.mark.parametrize("scenario,label,check", CASES,
                         ids=[f"{s.name}::{label}" for s, label, _ in CASES])
def test_scenario_expectation(scenario, label, check):
    owner, llm = scenario.build()
    result = PlanningAgent(llm=llm).run(owner, TODAY)
    assert check(result, llm), f"{scenario.name}: expected '{label}'"

import importlib.util
from itertools import product
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "baseline_models.py"
spec = importlib.util.spec_from_file_location("baseline_models", SCRIPT)
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)


class RegressionBaselines(unittest.TestCase):
    def test_integer_targets_keep_fractional_mean(self):
        result = models.run_regression_baselines([[0], [1]], [0, 1], [[0], [1]], [0, 1])
        self.assertEqual(result[0]["predictions"], [0.5, 0.5])
        self.assertEqual(result[0]["mae"], 0.5)
        self.assertEqual(result[0]["rmse"], 0.5)

    def test_noisy_ols_matches_hand_calculated_solution(self):
        result = models.run_regression_baselines([[0], [1], [2]], [1, 2, 2], [[3]], [3])[1]
        self.assertAlmostEqual(result["intercept"], 7 / 6)
        self.assertAlmostEqual(result["coefficients"][0], 0.5)
        self.assertAlmostEqual(result["predictions"][0], 8 / 3)
        self.assertAlmostEqual(result["mae"], 1 / 3)
        self.assertIsNone(result["r2"])

    def test_multiple_features_match_known_linear_relation(self):
        result = models.run_regression_baselines(
            [[0, 0], [1, 0], [0, 1], [1, 1]], [1, 3, -2, 0], [[2, -1], [-1, 2]], [8, -7])[1]
        np.testing.assert_allclose(result["predictions"], [8, -7], atol=1e-12)
        np.testing.assert_allclose(result["coefficients"], [2, -3], atol=1e-12)
        self.assertAlmostEqual(result["r2"], 1)

    def test_test_targets_do_not_change_predictions_or_training_inputs(self):
        train = np.array([[0.0], [1.0], [2.0]])
        original = train.copy()
        first = models.run_regression_baselines(train, [2, 4, 6], [[3], [4]], [8, 10])
        second = models.run_regression_baselines(train, [2, 4, 6], [[3], [4]], [-99, 99])
        for one, two in zip(first, second):
            self.assertEqual(one["predictions"], two["predictions"])
        np.testing.assert_array_equal(train, original)

    def test_constant_target_and_rank_deficiency_are_explicit(self):
        result = models.run_regression_baselines([[1, 1], [1, 1]], [4, 4], [[1, 1], [1, 1]], [4, 4])
        self.assertIsNone(result[0]["r2"])
        self.assertIsNone(result[1]["r2"])
        self.assertFalse(result[1]["full_column_rank"])
        self.assertAlmostEqual(result[1]["mae"], 0)

    def test_bad_shape_and_nonfinite_inputs_are_rejected(self):
        for target in ([1], [1, np.nan], [1, np.inf], [1, 2j]):
            with self.subTest(target=target), self.assertRaises(ValueError):
                models.run_regression_baselines([[0], [1]], target, [[2]], [3])

    def test_explicit_json_output_is_portable_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="mathorcup_baseline_") as temporary:
            target = Path(temporary) / "中文 结果"
            result = models.run_regression_baselines([[0], [1]], [0, 1], [[2]], [2], target)
            path = target / "regression_baselines.json"
            before = path.read_bytes()
            self.assertEqual(json.loads(before), result)
            with self.assertRaises(FileExistsError):
                models.run_regression_baselines([[0], [1]], [2, 4], [[2]], [6], target)
            self.assertEqual(path.read_bytes(), before)


class ForecastBaselines(unittest.TestCase):
    def test_fixed_origin_does_not_use_test_observations(self):
        result = models.run_time_series_baselines([1, 2, 4], [100, 200], protocol="fixed_origin", window=2)
        self.assertEqual(result[0]["predictions"], [4.0, 4.0])
        self.assertEqual(result[1]["predictions"], [3.0, 3.0])
        self.assertEqual(result[0]["forecast_horizons"], [1, 2])

    def test_rolling_forecast_reveals_only_previous_observations(self):
        result = models.run_time_series_baselines([1, 2, 4], [100, 200], protocol="rolling_one_step", window=2)
        changed = models.run_time_series_baselines([1, 2, 4], [100, -999], protocol="rolling_one_step", window=2)
        self.assertEqual(result[0]["predictions"], [4.0, 100.0])
        self.assertEqual(result[1]["predictions"], [3.0, 52.0])
        self.assertEqual(result[1]["predictions"], changed[1]["predictions"])
        self.assertEqual(result[0]["forecast_horizons"], [1, 1])

    def test_protocol_and_window_must_be_valid(self):
        with self.assertRaises(TypeError):
            models.run_time_series_baselines([1, 2, 3], [4])
        with self.assertRaises(ValueError):
            models.run_time_series_baselines([1, 2, 3], [4], protocol="unknown")
        for window in (0, 4, True, 1.5):
            with self.subTest(window=window), self.assertRaises(ValueError):
                models.run_time_series_baselines([1, 2, 3], [4], protocol="fixed_origin", window=window)


class FacilityBaseline(unittest.TestCase):
    def test_known_optimum_and_complete_allocations(self):
        result = models.solve_facility_allocation_milp([[1, 5], [4, 1]], [2, 3], [4, 4], [3, 2])
        self.assertAlmostEqual(result["objective_value"], 10)
        self.assertEqual(result["opened_facilities"], [0, 1])
        np.testing.assert_allclose(result["allocation"], [[2, 0], [0, 3]], atol=1e-8)

    def test_fractional_demand_can_be_split(self):
        result = models.solve_facility_allocation_milp([[1], [2]], [1.5], [1, 1], [0, 0])
        self.assertAlmostEqual(result["objective_value"], 2)
        np.testing.assert_allclose(result["allocation"], [[1], [0.5]], atol=1e-8)

    def test_matches_independent_enumeration(self):
        rng = np.random.default_rng(20261001)
        demand, capacity = [2, 1], [2, 2, 3]
        # For fixed opening decisions this integer-data transport polytope has
        # an integral optimum. Exhaustive scalar allocation checks are independent
        # of the constraint matrix and the MILP solver.
        for case in range(5):
            costs = rng.integers(0, 8, size=(3, 2)).tolist()
            fixed = rng.integers(0, 6, size=3).tolist()
            best = float("inf")
            for opened in product((0, 1), repeat=3):
                for flat in product(range(3), range(2), range(3), range(2), range(3), range(2)):
                    flow = [flat[0:2], flat[2:4], flat[4:6]]
                    if any(sum(flow[i][j] for i in range(3)) != demand[j] for j in range(2)):
                        continue
                    if any(sum(flow[i]) > capacity[i] * opened[i] for i in range(3)):
                        continue
                    value = sum(fixed[i] * opened[i] for i in range(3))
                    value += sum(costs[i][j] * flow[i][j] for i in range(3) for j in range(2))
                    best = min(best, value)
            with self.subTest(case=case):
                result = models.solve_facility_allocation_milp(costs, demand, capacity, fixed)
                self.assertAlmostEqual(result["objective_value"], best)

    def test_zero_demand_and_infeasible_demand(self):
        result = models.solve_facility_allocation_milp([[2]], [0], [3], [5])
        self.assertAlmostEqual(result["objective_value"], 0)
        self.assertEqual(result["opened_facilities"], [])
        with self.assertRaisesRegex(RuntimeError, "No accepted optimum"):
            models.solve_facility_allocation_milp([[2]], [4], [3], [5])

    def test_independent_checks_reject_bad_solver_outputs(self):
        for x, objective, error in (([0, 1], 3, "demand"), ([1, 1], 0, "objective"), ([1, 0.5], 3.5, "integrality")):
            fake = SimpleNamespace(success=True, status=0, x=np.array(x, dtype=float), fun=objective)
            with self.subTest(error=error), patch("scipy.optimize.milp", return_value=fake):
                with self.assertRaisesRegex(RuntimeError, error):
                    models.solve_facility_allocation_milp([[2]], [1], [2], [3])


if __name__ == "__main__":
    unittest.main()

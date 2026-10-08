"""Reusable baselines adapted from cumcm-skills; see THIRD_PARTY_NOTICES.txt.

No data splitting, imputation, installation, or implicit output files.
Inputs must already have the intended units, time ordering and information set.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np


def _array(value, ndim, name):
    if np.iscomplexobj(value):
        raise ValueError(f"{name} must be real-valued")
    result = np.asarray(value, dtype=float)
    if result.ndim != ndim or result.size == 0 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a nonempty finite {ndim}-D array")
    return result


def _metrics(actual, predicted):
    predicted = _array(predicted, 1, "predictions")
    if actual.shape != predicted.shape:
        raise ValueError("Prediction and target shapes differ")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        error = actual - predicted
        sse = float(error @ error)
        centered = actual - actual.mean()
        sst = float(centered @ centered)
        return {"mae": float(np.mean(np.abs(error))),
                "rmse": float(np.sqrt(sse / len(actual))),
                "r2": None if len(actual) < 2 or sst == 0 else float(1 - sse / sst)}


def _finish(result, output_dir, filename):
    # Serialization also rejects any non-finite computed values.
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / filename).open("x", encoding="utf-8") as stream:
            stream.write(payload + "\n")
    return result


def run_regression_baselines(X_train, y_train, X_test, y_test, output_dir=None):
    """Mean predictor and intercept OLS; fit only training rows, score test rows.

    X arrays are (rows, features), y arrays are (rows,). Constant/singleton test
    targets have r2=None. Rank deficiency is reported, not silently concealed.
    """
    train = _array(X_train, 2, "X_train")
    test = _array(X_test, 2, "X_test")
    target = _array(y_train, 1, "y_train")
    actual = _array(y_test, 1, "y_test")
    if len(train) != len(target) or len(test) != len(actual) or train.shape[1] != test.shape[1]:
        raise ValueError("Training/test row counts or feature counts do not match")
    design = np.column_stack((np.ones(len(train)), train))
    coefficients, _, rank, singular = np.linalg.lstsq(design, target, rcond=None)
    mean_prediction = np.full(len(actual), target.mean(), dtype=float)
    linear_prediction = np.column_stack((np.ones(len(test)), test)) @ coefficients
    result = [
        {"model": "Mean_Baseline", "predictions": mean_prediction.tolist(),
         **_metrics(actual, mean_prediction)},
        {"model": "OLS_Linear_Regression", "predictions": linear_prediction.tolist(),
         **_metrics(actual, linear_prediction), "intercept": float(coefficients[0]),
         "coefficients": coefficients[1:].tolist(), "design_rank": int(rank),
         "design_columns": int(design.shape[1]), "singular_values": singular.tolist(),
         "full_column_rank": bool(rank == design.shape[1])},
    ]
    return _finish(result, output_dir, "regression_baselines.json")


def run_time_series_baselines(train_series, test_series, *, protocol, window=3, output_dir=None):
    """Persistence and trailing-window-mean forecasts with explicit information use.

    fixed_origin: forecast every test row using only the end of training data.
    rolling_one_step: forecast a row, then reveal its observation for the next row.
    Each row is one consecutive time step; window must fit in training history.
    """
    train = _array(train_series, 1, "train_series")
    actual = _array(test_series, 1, "test_series")
    if protocol not in {"fixed_origin", "rolling_one_step"}:
        raise ValueError("protocol must be fixed_origin or rolling_one_step")
    if isinstance(window, (bool, np.bool_)) or not isinstance(window, (int, np.integer)) or not 1 <= window <= len(train):
        raise ValueError("window must be an integer from 1 to the training length")
    if protocol == "fixed_origin":
        naive = np.full(len(actual), train[-1], dtype=float)
        moving = np.full(len(actual), train[-window:].mean(), dtype=float)
    else:
        history = train.tolist()
        naive, moving = [], []
        for observed in actual:
            naive.append(history[-1])
            moving.append(float(np.mean(history[-window:])))
            history.append(float(observed))
        naive, moving = np.asarray(naive), np.asarray(moving)
    result = []
    for name, predicted in (("Naive_Persistence", naive), (f"Moving_Average_{window}", moving)):
        result.append({"model": name, "protocol": protocol, "test_steps": len(actual),
                       "forecast_horizons": list(range(1, len(actual) + 1)) if protocol == "fixed_origin" else [1] * len(actual),
                       "window": int(window) if name.startswith("Moving") else 1,
                       "predictions": predicted.tolist(), **_metrics(actual, predicted)})
    return _finish(result, output_dir, "timeseries_baselines.json")


def solve_facility_allocation_milp(cost_matrix, demand_vec, capacity_vec, fixed_costs,
                                   output_dir=None, *, time_limit=60.0, atol=1e-7, rtol=1e-8):
    """Capacitated facility opening with splittable, continuous demand allocation.

    costs[i,j] are per-unit transport costs; fixed[i] is an opening cost.
    Every demand must be served exactly. No unmet demand, arcs restrictions,
    indivisible customers, transport capacities or time windows are modeled.
    Non-optimal termination raises instead of returning an accepted baseline.
    """
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    costs = _array(cost_matrix, 2, "cost_matrix")
    demand = _array(demand_vec, 1, "demand_vec")
    capacity = _array(capacity_vec, 1, "capacity_vec")
    fixed = _array(fixed_costs, 1, "fixed_costs")
    n, m = costs.shape
    if len(demand) != m or len(capacity) != n or len(fixed) != n:
        raise ValueError("Facilities/customers dimensions do not match")
    if np.any(demand < 0) or np.any(capacity < 0):
        raise ValueError("Demand and capacity must be nonnegative")
    if not all(np.isfinite(v) for v in (time_limit, atol, rtol)) or time_limit <= 0 or atol <= 0 or rtol < 0:
        raise ValueError("time_limit and atol must be positive; rtol must be nonnegative")
    count = n * m
    flow_cols = np.arange(count)
    facility_rows = np.repeat(np.arange(n), m)
    rows = np.concatenate((np.tile(np.arange(m), n), m + facility_rows, m + np.arange(n)))
    cols = np.concatenate((flow_cols, flow_cols, count + np.arange(n)))
    values = np.concatenate((np.ones(2 * count), -capacity))
    matrix = coo_matrix((values, (rows, cols)), shape=(m + n, count + n)).tocsc()
    constraint = LinearConstraint(matrix, np.r_[demand, np.full(n, -np.inf)], np.r_[demand, np.zeros(n)])
    result = milp(np.r_[costs.ravel(), fixed], integrality=np.r_[np.zeros(count), np.ones(n)],
                  bounds=Bounds(np.zeros(count + n), np.r_[np.full(count, np.inf), np.ones(n)]),
                  constraints=constraint, options={"time_limit": float(time_limit), "mip_rel_gap": 0.0})
    if not result.success or result.status != 0 or result.x is None or result.fun is None:
        raise RuntimeError(f"No accepted optimum: status={result.status}; {result.message}")
    solution = _array(result.x, 1, "solver solution")
    if len(solution) != count + n or not np.isfinite(result.fun):
        raise RuntimeError("Invalid solver result")
    flow = solution[:count].reshape(n, m)
    opened_raw = solution[count:]
    opened = np.rint(opened_raw)
    integrality_error = float(np.max(np.abs(opened_raw - opened)))
    if integrality_error > 1e-7 or np.any(opened < 0) or np.any(opened > 1) or np.any(flow < -atol):
        raise RuntimeError("Independent check failed: variable bounds/integrality")
    # Recompute semantic constraints directly, without the solver's matrix.
    demand_errors, capacity_excesses = [], []
    for j in range(m):
        supplied = sum(float(flow[i, j]) for i in range(n))
        error = abs(supplied - float(demand[j]))
        demand_errors.append(error)
        if error > atol + rtol * abs(demand[j]):
            raise RuntimeError("Independent check failed: unmet or excess demand")
    for i in range(n):
        used = sum(float(flow[i, j]) for j in range(m))
        limit = float(capacity[i] * opened[i])
        excess = max(0.0, used - limit)
        capacity_excesses.append(excess)
        if excess > atol + rtol * abs(limit):
            raise RuntimeError("Independent check failed: facility capacity/opening")
    objective = sum(float(costs[i, j] * flow[i, j]) for i in range(n) for j in range(m))
    objective += sum(float(fixed[i] * opened[i]) for i in range(n))
    objective_error = abs(objective - float(result.fun))
    if objective_error > atol + rtol * max(abs(objective), abs(result.fun)):
        raise RuntimeError("Independent check failed: objective recomputation")
    data = {"status": "optimal_within_solver_tolerances", "solver_used": "scipy.optimize.milp/HiGHS",
            "objective_value": float(objective), "solver_objective": float(result.fun),
            "opened_facilities": [int(i) for i in np.flatnonzero(opened)],
            "open_decisions": opened.astype(int).tolist(), "allocation": flow.tolist(),
            "mip_gap": None if result.mip_gap is None else float(result.mip_gap),
            "dual_bound": None if result.mip_dual_bound is None else float(result.mip_dual_bound),
            "checks": {"demand_max_abs_error": max(demand_errors), "capacity_max_excess": max(capacity_excesses),
                       "integrality_max_abs_error": integrality_error, "objective_abs_error": objective_error,
                       "atol": float(atol), "rtol": float(rtol)}}
    return _finish(data, output_dir, "milp_solution.json")

"""Splines, vecinos ponderados y boosting de árboles con NumPy y pandas."""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd


def _log_target(y, rows: int) -> np.ndarray:
    target = np.asarray(y, dtype=float)
    if rows == 0 or target.shape != (rows,) or not np.isfinite(target).all() or (target <= 0).any():
        raise ValueError("Cada fila de entrenamiento requiere un precio positivo y finito.")
    return np.log1p(target)


def _to_prices(prediction, target_bounds) -> np.ndarray:
    low, high = target_bounds
    safe_max = np.nextafter(np.log(np.finfo(float).max), 0)
    return np.expm1(np.clip(prediction, low, min(high, safe_max)))


@dataclass(frozen=True)
class NumericColumn:
    name: str
    center: float
    scale: float
    lower: float
    upper: float
    knots: np.ndarray
    has_missing: bool

    @classmethod
    def fit(cls, name: str, values: pd.Series, *, n_knots: int = 3) -> "NumericColumn":
        numeric = values.to_numpy(dtype=float, na_value=np.nan)
        observed = numeric[np.isfinite(numeric)]
        if len(observed):
            lower, q1, median, q3, upper = np.quantile(observed, [0.01, 0.25, 0.5, 0.75, 0.99])
            scale = q3 - q1 or np.std(observed) or 1.0
            if n_knots == 3:
                positions = np.array([q1, median, q3])
            else:
                quantiles = np.linspace(0, 1, n_knots + 2)[1:-1]
                positions = np.quantile(observed, quantiles)
            knots = np.unique((positions - median) / scale)
            return cls(name, median, scale, lower, upper, knots, len(observed) < len(numeric))
        return cls(name, 0.0, 1.0, 0.0, 0.0, np.array([]), True)

    def transform(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        values = frame[self.name].to_numpy(dtype=float, na_value=np.nan)
        missing = ~np.isfinite(values)
        filled = np.where(missing, self.center, values)
        standardized = (np.clip(filled, self.lower, self.upper) - self.center) / self.scale
        return standardized, missing


class FeatureEncoder:
    """Aprende medidas resistentes a valores extremos y niveles categóricos en train."""

    def __init__(self, frame: pd.DataFrame, min_category_count: int, *, n_knots: int = 3):
        self.columns = frame.columns.tolist()
        if not self.columns or not frame.columns.is_unique:
            raise ValueError("Se requieren nombres únicos para las variables de entrada.")
        numeric = frame.select_dtypes(include="number").columns
        self.numeric = [NumericColumn.fit(name, frame[name], n_knots=n_knots) for name in numeric]
        self.categories = {}
        for name in self.columns:
            if name not in numeric:
                counts = self._labels(frame[name]).value_counts()
                self.categories[name] = sorted(counts[counts >= min_category_count].index)

    @staticmethod
    def _labels(values: pd.Series) -> pd.Series:
        return values.astype("string").fillna("__sin_informacion__")

    def _check(self, frame: pd.DataFrame) -> None:
        missing = set(self.columns) - set(frame.columns)
        if missing:
            raise ValueError(f"Faltan variables de entrada: {sorted(missing)}")

    def _categorical_codes(self, frame: pd.DataFrame):
        for name, categories in self.categories.items():
            labels = self._labels(frame[name])
            known_labels = labels.where(labels.isin(categories))
            codes = pd.Categorical(known_labels, categories=categories).codes
            yield name, categories, codes

    def spline_matrix(self, frame: pd.DataFrame) -> np.ndarray:
        self._check(frame)
        columns = [np.ones((len(frame), 1))]
        for variable in self.numeric:
            values, missing = variable.transform(frame)
            columns.append(values[:, None])
            columns.append(np.maximum(0, values[:, None] - variable.knots))
            if variable.has_missing:
                columns.append(missing[:, None])
        for _, levels, codes in self._categorical_codes(frame):
            columns.append(codes[:, None] == np.arange(len(levels)))
        return np.column_stack(columns)

    def distance_matrix(self, frame: pd.DataFrame) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        self._check(frame)
        columns = []
        for variable in self.numeric:
            values, missing = variable.transform(frame)
            columns.append(np.clip(values, -3, 3))
            if variable.has_missing:
                columns.append(missing)
        numeric = np.column_stack(columns) if columns else np.zeros((len(frame), 0))
        categories = {name: codes for name, _, codes in self._categorical_codes(frame)}
        return numeric, categories


class SplineAdditiveRegressor:
    """Efectos no lineales por variable y regularización de categorías poco frecuentes."""

    def __init__(self, penalty: float = 8.0, *, n_knots: int = 3):
        if not np.isfinite(penalty) or penalty <= 0:
            raise ValueError("La penalización debe ser positiva y finita.")
        if isinstance(n_knots, bool) or not isinstance(n_knots, (int, np.integer)) or n_knots < 0:
            raise ValueError("El número de nudos debe ser un entero no negativo.")
        self.penalty = penalty
        self.n_knots = int(n_knots)

    def fit(self, X: pd.DataFrame, y) -> "SplineAdditiveRegressor":
        target = _log_target(y, len(X))
        # Los modelos anteriores al parámetro usaban los tres cuartiles interiores.
        encoder = FeatureEncoder(X, min_category_count=2, n_knots=getattr(self, "n_knots", 3))
        matrix = encoder.spline_matrix(X)
        gram = matrix.T @ matrix
        gram.flat[:: len(gram) + 1] += self.penalty
        gram[0, 0] -= self.penalty  # El intercepto no se penaliza.
        self.coefficients_ = np.linalg.solve(gram, matrix.T @ target)
        self.encoder_ = encoder
        self.bounds_ = (target.min(), target.max())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return _to_prices(self.encoder_.spline_matrix(X) @ self.coefficients_, self.bounds_)


class WeightedNeighborRegressor:
    """Promedia precios logarítmicos cercanos con distancia numérica y categórica."""

    def __init__(self, neighbors: int = 15, artist_weight: float = 8.0):
        if neighbors < 1 or not np.isfinite(artist_weight) or artist_weight < 0:
            raise ValueError("Se requiere al menos un vecino y peso no negativo para el artista.")
        self.neighbors = neighbors
        self.artist_weight = artist_weight

    def fit(self, X: pd.DataFrame, y) -> "WeightedNeighborRegressor":
        target = _log_target(y, len(X))
        encoder = FeatureEncoder(X, min_category_count=1)
        self.numeric_, self.categories_ = encoder.distance_matrix(X)
        self.numeric_squared_norm_ = np.square(self.numeric_).sum(axis=1)
        self.encoder_ = encoder
        self.target_ = target
        self.bounds_ = (target.min(), target.max())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        numeric, categories = self.encoder_.distance_matrix(X)
        k = min(self.neighbors, len(self.target_))
        prediction = np.empty(len(X))
        for start in range(0, len(X), 128):
            batch = slice(start, start + 128)
            rows = numeric[batch]
            distance = np.maximum(
                np.square(rows).sum(axis=1, keepdims=True) + self.numeric_squared_norm_
                - 2 * rows @ self.numeric_.T,
                0,
            )
            for name, codes in categories.items():
                mismatched = codes[batch, None] != self.categories_[name]
                distance += mismatched * (self.artist_weight if name == "artista" else 1.5)
            indexes = np.argsort(distance, axis=1, kind="stable")[:, :k]
            closest = np.take_along_axis(distance, indexes, axis=1)
            weights = 1.0 / (np.sqrt(closest) + 0.1)
            prediction[batch] = (weights * self.target_[indexes]).sum(axis=1) / weights.sum(axis=1)
        return _to_prices(prediction, self.bounds_)


@dataclass(frozen=True)
class _BoostingSplit:
    feature: int | str
    threshold: float | int

    def mask(self, numeric: np.ndarray, categories: dict[str, np.ndarray]) -> np.ndarray:
        if isinstance(self.feature, int):
            return numeric[:, self.feature] <= self.threshold
        return categories[self.feature] == self.threshold


@dataclass(frozen=True)
class _BoostingNode:
    adjustment: float
    split: int | None = None
    left: "_BoostingNode | None" = None
    right: "_BoostingNode | None" = None

    def predict(self, conditions: np.ndarray) -> np.ndarray:
        if self.split is None:
            return np.full(len(conditions), self.adjustment)
        return np.where(
            conditions[:, self.split], self.left.predict(conditions), self.right.predict(conditions)
        )


class GradientTreeBoostingRegressor:
    """Árboles de profundidad 2 ajustados a los residuos de log1p(precio)."""

    def __init__(self, rounds: int = 100, learning_rate: float = 0.08, min_leaf: int = 12):
        if rounds < 1 or min_leaf < 1 or not 0 < learning_rate <= 1:
            raise ValueError("Rondas y mínimo por hoja deben ser positivos, con tasa en (0, 1].")
        self.rounds = rounds
        self.learning_rate = learning_rate
        self.min_leaf = min_leaf

    def _split_rules(self, numeric: np.ndarray, categories: dict[str, np.ndarray]) -> list:
        rules = []
        for index, values in enumerate(numeric.T):
            p = np.unique(np.quantile(values, np.linspace(0.1, 0.9, 9)))
            rules.extend(_BoostingSplit(index, float(threshold)) for threshold in p)
        for name, codes in categories.items():
            levels, counts = np.unique(codes, return_counts=True)
            for code, count in zip(levels, counts):
                if self.min_leaf <= count <= len(codes) - self.min_leaf:
                    rules.append(_BoostingSplit(name, int(code)))
        # Un corte que ya incumple el mínimo en la raíz no vale en ningún hijo.
        valid = []
        for rule in rules:
            count = rule.mask(numeric, categories).sum()
            if self.min_leaf <= count <= len(numeric) - self.min_leaf:
                valid.append(rule)
        return valid

    @staticmethod
    def _conditions(numeric, categories, rules) -> np.ndarray:
        if not rules:
            return np.empty((len(numeric), 0), dtype=bool)
        return np.column_stack([rule.mask(numeric, categories) for rule in rules])

    def _grow(self, conditions, residual, rows, depth) -> _BoostingNode:
        local = residual[rows]
        total = local.sum()
        value = float(local.mean())
        if depth == 0 or len(local) < 2 * self.min_leaf:
            return _BoostingNode(value)
        local_conditions = conditions[rows]
        counts = local_conditions.sum(axis=0)
        right_counts = len(local) - counts
        valid = np.flatnonzero((counts >= self.min_leaf) & (right_counts >= self.min_leaf))
        if not len(valid):
            return _BoostingNode(value)
        sums = np.einsum("ij,i->j", local_conditions, local)[valid]
        scores = sums ** 2 / counts[valid] + (total - sums) ** 2 / right_counts[valid]
        best = int(np.argmax(scores))
        if scores[best] <= total ** 2 / len(local) + 1e-12:
            return _BoostingNode(value)
        split = int(valid[best])
        mask = local_conditions[:, split]
        left = self._grow(conditions, residual, rows[mask], depth - 1)
        right = self._grow(conditions, residual, rows[~mask], depth - 1)
        return _BoostingNode(value, split, left, right)

    def fit(self, X: pd.DataFrame, y) -> "GradientTreeBoostingRegressor":
        target = _log_target(y, len(X))
        self.encoder_ = FeatureEncoder(X, min_category_count=1)
        numeric, categories = self.encoder_.distance_matrix(X)
        self.rules_ = self._split_rules(numeric, categories)
        conditions = self._conditions(numeric, categories, self.rules_)
        self.initial_ = float(target.mean())
        prediction = np.full(len(X), self.initial_)
        rows = np.arange(len(X))
        self.trees_ = []
        for _ in range(self.rounds):
            tree = self._grow(conditions, target - prediction, rows, depth=2)
            if tree.split is None:
                break
            prediction += self.learning_rate * tree.predict(conditions)
            self.trees_.append(tree)
        self.bounds_ = (target.min(), target.max())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        numeric, categories = self.encoder_.distance_matrix(X)
        conditions = self._conditions(numeric, categories, self.rules_)
        prediction = np.full(len(X), self.initial_)
        for tree in self.trees_:
            prediction += self.learning_rate * tree.predict(conditions)
        return _to_prices(prediction, self.bounds_)


def candidate_factories(seed: int = 42, quick: bool = False) -> dict[str, Callable]:
    """Modelos deterministas. El modo rápido solo reduce las rondas de boosting."""
    return {
        "spline_additive_log": SplineAdditiveRegressor,
        "knn_weighted_log": WeightedNeighborRegressor,
        "boosting_numpy_log": lambda: GradientTreeBoostingRegressor(rounds=30 if quick else 100),
    }

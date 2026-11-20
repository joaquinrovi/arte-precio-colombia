import numpy as np


def regression_metrics(y_true, y_pred) -> dict:
    truth = np.asarray(y_true, dtype=float)
    prediction = np.asarray(y_pred, dtype=float)
    if truth.shape != prediction.shape or not truth.size:
        raise ValueError("Target y predicción deben tener la misma forma y no estar vacíos.")
    if not np.isfinite(truth).all() or not np.isfinite(prediction).all():
        raise ValueError("Las métricas requieren valores finitos.")
    if (truth <= 0).any():
        raise ValueError("El precio observado debe ser positivo.")
    clipped = np.maximum(0, prediction)
    errors = clipped - truth
    absolute_errors = np.abs(errors)
    squared_errors = np.square(errors)
    total_squares = np.square(truth - truth.mean()).sum()
    return {
        "n": int(truth.size),
        "mae_cop": float(absolute_errors.mean()),
        "median_absolute_error_cop": float(np.median(absolute_errors)),
        "rmse_cop": float(np.sqrt(squared_errors.mean())),
        "rmsle": float(np.sqrt(np.mean((np.log1p(clipped) - np.log1p(truth)) ** 2))),
        "r2": float(1 - squared_errors.sum() / total_squares) if total_squares else None,
        "median_absolute_percentage_error_pct": float(100 * np.median(absolute_errors / truth)),
        "within_25_pct": float(100 * np.mean(absolute_errors <= 0.25 * truth)),
        "negative_predictions_clipped": int((prediction < 0).sum()),
    }

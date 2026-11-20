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
    return {
        "n": int(truth.size),
        "mae_cop": float(np.mean(np.abs(errors))),
        "median_absolute_error_cop": float(np.median(np.abs(errors))),
        "rmse_cop": float(np.sqrt(np.mean(errors ** 2))),
        "rmsle": float(np.sqrt(np.mean((np.log1p(clipped) - np.log1p(truth)) ** 2))),
        "negative_predictions_clipped": int((prediction < 0).sum()),
    }

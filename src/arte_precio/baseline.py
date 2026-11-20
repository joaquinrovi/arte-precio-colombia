import numpy as np
import pandas as pd


class MedianBaseline:
    """Referencia global o mediana por artista suavizada, ajustada solo en train."""

    def __init__(self, by_artist: bool = False, prior_weight: float = 5.0):
        if prior_weight < 0:
            raise ValueError("prior_weight no puede ser negativo.")
        self.by_artist = by_artist
        self.prior_weight = prior_weight

    def fit(self, frame: pd.DataFrame):
        target = pd.to_numeric(frame["precio_venta_cop"], errors="coerce")
        if target.isna().any() or (target <= 0).any() or not np.isfinite(target).all():
            raise ValueError("El baseline requiere precios positivos y finitos.")
        if frame.empty:
            raise ValueError("No hay filas para entrenar el baseline.")
        self.global_ = float(target.median())
        self.artists_ = {}
        if self.by_artist:
            temporary = pd.DataFrame({"artist": frame["artista_id"], "target": target})
            for artist, group in temporary.dropna(subset=["artist"]).groupby("artist"):
                n = len(group)
                self.artists_[str(artist)] = float(
                    (n * group["target"].median() + self.prior_weight * self.global_)
                    / (n + self.prior_weight)
                )
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if not hasattr(self, "global_"):
            raise ValueError("Ajusta el baseline con fit antes de predecir.")
        if not self.by_artist:
            return np.full(len(frame), self.global_, dtype=float)
        return frame["artista_id"].map(
            lambda name: self.artists_.get(str(name), self.global_)
        ).to_numpy(dtype=float)

    def to_dict(self) -> dict:
        return {"kind": "median_baseline", "by_artist": self.by_artist,
                "prior_weight": self.prior_weight, "global_median_cop": self.global_,
                "artist_predictions_cop": self.artists_}

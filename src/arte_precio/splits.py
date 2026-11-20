import pandas as pd


def temporal_split(
    frame: pd.DataFrame, train_end: str = "2024-12-31", validation_end: str = "2025-12-31"
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_cutoff, valid_cutoff = pd.Timestamp(train_end), pd.Timestamp(validation_end)
    if train_cutoff >= valid_cutoff:
        raise ValueError("train_end debe ser anterior a validation_end.")
    dates = pd.to_datetime(frame["fecha_subasta"], errors="coerce").dt.normalize()
    if dates.isna().any():
        raise ValueError("No se puede dividir con fechas ausentes o inválidas.")
    parts = (
        frame.loc[dates <= train_cutoff].copy(),
        frame.loc[(dates > train_cutoff) & (dates <= valid_cutoff)].copy(),
        frame.loc[dates > valid_cutoff].copy(),
    )
    if any(p.empty for p in parts):
        raise ValueError("Cada partición necesita observaciones; ajusta los cortes temporales.")
    ids = [set(p["registro_id"]) for p in parts]
    if ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2]:
        raise ValueError("Se detectó solapamiento de IDs entre particiones.")
    return parts


def split_summary(train: pd.DataFrame, valid: pd.DataFrame, test: pd.DataFrame) -> dict:
    known = set(train["artista_id"].dropna())
    result = {}
    for name, frame in [("train", train), ("validation", valid), ("test_reserved", test)]:
        dates = pd.to_datetime(frame["fecha_subasta"])
        result[name] = {
            "rows": len(frame), "auction_dates": dates.nunique(),
            "start": dates.min().date().isoformat(), "end": dates.max().date().isoformat(),
            "unseen_artist_rows": int((~frame["artista_id"].isin(known)).sum()),
        }
    return result

"""Evaluate saved predictions by season and named Sahel location."""

from __future__ import annotations

import argparse
import json

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_fscore_support, roc_auc_score


LOCATIONS = {
    "Niamey": (13.51, 2.11),
    "Sokoto": (13.06, 5.24),
    "Kano": (12.00, 8.52),
    "Maiduguri": (11.85, 13.16),
    "Agadez": (16.97, 7.99),
    "N'Djamena": (12.13, 15.06),
    "Bamako": (12.64, -8.00),
    "Timbuktu": (16.77, -3.01),
    "Ouagadougou": (12.36, -1.48),
    "Dakar (coastal)": (14.69, -17.44),
    "Nouakchott (coastal)": (18.09, -15.98),
}

SEASONS = {
    "dry": {11, 12, 1, 2, 3},
    "dry_to_wet_transition": {4, 5, 6},
    "wet": {7, 8, 9},
    "wet_to_dry_transition": {10},
}


def metrics(y_true: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict:
    if len(y_true) == 0:
        return {"samples": 0}
    predicted = probabilities >= threshold
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, predicted, average="binary", zero_division=0
    )
    both_classes = len(np.unique(y_true)) == 2
    return {
        "samples": int(len(y_true)),
        "positive_rate": round(float(np.mean(y_true)), 6),
        "precision": round(float(precision), 6),
        "recall": round(float(recall), 6),
        "f1": round(float(f1), 6),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 6) if both_classes else None,
        "pr_auc": round(float(average_precision_score(y_true, probabilities)), 6) if both_classes else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="NPZ containing y_test, probs, sample_dates, lat, and lon")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--radius", type=float, default=0.5, help="Location slice radius in degrees")
    parser.add_argument("--output", default="failure-slice-results.json")
    args = parser.parse_args()

    archive = np.load(args.archive)
    required = {"y_test", "probs", "sample_dates", "lat", "lon"}
    missing = required.difference(archive.files)
    if missing:
        raise SystemExit(f"Archive is missing fields: {', '.join(sorted(missing))}")

    y_true = np.asarray(archive["y_test"]).astype(int)
    probabilities = np.asarray(archive["probs"]).astype(float)
    dates = np.asarray(archive["sample_dates"], dtype="datetime64[D]")
    latitudes = np.asarray(archive["lat"]).astype(float)
    longitudes = np.asarray(archive["lon"]).astype(float)
    lengths = {len(y_true), len(probabilities), len(dates), len(latitudes), len(longitudes)}
    if len(lengths) != 1:
        raise SystemExit("All archive arrays must have the same number of samples")

    months = (dates.astype("datetime64[M]").astype(int) % 12) + 1
    report = {
        "threshold": args.threshold,
        "overall": metrics(y_true, probabilities, args.threshold),
        "seasons": {},
        "locations": {},
    }
    for season, members in SEASONS.items():
        mask = np.isin(months, list(members))
        report["seasons"][season] = metrics(y_true[mask], probabilities[mask], args.threshold)

    for name, (lat, lon) in LOCATIONS.items():
        mask = (np.abs(latitudes - lat) <= args.radius) & (np.abs(longitudes - lon) <= args.radius)
        report["locations"][name] = metrics(y_true[mask], probabilities[mask], args.threshold)

    rendered = json.dumps(report, indent=2)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()

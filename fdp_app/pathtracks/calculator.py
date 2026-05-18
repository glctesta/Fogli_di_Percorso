"""Funzioni pure per il calcolo dei rimborsi."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


def _round_to_eur(value: float) -> float:
    """Arrotonda a 2 decimali con ROUND_HALF_UP."""
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(d)


def compute_fuel_reimbursement(
    *,
    road_km_one_way: float,
    number_of_trips: int,
    avg_consumption_km_l: float,
    avg_fuel_price_eur_l: float,
) -> float:
    if road_km_one_way < 0:
        raise ValueError("road_km_one_way non puo' essere negativo")
    if number_of_trips < 0:
        raise ValueError("number_of_trips non puo' essere negativo")
    if avg_consumption_km_l <= 0:
        raise ValueError(
            f"avg_consumption_km_l (consumo) deve essere > 0, ricevuto {avg_consumption_km_l}"
        )
    if avg_fuel_price_eur_l < 0:
        raise ValueError("avg_fuel_price_eur_l non puo' essere negativo")
    if number_of_trips == 0:
        return 0.0
    liters_needed = (road_km_one_way * 2 * number_of_trips) / avg_consumption_km_l
    eur = liters_needed * avg_fuel_price_eur_l
    return _round_to_eur(eur)


def compute_taxi_reimbursement(receipt_amounts: Iterable[float]) -> float:
    total = 0.0
    for amount in receipt_amounts:
        if amount < 0:
            raise ValueError(f"importo ricevuta negativo non ammesso: {amount}")
        total += amount
    return _round_to_eur(total)

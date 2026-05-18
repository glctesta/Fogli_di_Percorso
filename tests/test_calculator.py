"""Test del calcolatore di rimborso."""
from __future__ import annotations

import pytest

from fdp_app.pathtracks.calculator import (
    compute_fuel_reimbursement,
    compute_taxi_reimbursement,
)


def test_fuel_basic_case():
    # 10 km one-way * 2 (A/R) * 20 viaggi / 15 km-l * 1.700 eur/l = 45.33...
    amount = compute_fuel_reimbursement(
        road_km_one_way=10.0,
        number_of_trips=20,
        avg_consumption_km_l=15.0,
        avg_fuel_price_eur_l=1.700,
    )
    assert amount == pytest.approx(45.33, abs=0.01)


def test_fuel_zero_trips_returns_zero():
    amount = compute_fuel_reimbursement(
        road_km_one_way=10.0,
        number_of_trips=0,
        avg_consumption_km_l=15.0,
        avg_fuel_price_eur_l=1.700,
    )
    assert amount == 0.0


def test_fuel_rounded_to_two_decimals():
    amount = compute_fuel_reimbursement(
        road_km_one_way=7.777,
        number_of_trips=3,
        avg_consumption_km_l=12.5,
        avg_fuel_price_eur_l=1.852,
    )
    assert amount == pytest.approx(6.91, abs=0.01)


def test_fuel_raises_on_zero_consumption():
    with pytest.raises(ValueError, match="consumo"):
        compute_fuel_reimbursement(
            road_km_one_way=10.0,
            number_of_trips=20,
            avg_consumption_km_l=0.0,
            avg_fuel_price_eur_l=1.7,
        )


def test_fuel_raises_on_negative_inputs():
    with pytest.raises(ValueError):
        compute_fuel_reimbursement(
            road_km_one_way=-1.0,
            number_of_trips=10,
            avg_consumption_km_l=15.0,
            avg_fuel_price_eur_l=1.7,
        )


def test_taxi_sums_amounts():
    amount = compute_taxi_reimbursement([12.50, 8.30, 15.00])
    assert amount == pytest.approx(35.80, abs=0.01)


def test_taxi_empty_list_returns_zero():
    amount = compute_taxi_reimbursement([])
    assert amount == 0.0


def test_taxi_raises_on_negative_amount():
    with pytest.raises(ValueError, match="negat"):
        compute_taxi_reimbursement([10.0, -5.0])


def test_taxi_rounded_to_two_decimals():
    amount = compute_taxi_reimbursement([3.333, 2.222, 1.111])
    assert amount == pytest.approx(6.67, abs=0.01)

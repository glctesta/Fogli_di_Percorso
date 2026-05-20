"""Test del client BnrRateClient (BNR + cursbnr fallback)."""
from __future__ import annotations

import pytest
import responses

from fdp_app.pathtracks.bnr_client import (
    BnrRateClient,
    BnrRateUnavailable,
    BNR_XML_URL,
    CURSBNR_API_URL,
)


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


def test_bnr_xml_success(mocked_responses):
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<DataSet xmlns="http://www.bnr.ro/xsd">
    <Header><Publisher>National Bank of Romania</Publisher></Header>
    <Body>
        <Subject>Reference rates</Subject>
        <OrigCurrency>RON</OrigCurrency>
        <Cube date="2026-05-20">
            <Rate currency="USD">4.5876</Rate>
            <Rate currency="EUR">4.9756</Rate>
            <Rate currency="HUF" multiplier="100">1.2345</Rate>
        </Cube>
    </Body>
</DataSet>"""
    mocked_responses.get(BNR_XML_URL, body=xml, status=200,
                          content_type="application/xml")
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert rate == pytest.approx(4.9756)
    assert source == "BNR"


def test_bnr_xml_handles_multiplier(mocked_responses):
    xml = b"""<?xml version="1.0"?>
<DataSet xmlns="http://www.bnr.ro/xsd">
    <Body><Cube date="2026-05-20">
        <Rate currency="EUR" multiplier="2">9.9512</Rate>
    </Cube></Body>
</DataSet>"""
    mocked_responses.get(BNR_XML_URL, body=xml, status=200)
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    # 9.9512 / 2 = 4.9756
    assert rate == pytest.approx(4.9756, abs=1e-4)


def test_bnr_fail_cursbnr_success(mocked_responses):
    mocked_responses.get(BNR_XML_URL, status=503)
    mocked_responses.get(
        CURSBNR_API_URL,
        json={"rates": {"EUR": 4.97}},
        status=200,
    )
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert rate == pytest.approx(4.97)
    assert source == "CURSBNR"


def test_bnr_fail_cursbnr_alternate_format(mocked_responses):
    """cursbnr may return a different JSON shape with 'EUR' at top level."""
    mocked_responses.get(BNR_XML_URL, status=503)
    mocked_responses.get(
        CURSBNR_API_URL,
        json={"EUR": 4.95, "USD": 4.65},
        status=200,
    )
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert rate == pytest.approx(4.95)
    assert source == "CURSBNR"


def test_both_fail_raises(mocked_responses):
    mocked_responses.get(BNR_XML_URL, status=503)
    mocked_responses.get(CURSBNR_API_URL, status=500)
    client = BnrRateClient()
    with pytest.raises(BnrRateUnavailable):
        client.fetch_eur_to_ron()


def test_bnr_invalid_xml_falls_through_to_cursbnr(mocked_responses):
    mocked_responses.get(BNR_XML_URL, body=b"not xml", status=200)
    mocked_responses.get(
        CURSBNR_API_URL,
        json={"rates": {"EUR": 4.96}},
        status=200,
    )
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert rate == pytest.approx(4.96)
    assert source == "CURSBNR"


def test_bnr_xml_without_eur_falls_through(mocked_responses):
    xml = b"""<?xml version="1.0"?>
<DataSet xmlns="http://www.bnr.ro/xsd">
    <Body><Cube date="2026-05-20">
        <Rate currency="USD">4.58</Rate>
    </Cube></Body>
</DataSet>"""
    mocked_responses.get(BNR_XML_URL, body=xml, status=200)
    mocked_responses.get(
        CURSBNR_API_URL,
        json={"rates": {"EUR": 4.96}},
        status=200,
    )
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert source == "CURSBNR"


def test_timeout_fails_gracefully(mocked_responses):
    import requests
    def timeout_callback(req):
        raise requests.exceptions.Timeout()
    mocked_responses.add_callback(responses.GET, BNR_XML_URL,
                                    callback=lambda req: (504, {}, b""))
    mocked_responses.get(CURSBNR_API_URL,
                          json={"rates": {"EUR": 4.96}}, status=200)
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert source == "CURSBNR"

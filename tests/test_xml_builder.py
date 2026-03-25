"""
Tests for tonedef.xml_builder

All tests use synthetic in-memory data — no disk I/O required.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from tonedef.xml_builder import build_signal_chain_xml

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SCHEMA = {
    "Tweed Delight": {
        "component_id": 79000,
        "parameters": [
            {"param_id": "vb", "param_name": "Bright", "default_value": 0.5},
            {"param_id": "vo", "param_name": "Volume", "default_value": 0.5},
        ],
    },
    "Spring Reverb": {
        "component_id": 90000,
        "parameters": [
            {"param_id": "rv", "param_name": "Reverb", "default_value": 0.3},
        ],
    },
}

_COMPONENTS_ONE = [
    {
        "component_name": "Tweed Delight",
        "component_id": 79000,
        "parameters": {"vb": 0.64, "vo": 0.5},
    }
]

_COMPONENTS_TWO = [
    {
        "component_name": "Tweed Delight",
        "component_id": 79000,
        "parameters": {"vb": 0.64, "vo": 0.5},
    },
    {
        "component_name": "Spring Reverb",
        "component_id": 90000,
        "parameters": {"rv": 0.3},
    },
]


# ---------------------------------------------------------------------------
# Return type and basic structure
# ---------------------------------------------------------------------------


def test_build_signal_chain_xml_returns_bytes() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    assert isinstance(result, bytes)


def test_build_signal_chain_xml_is_parseable() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    assert root.tag == "non-fix-components"


def test_build_signal_chain_xml_empty_components() -> None:
    result = build_signal_chain_xml([], _SCHEMA)
    root = ET.fromstring(result)
    assert list(root) == []


# ---------------------------------------------------------------------------
# Component attributes
# ---------------------------------------------------------------------------


def test_build_signal_chain_xml_component_id() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    comp = root.find("component")
    assert comp is not None
    assert comp.get("id") == "79000"


def test_build_signal_chain_xml_component_name() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    comp = root.find("component")
    assert comp is not None
    assert comp.get("name") == "Tweed Delight"


def test_build_signal_chain_xml_component_has_uuid() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    comp = root.find("component")
    assert comp is not None
    assert comp.get("uuid") is not None
    assert len(comp.get("uuid", "")) > 0


def test_build_signal_chain_xml_each_call_generates_unique_uuids() -> None:
    r1 = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    r2 = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root1 = ET.fromstring(r1)
    root2 = ET.fromstring(r2)
    uuid1 = root1.find("component").get("uuid")  # type: ignore[union-attr]
    uuid2 = root2.find("component").get("uuid")  # type: ignore[union-attr]
    assert uuid1 != uuid2


# ---------------------------------------------------------------------------
# Parameter elements
# ---------------------------------------------------------------------------


def test_build_signal_chain_xml_parameter_count() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    params = root.findall(".//parameter")
    assert len(params) == 2


def test_build_signal_chain_xml_parameter_value_formatted() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    param = root.find(".//parameter[@id='vb']")
    assert param is not None
    assert param.get("value") == "0.640000"


def test_build_signal_chain_xml_parameter_name_from_schema() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    param = root.find(".//parameter[@id='vb']")
    assert param is not None
    assert param.get("name") == "Bright"


def test_build_signal_chain_xml_param_name_fallback_to_id() -> None:
    components = [
        {
            "component_name": "Unknown Widget",
            "component_id": 99999,
            "parameters": {"xx": 0.5},
        }
    ]
    result = build_signal_chain_xml(components, _SCHEMA)
    root = ET.fromstring(result)
    param = root.find(".//parameter[@id='xx']")
    assert param is not None
    assert param.get("name") == "xx"  # falls back to param_id


def test_build_signal_chain_xml_parameter_value_clamped_high() -> None:
    components = [
        {"component_name": "Tweed Delight", "component_id": 79000, "parameters": {"vb": 2.5}}
    ]
    result = build_signal_chain_xml(components, _SCHEMA)
    root = ET.fromstring(result)
    param = root.find(".//parameter[@id='vb']")
    assert param is not None
    assert float(param.get("value", "0")) == pytest.approx(1.0)


def test_build_signal_chain_xml_parameter_value_clamped_low() -> None:
    components = [
        {"component_name": "Tweed Delight", "component_id": 79000, "parameters": {"vb": -0.5}}
    ]
    result = build_signal_chain_xml(components, _SCHEMA)
    root = ET.fromstring(result)
    param = root.find(".//parameter[@id='vb']")
    assert param is not None
    assert float(param.get("value", "1")) == pytest.approx(0.0)


def test_build_signal_chain_xml_base_parameters_present() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    base = root.find(".//base-parameters")
    assert base is not None
    assert base.get("remote-max") == "1.000000"
    assert base.get("remote-min") == "0.000000"


# ---------------------------------------------------------------------------
# Multiple components
# ---------------------------------------------------------------------------


def test_build_signal_chain_xml_two_components_order() -> None:
    result = build_signal_chain_xml(_COMPONENTS_TWO, _SCHEMA)
    root = ET.fromstring(result)
    comps = root.findall("component")
    assert len(comps) == 2
    assert comps[0].get("name") == "Tweed Delight"
    assert comps[1].get("name") == "Spring Reverb"


def test_build_signal_chain_xml_num_parameters_attribute() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    params_el = root.find(".//parameters")
    assert params_el is not None
    assert params_el.get("num-parameters") == "2"


# ---------------------------------------------------------------------------
# GUI structure
# ---------------------------------------------------------------------------


def test_build_signal_chain_xml_has_component_gui() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    gui = root.find(".//component-gui")
    assert gui is not None


def test_build_signal_chain_xml_has_component_audio() -> None:
    result = build_signal_chain_xml(_COMPONENTS_ONE, _SCHEMA)
    root = ET.fromstring(result)
    audio = root.find(".//component-audio")
    assert audio is not None
    assert audio.get("version") == "2"

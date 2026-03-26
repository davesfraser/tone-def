"""
xml_builder.py
--------------
Assembles Guitar Rig 7 <non-fix-components> XML from a list of component dicts
produced by component_mapper.py, ready for injection into a .ngrr preset via
transplant_preset().

The GR7 XML format requires this nesting structure per component:

    <component id="40000" name="Treble Booster" uuid="...">
      <component-gui>
        <view component-template-bank="" component-template-name=""
              stored-view-mode="1" view-mode="1" visible="true"/>
      </component-gui>
      <component-audio version="2">
        <parameters enable-automation="1" num-parameters="N" static-automation="0">
          <parameter id="Pwr" name="On/Off" value="1.000000">
            <base-parameters remote-max="1.000000" remote-min="0.000000"/>
          </parameter>
          ...
        </parameters>
      </component-audio>
    </component>

The component schema supplies the param_name display label for each param_id.
"""

import base64
import uuid as _uuid
from xml.etree.ElementTree import Element, SubElement, indent, tostring


def build_signal_chain_xml(
    components: list[dict],
    schema: dict,
) -> bytes:
    """
    Assemble a <non-fix-components> XML block from a list of component dicts.

    Each component dict (as produced by component_mapper.map_components) has:
        component_name: str
        component_id: int
        parameters: dict[str, float]  — keyed by param_id

    The schema dict (from component_schema.json) is used to look up the
    param_name display label for each param_id. If a param_id is not found
    in the schema, its param_id is used as the name fallback.

    Args:
        components: Ordered list of component dicts forming the signal chain.
        schema: Parsed component_schema.json as a dict keyed by component_name.

    Returns:
        UTF-8 encoded bytes of the complete
        <non-fix-components>...</non-fix-components> block,
        indented to match GR7's native preset format.
    """
    root = Element("non-fix-components")

    for comp in components:
        comp_name = comp["component_name"]
        comp_id = comp["component_id"]
        parameters = comp.get("parameters", {})

        # Build a param_id → param_name lookup from the schema for this component
        param_name_lookup: dict[str, str] = {}
        if comp_name in schema:
            for param_entry in schema[comp_name].get("parameters", []):
                param_name_lookup[param_entry["param_id"]] = param_entry["param_name"]

        # <component id="..." name="..." uuid="...">
        comp_el = SubElement(root, "component")
        comp_el.set("id", str(comp_id))
        comp_el.set("name", comp_name)
        comp_el.set("uuid", base64.b64encode(_uuid.uuid4().bytes).decode("ascii"))

        # <component-gui><view .../></component-gui>
        gui_el = SubElement(comp_el, "component-gui")
        view_el = SubElement(gui_el, "view")
        view_el.set("component-template-bank", "")
        view_el.set("component-template-name", "")
        view_el.set("stored-view-mode", "1")
        view_el.set("view-mode", "1")
        view_el.set("visible", "true")

        # <component-audio version="2"><parameters ...>
        audio_el = SubElement(comp_el, "component-audio")
        audio_el.set("version", "2")

        params_el = SubElement(audio_el, "parameters")
        params_el.set("enable-automation", "1")
        params_el.set("num-parameters", str(len(parameters)))
        params_el.set("static-automation", "0")

        for param_id, value in parameters.items():
            # Integer params (enums, selectors, step counts) are written
            # as bare integers; continuous params as 6-decimal floats.
            # Values are already range-checked by fill_defaults.
            formatted = str(value) if isinstance(value, int) else f"{float(value):.6f}"
            param_el = SubElement(params_el, "parameter")
            param_el.set("id", param_id)
            param_el.set("name", param_name_lookup.get(param_id, param_id))
            param_el.set("value", formatted)
            # <base-parameters remote-max="1.000000" remote-min="0.000000"/>
            base_el = SubElement(param_el, "base-parameters")
            base_el.set("remote-max", "1.000000")
            base_el.set("remote-min", "0.000000")

    indent(root, space="  ")
    return tostring(root, encoding="unicode").encode("utf-8")

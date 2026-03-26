import os
import tempfile

import anthropic
import streamlit as st
from dotenv import load_dotenv

from tonedef.component_mapper import load_schema, map_components
from tonedef.ngrr_builder import transplant_preset
from tonedef.paths import DATA_EXTERNAL
from tonedef.prompts import SYSTEM_PROMPT
from tonedef.settings import settings
from tonedef.xml_builder import build_signal_chain_xml

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

st.title("ToneDef")
st.caption("Describe the guitar tone you want to achieve")

query = st.text_area("Your tone query", placeholder="e.g. I want the Hotel California solo tone")

if st.button("Generate signal chain") and query:
    with st.spinner("Analysing tone..."):
        system = SYSTEM_PROMPT.replace("{{TAVILY_RESULTS}}", "No context retrieved.")

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=settings.phase1_temperature,
            system=system,
            messages=[{"role": "user", "content": query}],
        )

        result = message.content[0].text
        st.session_state["last_result"] = result
        st.session_state.pop("last_components", None)
        st.session_state.pop("last_preset", None)

if "last_result" in st.session_state:
    st.text(st.session_state["last_result"])

    if st.button("Build preset") and "last_components" not in st.session_state:
        with st.spinner("Mapping components..."):
            components = map_components(st.session_state["last_result"], client)
            st.session_state["last_components"] = components

        schema = load_schema()
        xml = build_signal_chain_xml(components, schema)

        with tempfile.NamedTemporaryFile(suffix=".ngrr", delete=False) as tmp:
            tmp_path = tmp.name

        transplant_preset(
            template_path=DATA_EXTERNAL / "Blank_template.ngrr",
            signal_chain_xml=xml,
            output_path=tmp_path,
            preset_name="ToneDef Preset",
        )
        with open(tmp_path, "rb") as f:
            st.session_state["last_preset"] = f.read()
        os.unlink(tmp_path)

if "last_components" in st.session_state:
    with st.expander("Components selected", expanded=False):
        for comp in st.session_state["last_components"]:
            mod = comp.get("modification", "—")
            base = comp.get("base_exemplar", "")
            origin = f"from _{base}_" if base else ""
            st.markdown(
                f"**{comp['component_name']}** (id `{comp['component_id']}`) "
                f"· {mod} · {comp.get('confidence', '')} {origin}"
            )

if "last_preset" in st.session_state:
    st.download_button(
        label="Download .ngrr preset",
        data=st.session_state["last_preset"],
        file_name="tonedef_preset.ngrr",
        mime="application/octet-stream",
    )

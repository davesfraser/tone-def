import os

import anthropic
import streamlit as st
from dotenv import load_dotenv

from tonedef.prompts import SYSTEM_PROMPT

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
            system=system,
            messages=[{"role": "user", "content": query}],
        )

        result = message.content[0].text
        st.session_state["last_result"] = result

if "last_result" in st.session_state:
    st.text(st.session_state["last_result"])

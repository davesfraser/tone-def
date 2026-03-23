import marimo

__generated_with = "0.20.4"
app = marimo.App()


@app.cell
def _():
    import os

    import anthropic
    from dotenv import load_dotenv

    from tonedef.prompt import SYSTEM_PROMPT

    load_dotenv()
    return SYSTEM_PROMPT, anthropic, os


@app.cell
def _(SYSTEM_PROMPT):
    print(SYSTEM_PROMPT[:500])
    return


@app.cell
def _(SYSTEM_PROMPT, anthropic, os):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    test_query = "Give me Eric Clapton's tone from John Mayall's Blues Breakers album 'Beano'"

    # Until such time that we have something to place into context, we'll overwrite with nothing
    system = SYSTEM_PROMPT.replace("{{TAVILY_RESULTS}}", "No context retrieved.")
    return client, system, test_query


@app.cell
def _(client, system, test_query):
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": test_query}],
    )

    print(message.content[0].text)
    return


if __name__ == "__main__":
    app.run()

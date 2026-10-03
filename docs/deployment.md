# Streamlit Community Cloud deployment

The user selected Streamlit Community Cloud. The app entrypoint is `app.py` and the tested interpreter is Python 3.12.

Repository: [angelinjohn/dhaga-return-intelligence](https://github.com/angelinjohn/dhaga-return-intelligence) (private). Branch: `codex/initial-mvp`.

1. Push the project to a GitHub repository you can access from Streamlit. Keep `.env`, `.venv`, `.streamlit/secrets.toml`, and generated output out of Git.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/), sign in, and connect the matching GitHub account.
3. Select **Create app**, choose `angelinjohn/dhaga-return-intelligence`, branch `codex/initial-mvp`, and set the file path to **app.py**.
4. Under **Advanced settings**, select Python **3.12**. The offline demo requires no secrets.
5. Deploy. Open the returned `streamlit.app` URL in a fresh browser session, run the sample, inspect Insights, and resolve an item in Review Queue.

Visitors can select **Live models → Use my OpenAI API key** and paste their own key into the masked field. This works on the deployed site without a host OpenAI key. Model A, Model B, and any enabled fallback must use the OpenAI provider. Keys are passed directly to per-run clients, never shared through environment variables or written to disk. Visitors can clear the key explicitly; switching to offline mode or server credentials also clears the input. Use HTTPS and only invite users to enter keys into a deployment they trust: the server necessarily receives the key in memory, and requests are billed to the visitor's OpenAI account.

For host-funded live runs, users can select **Use server credentials**. Configure top-level TOML values under Cloud app settings → Secrets. The `OPENAI_API_KEY` below is optional when all visitors bring their own keys. Do not paste `.env` syntax or put API keys into Git:

```toml
OPENAI_API_KEY = "YOUR_KEY"
MODEL_A_PROVIDER = "openai"
MODEL_A_NAME = "gpt-4.1-mini"
MODEL_A_TEMPERATURE = "0"
MODEL_B_PROVIDER = "openai"
MODEL_B_NAME = "gpt-4.1"
MODEL_B_TEMPERATURE = "0"
THRESHOLD_A = "0.85"
THRESHOLD_B = "0.80"
# Set current per-million-token USD prices before a live run.
MODEL_A_INPUT_PRICE_PER_MILLION = "0"
MODEL_A_OUTPUT_PRICE_PER_MILLION = "0"
MODEL_B_INPUT_PRICE_PER_MILLION = "0"
MODEL_B_OUTPUT_PRICE_PER_MILLION = "0"
LANGSMITH_TRACING = "false"
```

This app has no built-in user authentication or spending quota. Use Cloud's appropriate sharing controls for a credential-enabled demo. Each visitor receives independent session state; exporting is necessary to retain reviews.

Reference: [official Cloud deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

An optional Actions test workflow is saved as `docs/github-actions-tests.yml`. Move it to `.github/workflows/tests.yml` when your GitHub authorization includes the `workflow` scope. The current deployment does not require Actions; run the tests locally with the README command.

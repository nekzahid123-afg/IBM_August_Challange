import os
import warnings
from dotenv import load_dotenv
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

# Suppress WatsonxAPIWarning noise
warnings.filterwarnings("ignore")

load_dotenv()

WATSONX_API_KEY = os.getenv("WATSONX_APIKEY", "")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

def query_granite(prompt: str) -> str:
    """Queries watsonx.ai model using provided prompt context."""
    if WATSONX_API_KEY and WATSONX_PROJECT_ID:
        try:
            credentials = Credentials(
                url=WATSONX_URL,
                api_key=WATSONX_API_KEY
            )
            
            model = ModelInference(
                model_id="ibm/granite-4-h-small",
                credentials=credentials,
                project_id=WATSONX_PROJECT_ID,
                params={
                    "max_new_tokens": 300,
                    "temperature": 0.1
                }
            )
            
            response = model.generate_text(prompt=prompt)
            return response.strip() if isinstance(response, str) else str(response).strip()
            
        except Exception as e:
            print(f"[Warning] WatsonX API Error: {e}. Executing fallback response.")

    return (
        "1) Plain-language explanation:\n"
        "Operational parameter anomaly detected outside expected bounds.\n\n"
        "2) Likely root cause:\n"
        "Transient subsystem voltage variance.\n\n"
        "3) Recommended action:\n"
        "Check telemetry logs on next pass."
    )
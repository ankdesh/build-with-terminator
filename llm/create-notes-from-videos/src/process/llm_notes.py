import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

class LlamaNotesGenerator:
    """Generates 2-level hierarchical pointwise notes from transcripts using a local Llama model."""

    def __init__(self, api_url: str = "http://localhost:11434/v1", model: str = "llama3") -> None:
        self.api_url = api_url.rstrip("/")
        self.model = model

    def generate_notes(self, transcript: str) -> str:
        """Sends the transcript to the local LLM and returns the structured notes.

        Args:
            transcript: The transcribed text.

        Returns:
            A string containing the 2-level hierarchical pointwise notes.
        """
        if not transcript.strip():
            logger.warning("Empty transcript provided to LLM. Skipping note generation.")
            return ""

        endpoint = f"{self.api_url}/chat/completions"
        system_prompt = (
            "You are an expert assistant. Your task is to write detailed, structured lecture notes "
            "based on the provided transcript of a video slide.\n\n"
            "Guidelines:\n"
            "1. Capture all key information, definitions, explanations, and context related to the topic.\n"
            "2. Format the notes in a clear 2-level hierarchy of bullet points:\n"
            "   - Main topic / key point\n"
            "     * Sub-point explaining details, examples, or context\n"
            "3. Do not include any introductory or concluding text (like 'Here are the notes:'). "
            "Start directly with the first bullet point."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Transcript:\n{transcript}"}
            ],
            "temperature": 0.2
        }

        logger.info(f"Sending transcript to local LLM ({self.model}) at {endpoint}...")
        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            notes = data["choices"][0]["message"]["content"].strip()
            logger.info("Successfully generated notes from LLM.")
            return notes
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to local LLM at {endpoint}: {e}")
            raise RuntimeError(
                f"Could not connect to local LLM at '{endpoint}'. "
                f"Please ensure your local LLM runner (e.g. Ollama, LM Studio) is running and "
                f"the model '{self.model}' is loaded, or run with --skip-llm to skip this step."
            ) from e
        except (KeyError, IndexError) as e:
            logger.error(f"Malformed response from LLM API: {e}")
            raise RuntimeError(f"Received malformed response from the local LLM API: {e}") from e

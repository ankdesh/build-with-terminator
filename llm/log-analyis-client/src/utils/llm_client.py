import json
import urllib.error
import urllib.request


def execute_llm(prompt: str, model: str = "hf.co/unsloth/gpt-oss-20b-GGUF:Q4_K_M") -> str:
    """
    Sends a prompt to the local Ollama instance and returns the text reply.
    This is a temporary setup.

    Args:
        prompt (str): The prompt to send to the LLM.
        model (str): The name of the local Ollama model to use. You may need to change
                     this depending on which model you have pulled (e.g., 'llama3', 'mistral').

    Returns:
        str: The generated text response from the model.
    """
    url = "http://localhost:11434/api/generate"

    payload = {"model": model, "prompt": prompt, "stream": False}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as response:
            result_data = response.read().decode("utf-8")
            result_json = json.loads(result_data)
            return result_json.get("response", "")
    except urllib.error.URLError as e:
        return f"Error connecting to Ollama: {e}. Is Ollama running?"
    except json.JSONDecodeError:
        return "Error decoding JSON response from Ollama."
    except Exception as e:
        return f"An unexpected error occurred: {e}"


if __name__ == "__main__":
    # Simple test if the file is run directly
    print("Testing connection to local Ollama...")
    test_prompt = "Explain why the sky is blue in one short sentence."
    print(f"Prompt: {test_prompt}")
    print(f"Response: {execute_llm(test_prompt)}")

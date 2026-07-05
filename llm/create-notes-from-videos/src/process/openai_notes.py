import os
import logging
import re
from typing import List, Dict
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAINotesGenerator:
    """Generates 2-level hierarchical pointwise notes from transcripts using the OpenAI API.
    
    Optimized to send all slide transcripts in a single request and parse the response.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.2) -> None:
        self.model = model
        self.temperature = temperature
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable is not set.")
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set. Please set it before running the script:\n"
                "  export OPENAI_API_KEY='your_api_key_here'"
            )
            
        self.client = OpenAI(api_key=api_key)

    def generate_notes(self, slides_transcripts: List[str]) -> Dict[int, str]:
        """Sends all slide transcripts in a single request to OpenAI and returns parsed notes per slide.

        Args:
            slides_transcripts: A list of transcripts for each unique slide in chronological order.

        Returns:
            A dictionary mapping 1-based slide index (int) to its generated notes (str).
        """
        if not slides_transcripts:
            logger.warning("No transcripts provided. Skipping note generation.")
            return {}

        # Format the combined transcripts
        formatted_transcripts = []
        for i, transcript in enumerate(slides_transcripts, start=1):
            formatted_transcripts.append(f"=== SLIDE {i} ===\n{transcript.strip() if transcript.strip() else '[No audio captured]'}")
        
        combined_text = "\n\n".join(formatted_transcripts)

        system_prompt = (
            "You are an expert assistant. Your task is to write detailed, structured lecture notes "
            "for each slide in the lecture based on the provided transcripts.\n\n"
            "FORMAT INSTRUCTIONS:\n"
            "1. For each slide, you MUST start its notes with a slide marker on a new line: [SLIDE X] "
            "(where X is the slide number, e.g. [SLIDE 1], [SLIDE 2]).\n"
            "2. Follow the marker immediately with the notes for that slide.\n"
            "3. Format the notes in a clear 2-level hierarchy of bullet points:\n"
            "   - Main topic / key point\n"
            "     * Sub-bullet point explaining details, examples, or context\n"
            "4. Do NOT include any introductory or concluding text (like 'Here are the notes:'). "
            "Begin directly with the first slide marker [SLIDE 1].\n\n"
            "Example Output:\n"
            "[SLIDE 1]\n"
            "- Topic A\n"
            "  * Details about topic A\n\n"
            "[SLIDE 2]\n"
            "- Topic B\n"
            "  * Details about topic B"
        )

        logger.info(f"Sending {len(slides_transcripts)} slide transcripts to OpenAI ({self.model}) in a single request...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_text}
                ],
                temperature=self.temperature
            )
            response_text = response.choices[0].message.content.strip()
            
            # Parse the response using regex
            # We split by [SLIDE X] (case insensitive)
            parts = re.split(r"\[SLIDE\s+(\d+)\]", response_text, flags=re.IGNORECASE)
            
            slide_notes_map: Dict[int, str] = {}
            
            # If the split worked, parts will have:
            # - index 0: text before the first [SLIDE 1] (usually empty)
            # - index 1: '1' (the slide number)
            # - index 2: the notes for slide 1
            # - index 3: '2'
            # - index 4: the notes for slide 2
            # ... and so on
            for i in range(1, len(parts), 2):
                try:
                    slide_num = int(parts[i])
                    notes = parts[i+1].strip()
                    slide_notes_map[slide_num] = notes
                except (ValueError, IndexError) as parse_err:
                    logger.warning(f"Failed to parse slide notes segment at index {i}: {parse_err}")
            
            logger.info(f"Successfully parsed notes for {len(slide_notes_map)} slides.")
            return slide_notes_map
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise RuntimeError(f"Failed to generate notes via OpenAI API: {e}") from e

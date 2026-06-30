import logging
from typing import Optional
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class AudioTranscriber:
    """Transcribes audio files using a local faster-whisper model."""

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self.model: Optional[WhisperModel] = None

    def _load_model(self) -> None:
        """Loads the Whisper model, attempting GPU first, then falling back to CPU."""
        if self.model is not None:
            return

        logger.info(f"Loading Whisper model '{self.model_size}'...")
        try:
            # Try loading on GPU
            logger.info("Attempting to load model on CUDA (GPU)...")
            self.model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
            logger.info("Whisper model loaded successfully on CUDA.")
        except Exception as e:
            logger.warning(f"Could not load Whisper model on CUDA: {e}. Falling back to CPU.")
            try:
                # Fallback to CPU
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("Whisper model loaded successfully on CPU (int8).")
            except Exception as cpu_err:
                logger.error(f"Failed to load Whisper model on CPU: {cpu_err}")
                raise RuntimeError("Failed to initialize Whisper model on both GPU and CPU.") from cpu_err

    def transcribe(self, audio_path: str) -> str:
        """Transcribes the given audio file and returns the text.

        Args:
            audio_path: Path to the WAV/MP3 audio file.

        Returns:
            The transcribed text as a single string.
        """
        self._load_model()
        assert self.model is not None
        
        logger.debug(f"Transcribing audio file: {audio_path}")
        try:
            segments, info = self.model.transcribe(audio_path, beam_size=5)
            
            # Extract text from segments
            text_segments = []
            for segment in segments:
                text_segments.append(segment.text)
                
            transcription = " ".join(text_segments).strip()
            logger.debug(f"Transcription completed for {audio_path}. Length: {len(transcription)} chars.")
            return transcription
        except Exception as e:
            logger.error(f"Error transcribing {audio_path}: {e}")
            # Do not fail the whole process if a single audio file fails, return empty string
            return ""

import os
import shutil
import logging
from typing import List, Dict
from src.process.transcriber import AudioTranscriber
from src.process.comparator import ImageComparator

logger = logging.getLogger(__name__)

class SessionProcessor:
    """Orchestrates the transcription and merging of captured slides and audio."""

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        threshold: float = 0.95,
        model_size: str = "base"
    ) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.threshold = threshold
        
        self.transcriber = AudioTranscriber(model_size=model_size)
        self.comparator = ImageComparator()
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_sorted_files(self) -> tuple[List[str], List[str]]:
        """Finds and sorts all screenshots and audio files in the input directory."""
        all_files = os.listdir(self.input_dir)
        
        # Filter and sort screenshots (e.g., screenshot_0000.png, screenshot_0001.png)
        screenshots = sorted([
            f for f in all_files 
            if f.startswith("screenshot_") and f.endswith(".png")
        ])
        
        # Filter and sort audio files (e.g., audio_0000.wav, audio_0001.wav)
        audios = sorted([
            f for f in all_files 
            if f.startswith("audio_") and f.endswith(".wav")
        ])
        
        return screenshots, audios

    def process(self) -> None:
        """Processes the session by transcribing audio and merging similar slides."""
        screenshots, audios = self._get_sorted_files()
        
        if not screenshots:
            logger.error(f"No screenshots found in {self.input_dir}. Nothing to process.")
            return
            
        logger.info(f"Found {len(screenshots)} screenshots and {len(audios)} audio files to process.")
        
        # Step 1: Transcribe all audio files
        # We map audio index (e.g. 0) to its transcript text
        transcripts: Dict[int, str] = {}
        for audio_file in audios:
            # Extract index from filename, e.g. "audio_0001.wav" -> 1
            try:
                idx_str = audio_file.split("_")[1].split(".")[0]
                idx = int(idx_str)
            except (IndexError, ValueError):
                logger.warning(f"Skipping malformed audio file: {audio_file}")
                continue
                
            audio_path = os.path.join(self.input_dir, audio_file)
            logger.info(f"Transcribing {audio_file}...")
            transcripts[idx] = self.transcriber.transcribe(audio_path)
            
        # Step 2: Compare slides and merge transcripts
        # We start with screenshot_0000.png as the first slide
        active_idx = 0
        active_transcripts: List[str] = []
        
        # Add the first transcript if it exists
        if 0 in transcripts:
            active_transcripts.append(transcripts[0])
            
        slide_counter = 1
        
        for i in range(1, len(screenshots)):
            current_screenshot = screenshots[i]
            active_screenshot = screenshots[active_idx]
            
            current_path = os.path.join(self.input_dir, current_screenshot)
            active_path = os.path.join(self.input_dir, active_screenshot)
            
            # Compare current screenshot with active screenshot
            ssim_score = self.comparator.calculate_ssim(active_path, current_path)
            
            if ssim_score >= self.threshold:
                # The slide hasn't changed. Merge the transcript of the audio segment
                # corresponding to the current interval (which starts at screenshot i)
                logger.info(f"Slide {i} is similar to active slide {active_idx} (SSIM: {ssim_score:.4f}). Merging.")
                if i in transcripts and transcripts[i]:
                    active_transcripts.append(transcripts[i])
            else:
                # The slide has changed! Save the previous active slide and its transcripts.
                logger.info(f"Slide {i} is different from active slide {active_idx} (SSIM: {ssim_score:.4f}). Creating new slide.")
                self._save_slide(slide_counter, active_path, active_transcripts)
                slide_counter += 1
                
                # Set the current slide as the active slide
                active_idx = i
                active_transcripts = []
                if i in transcripts and transcripts[i]:
                    active_transcripts.append(transcripts[i])
                    
        # Save the final active slide
        if active_idx < len(screenshots):
            final_active_path = os.path.join(self.input_dir, screenshots[active_idx])
            self._save_slide(slide_counter, final_active_path, active_transcripts)
            
        logger.info(f"Processing complete. Generated {slide_counter} unique slides in {self.output_dir}.")

    def _save_slide(self, counter: int, image_path: str, transcripts: List[str]) -> None:
        """Saves a slide image and its merged transcript to the output directory."""
        dest_image_name = f"slide_{counter:02d}.png"
        dest_transcript_name = f"slide_{counter:02d}.txt"
        
        dest_image_path = os.path.join(self.output_dir, dest_image_name)
        dest_transcript_path = os.path.join(self.output_dir, dest_transcript_name)
        
        # Copy image
        shutil.copy2(image_path, dest_image_path)
        
        # Write merged transcript (joined by space/newlines)
        merged_text = "\n\n".join([t for t in transcripts if t.strip()]).strip()
        with open(dest_transcript_path, "w", encoding="utf-8") as f:
            f.write(merged_text)
            
        logger.info(f"Saved: {dest_image_name} and {dest_transcript_name}")

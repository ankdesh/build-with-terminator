import os
import shutil
import logging
import json
import re
from typing import List, Dict, Tuple, Optional
from src.process.transcriber import AudioTranscriber
from src.process.comparator import ImageComparator
from src.process.openai_notes import OpenAINotesGenerator
from src.process.pdf_generator import PDFGenerator

logger = logging.getLogger(__name__)

class SessionProcessor:
    """Orchestrates the transcription, merging, note generation, and PDF compilation of captured sessions."""

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        threshold: float = 0.95,
        model_size: str = "base",
        llm_model: str = "gpt-4o-mini",
        llm_temperature: float = 0.2,
        skip_llm: bool = False,
        pdf_image_quality: Optional[int] = 80
    ) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.threshold = threshold
        self.skip_llm = skip_llm
        self.pdf_image_quality = pdf_image_quality
        
        self.transcriber = AudioTranscriber(model_size=model_size)
        self.comparator = ImageComparator()
        
        if not self.skip_llm:
            self.llm_generator = OpenAINotesGenerator(model=llm_model, temperature=llm_temperature)
        else:
            self.llm_generator = None
            
        self.pdf_generator = PDFGenerator()
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_sorted_files(self) -> Tuple[List[str], List[str], str, Optional[str]]:
        """Finds and sorts all screenshots, audio, and metadata files in the input directory.
        
        Supports both the new YYYYMMDD_HHMMSS_partXXXX format and the old screenshot_XXXX format.
        
        Returns:
            A tuple of (sorted_screenshots, sorted_audios, session_prefix, timestamps_json_path).
        """
        all_files = os.listdir(self.input_dir)
        
        # 1. Try matching the new timestamped format: YYYYMMDD_HHMMSS_partXXXX
        timestamp_pattern = r"^(\d{8}_\d{6})_part(\d{4})\.(png|wav)$"
        timestamp_files = []
        session_prefixes = set()
        
        for f in all_files:
            match = re.match(timestamp_pattern, f)
            if match:
                prefix, part_idx, ext = match.groups()
                timestamp_files.append((f, prefix, int(part_idx), ext))
                session_prefixes.add(prefix)
                
        if timestamp_files:
            chosen_prefix = sorted(list(session_prefixes))[0]
            logger.info(f"Detected timestamped session prefix: {chosen_prefix}")
            
            screenshots = sorted([
                f for f, pref, idx, ext in timestamp_files 
                if pref == chosen_prefix and ext == "png"
            ], key=lambda x: int(re.search(r"_part(\d+)\.png$", x).group(1)))
            
            audios = sorted([
                f for f, pref, idx, ext in timestamp_files 
                if pref == chosen_prefix and ext == "wav"
            ], key=lambda x: int(re.search(r"_part(\d+)\.wav$", x).group(1)))
            
            timestamps_json = f"{chosen_prefix}_timestamps.json"
            timestamps_path = os.path.join(self.input_dir, timestamps_json)
            if not os.path.exists(timestamps_path):
                timestamps_path = None
                
            return screenshots, audios, chosen_prefix, timestamps_path

        # 2. Fallback to old format: screenshot_XXXX.png, audio_XXXX.wav
        screenshots = sorted([
            f for f in all_files 
            if f.startswith("screenshot_") and f.endswith(".png")
        ])
        audios = sorted([
            f for f in all_files 
            if f.startswith("audio_") and f.endswith(".wav")
        ])
        
        return screenshots, audios, "session", None

    def process(self) -> None:
        """Processes the session by transcribing, mapping, merging, and summarizing."""
        screenshots, audios, session_prefix, timestamps_path = self._get_sorted_files()
        
        if not screenshots:
            logger.error(f"No screenshots found in {self.input_dir}. Nothing to process.")
            return
            
        logger.info(f"Found {len(screenshots)} screenshots and {len(audios)} audio files to process.")
        
        # Check if we have continuous audio and timestamps
        continuous_audio = os.path.join(self.input_dir, f"{session_prefix}_continuous.wav")
        
        # Map of screenshot index -> raw transcript text
        raw_transcripts: Dict[int, str] = {i: "" for i in range(len(screenshots))}
        
        if os.path.exists(continuous_audio) and timestamps_path:
            # --- NEW FLOW: Transcribe full audio and map to screenshots ---
            logger.info(f"Found continuous audio: {continuous_audio}. Running full transcription...")
            
            # Load timestamps
            with open(timestamps_path, "r", encoding="utf-8") as f:
                timestamps_data = json.load(f)
                
            # Transcribe the entire continuous file
            self.transcriber._load_model()
            assert self.transcriber.model is not None
            
            logger.info("Transcribing continuous audio file...")
            segments, info = self.transcriber.model.transcribe(continuous_audio, beam_size=5)
            
            # Map segment texts to screenshots based on timestamps
            # Sort timestamps data by timestamp to be safe
            sorted_timestamps = sorted(timestamps_data, key=lambda x: x["timestamp"])
            
            screenshot_segments: List[List[str]] = [[] for _ in range(len(screenshots))]
            
            for segment in segments:
                start_time = segment.start
                # Find the first screenshot taken after this segment's start time
                assigned_idx = len(sorted_timestamps) - 1  # Default to the last screenshot
                for idx, record in enumerate(sorted_timestamps):
                    if record["timestamp"] > start_time:
                        assigned_idx = idx
                        break
                
                # Find the index of this screenshot in our screenshots list
                shot_name = sorted_timestamps[assigned_idx]["screenshot"]
                try:
                    shot_idx = screenshots.index(shot_name)
                    screenshot_segments[shot_idx].append(segment.text)
                except ValueError:
                    logger.warning(f"Screenshot {shot_name} from timestamps JSON not found in screenshots list.")
                    
            # Join segments for each screenshot
            for i in range(len(screenshots)):
                raw_transcripts[i] = " ".join(screenshot_segments[i]).strip()
                
        else:
            # --- LEGACY FLOW: Transcribe individual segment audio files ---
            logger.info("No continuous audio found. Falling back to individual segment transcription.")
            for audio_file in audios:
                try:
                    if "_part" in audio_file:
                        idx_str = audio_file.split("_part")[1].split(".")[0]
                    else:
                        idx_str = audio_file.split("_")[1].split(".")[0]
                    idx = int(idx_str)
                except (IndexError, ValueError):
                    logger.warning(f"Skipping malformed audio file: {audio_file}")
                    continue
                    
                audio_path = os.path.join(self.input_dir, audio_file)
                logger.info(f"Transcribing {audio_file}...")
                raw_transcripts[idx] = self.transcriber.transcribe(audio_path)

        # Step 2: Compare slides and merge transcripts
        active_idx = 0
        active_transcripts: List[str] = []
        if raw_transcripts.get(0):
            active_transcripts.append(raw_transcripts[0])
            
        slide_counter = 1
        merged_slides_info: List[Dict[str, str]] = []
        
        for i in range(1, len(screenshots)):
            current_screenshot = screenshots[i]
            active_screenshot = screenshots[active_idx]
            
            current_path = os.path.join(self.input_dir, current_screenshot)
            active_path = os.path.join(self.input_dir, active_screenshot)
            
            ssim_score = self.comparator.calculate_ssim(active_path, current_path)
            
            if ssim_score >= self.threshold:
                logger.info(f"Slide {i} is similar to active slide {active_idx} (SSIM: {ssim_score:.4f}). Merging.")
                if raw_transcripts.get(i):
                    active_transcripts.append(raw_transcripts[i])
            else:
                logger.info(f"Slide {i} is different from active slide {active_idx} (SSIM: {ssim_score:.4f}). Creating new slide.")
                # We save the raw merged transcript
                dest_image_name = f"{session_prefix}_slide_{slide_counter:02d}.png"
                dest_transcript_name = f"{session_prefix}_slide_{slide_counter:02d}_transcript.txt"
                
                dest_image_path = os.path.join(self.output_dir, dest_image_name)
                dest_transcript_path = os.path.join(self.output_dir, dest_transcript_name)
                
                shutil.copy2(active_path, dest_image_path)
                merged_text = "\n\n".join([t for t in active_transcripts if t.strip()]).strip()
                with open(dest_transcript_path, "w", encoding="utf-8") as f:
                    f.write(merged_text)
                    
                merged_slides_info.append({
                    "image_path": dest_image_path,
                    "transcript_path": dest_transcript_path,
                    "transcript": merged_text,
                    "slide_idx": slide_counter
                })
                slide_counter += 1
                
                # Reset active slide
                active_idx = i
                active_transcripts = []
                if raw_transcripts.get(i):
                    active_transcripts.append(raw_transcripts[i])
                    
        # Save the final active slide
        if active_idx < len(screenshots):
            final_active_path = os.path.join(self.input_dir, screenshots[active_idx])
            dest_image_name = f"{session_prefix}_slide_{slide_counter:02d}.png"
            dest_transcript_name = f"{session_prefix}_slide_{slide_counter:02d}_transcript.txt"
            
            dest_image_path = os.path.join(self.output_dir, dest_image_name)
            dest_transcript_path = os.path.join(self.output_dir, dest_transcript_name)
            
            shutil.copy2(final_active_path, dest_image_path)
            merged_text = "\n\n".join([t for t in active_transcripts if t.strip()]).strip()
            with open(dest_transcript_path, "w", encoding="utf-8") as f:
                f.write(merged_text)
                
            merged_slides_info.append({
                "image_path": dest_image_path,
                "transcript_path": dest_transcript_path,
                "transcript": merged_text,
                "slide_idx": slide_counter
            })

        # Step 3: Generate context-aware summaries using OpenAI in a single combined request
        final_slides_for_pdf: List[Dict[str, str]] = []
        num_slides = len(merged_slides_info)
        
        # Compile all transcripts into a list
        all_transcripts = [slide["transcript"] for slide in merged_slides_info]
        
        # Generate notes for all slides in a single combined request
        all_notes: Dict[int, str] = {}
        if self.llm_generator and any(t.strip() for t in all_transcripts):
            try:
                all_notes = self.llm_generator.generate_notes(all_transcripts)
            except Exception as e:
                logger.error(f"Failed to generate OpenAI notes: {e}. Falling back to raw transcripts.")
        
        for slide in merged_slides_info:
            slide_idx = slide["slide_idx"]
            current_transcript = slide["transcript"]
            
            dest_notes_name = f"{session_prefix}_slide_{slide_idx:02d}_notes.txt"
            dest_notes_path = os.path.join(self.output_dir, dest_notes_name)
            
            # Retrieve notes from the parsed dictionary, falling back to raw transcript if missing
            notes_content = ""
            if not self.skip_llm and self.llm_generator:
                notes_content = all_notes.get(slide_idx, "").strip()
                if not notes_content:
                    logger.warning(f"No notes returned for slide {slide_idx}. Falling back to raw transcript.")
                    notes_content = f"[OpenAI Notes Generation Missing]\n\n{current_transcript}"
            else:
                notes_content = current_transcript if current_transcript else "No audio captured for this slide."
                
            with open(dest_notes_path, "w", encoding="utf-8") as f:
                f.write(notes_content)
                
            logger.info(f"Saved: {dest_notes_name}")
            
            final_slides_for_pdf.append({
                "image_path": slide["image_path"],
                "notes": notes_content
            })

        # Step 4: Generate PDF
        pdf_path = os.path.join(self.output_dir, f"{session_prefix}_notes.pdf")
        self.pdf_generator.generate_pdf(final_slides_for_pdf, pdf_path, image_quality=self.pdf_image_quality)
        
        logger.info(f"Processing complete. Generated {num_slides} unique slides and PDF in {self.output_dir}.")

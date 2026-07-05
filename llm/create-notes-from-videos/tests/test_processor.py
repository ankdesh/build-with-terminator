import os
import shutil
import tempfile
import json
import pytest
from unittest.mock import MagicMock

# Mock OpenAI client before importing modules that use it
import sys
mock_openai_module = MagicMock()
sys.modules['openai'] = mock_openai_module

from src.process.comparator import ImageComparator
from src.process.processor import SessionProcessor
from src.process.openai_notes import OpenAINotesGenerator

@pytest.fixture
def temp_dirs():
    """Creates temporary directories for input and output."""
    input_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    yield input_dir, output_dir
    shutil.rmtree(input_dir)
    shutil.rmtree(output_dir)

def create_dummy_image(path: str, color: str = "white", text: str = "") -> None:
    """Helper to create a dummy image."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (200, 200), color=color)
    if text:
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), text, fill="black")
    img.save(path)

def create_dummy_audio(path: str) -> None:
    """Helper to create an empty dummy audio file."""
    with open(path, "wb") as f:
        f.write(b"RIFF....WAVEfmt ....data....")

def test_image_comparator(temp_dirs):
    input_dir, _ = temp_dirs
    img1_path = os.path.join(input_dir, "img1.png")
    img2_path = os.path.join(input_dir, "img2.png")
    img3_path = os.path.join(input_dir, "img3.png")

    create_dummy_image(img1_path, "white")
    create_dummy_image(img2_path, "white")
    create_dummy_image(img3_path, "black")

    comparator = ImageComparator()

    ssim_identical = comparator.calculate_ssim(img1_path, img2_path)
    assert pytest.approx(ssim_identical, abs=1e-4) == 1.0

    ssim_different = comparator.calculate_ssim(img1_path, img3_path)
    assert ssim_different < 0.9

def test_session_processor_legacy(temp_dirs, monkeypatch):
    """Verifies legacy mode where individual segment WAV files are transcribed."""
    input_dir, output_dir = temp_dirs

    # Create legacy files
    create_dummy_image(os.path.join(input_dir, "screenshot_0000.png"), "white", "Slide A")
    create_dummy_image(os.path.join(input_dir, "screenshot_0001.png"), "white", "Slide A")
    create_dummy_image(os.path.join(input_dir, "screenshot_0002.png"), "black", "Slide B")

    create_dummy_audio(os.path.join(input_dir, "audio_0000.wav"))
    create_dummy_audio(os.path.join(input_dir, "audio_0001.wav"))
    create_dummy_audio(os.path.join(input_dir, "audio_0002.wav"))

    # Mock AudioTranscriber
    mock_transcribe = MagicMock()
    mock_transcribe.side_effect = lambda path: {
        "audio_0000.wav": "Hello and welcome.",
        "audio_0001.wav": "Slide A detail.",
        "audio_0002.wav": "Slide B detail."
    }[os.path.basename(path)]
    monkeypatch.setattr("src.process.processor.AudioTranscriber.transcribe", mock_transcribe)

    # Mock ImageComparator
    mock_ssim = MagicMock()
    mock_ssim.side_effect = lambda p1, p2: {
        ("screenshot_0000.png", "screenshot_0001.png"): 0.98,
        ("screenshot_0000.png", "screenshot_0002.png"): 0.10,
    }.get((os.path.basename(p1), os.path.basename(p2)), 0.0)
    monkeypatch.setattr("src.process.processor.ImageComparator.calculate_ssim", mock_ssim)

    # Run processor with LLM skipped
    processor = SessionProcessor(
        input_dir=input_dir,
        output_dir=output_dir,
        threshold=0.95,
        model_size="base",
        skip_llm=True
    )
    processor.process()

    assert os.path.exists(os.path.join(output_dir, "session_slide_01.png"))
    assert os.path.exists(os.path.join(output_dir, "session_slide_01_transcript.txt"))
    assert os.path.exists(os.path.join(output_dir, "session_slide_02.png"))
    assert os.path.exists(os.path.join(output_dir, "session_slide_02_transcript.txt"))
    assert os.path.exists(os.path.join(output_dir, "session_notes.pdf"))

def test_session_processor_continuous(temp_dirs, monkeypatch):
    """Verifies continuous audio mode: transcribing full audio, mapping segments, and context-aware summarization."""
    input_dir, output_dir = temp_dirs
    prefix = "20260630_180000"

    # Create timestamped screenshots
    create_dummy_image(os.path.join(input_dir, f"{prefix}_part0000.png"), "white", "Slide A")
    create_dummy_image(os.path.join(input_dir, f"{prefix}_part0001.png"), "white", "Slide A")
    create_dummy_image(os.path.join(input_dir, f"{prefix}_part0002.png"), "black", "Slide B")

    # Create continuous audio file and timestamps JSON
    create_dummy_audio(os.path.join(input_dir, f"{prefix}_continuous.wav"))
    
    timestamps_data = [
        {"screenshot": f"{prefix}_part0000.png", "timestamp": 5.0},
        {"screenshot": f"{prefix}_part0001.png", "timestamp": 10.0},
        {"screenshot": f"{prefix}_part0002.png", "timestamp": 15.0}
    ]
    with open(os.path.join(input_dir, f"{prefix}_timestamps.json"), "w") as f:
        json.dump(timestamps_data, f)

    # Mock WhisperModel transcribe to return 3 segments
    mock_whisper_model = MagicMock()
    
    seg1 = MagicMock()
    seg1.start = 2.0
    seg1.text = "Hello and welcome."
    
    seg2 = MagicMock()
    seg2.start = 7.0
    seg2.text = "Slide A detail."
    
    seg3 = MagicMock()
    seg3.start = 12.0
    seg3.text = "Slide B detail."
    
    mock_whisper_model.transcribe.return_value = ([seg1, seg2, seg3], None)
    
    # Inject WhisperModel mock by making _load_model set the instance's model
    def mock_load_model(self_transcriber):
        self_transcriber.model = mock_whisper_model
    monkeypatch.setattr("src.process.processor.AudioTranscriber._load_model", mock_load_model)

    # Mock ImageComparator
    mock_ssim = MagicMock()
    mock_ssim.side_effect = lambda p1, p2: {
        (f"{prefix}_part0000.png", f"{prefix}_part0001.png"): 0.98,
        (f"{prefix}_part0000.png", f"{prefix}_part0002.png"): 0.10,
    }.get((os.path.basename(p1), os.path.basename(p2)), 0.0)
    monkeypatch.setattr("src.process.processor.ImageComparator.calculate_ssim", mock_ssim)

    # Mock OpenAINotesGenerator
    mock_notes_generator = MagicMock()
    # Return custom pointwise notes dictionary
    mock_notes_generator.generate_notes.return_value = {
        1: "Notes for Slide 1:\n- Hello and welcome.\n  * Slide A detail.",
        2: "Notes for Slide 2:\n- Slide B detail."
    }
    
    # Inject OpenAINotesGenerator mock
    monkeypatch.setenv("OPENAI_API_KEY", "mock_key")
    monkeypatch.setattr("src.process.processor.OpenAINotesGenerator", lambda model, temperature: mock_notes_generator)

    # Run processor
    processor = SessionProcessor(
        input_dir=input_dir,
        output_dir=output_dir,
        threshold=0.95,
        model_size="base",
        llm_model="gpt-4o-mini",
        skip_llm=False
    )
    processor.process()

    # Check generated files
    assert os.path.exists(os.path.join(output_dir, f"{prefix}_slide_01.png"))
    assert os.path.exists(os.path.join(output_dir, f"{prefix}_slide_01_transcript.txt"))
    assert os.path.exists(os.path.join(output_dir, f"{prefix}_slide_01_notes.txt"))
    assert os.path.exists(os.path.join(output_dir, f"{prefix}_slide_02.png"))
    assert os.path.exists(os.path.join(output_dir, f"{prefix}_slide_02_transcript.txt"))
    assert os.path.exists(os.path.join(output_dir, f"{prefix}_slide_02_notes.txt"))
    assert os.path.exists(os.path.join(output_dir, f"{prefix}_notes.pdf"))

    # Verify notes generator was called with the combined transcripts list
    mock_notes_generator.generate_notes.assert_called_once_with([
        "Hello and welcome.\n\nSlide A detail.",
        "Slide B detail."
    ])

    # Verify notes file content
    with open(os.path.join(output_dir, f"{prefix}_slide_01_notes.txt"), "r") as f:
        notes_content = f.read()
        assert "Notes for Slide 1:" in notes_content
        assert "Slide A detail." in notes_content

def test_openai_notes_parsing(monkeypatch):
    """Verifies that the regex parser in OpenAINotesGenerator splits the LLM response correctly."""
    # Mock the OpenAI client response
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    
    mock_message.content = """
    Some introductory text we want to ignore.
    
    [SLIDE 1]
    - Note 1
      * Detail 1
      
    [slide 2]
    - Note 2
      * Detail 2
      
    [SLIDE 03]
    - Note 3
      * Detail 3
    """
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    
    monkeypatch.setenv("OPENAI_API_KEY", "mock_key")
    generator = OpenAINotesGenerator(model="gpt-4o-mini")
    # Inject the mock client
    generator.client = mock_client
    
    notes_map = generator.generate_notes(["trans 1", "trans 2", "trans 3"])
    
    assert len(notes_map) == 3
    assert notes_map[1] == "- Note 1\n      * Detail 1"
    assert notes_map[2] == "- Note 2\n      * Detail 2"
    assert notes_map[3] == "- Note 3\n      * Detail 3"

def test_pdf_generator_quality(temp_dirs):
    """Verifies that PDFGenerator successfully builds a PDF with image compression enabled."""
    input_dir, output_dir = temp_dirs
    from src.process.pdf_generator import PDFGenerator
    
    img_path = os.path.join(input_dir, "slide.png")
    create_dummy_image(img_path, "white", "Slide Content")
    
    pdf_path = os.path.join(output_dir, "output.pdf")
    slides = [{"image_path": img_path, "notes": "Notes for Slide 1"}]
    
    generator = PDFGenerator()
    generator.generate_pdf(slides, pdf_path, image_quality=80)
    
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 0

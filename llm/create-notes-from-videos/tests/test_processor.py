import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock
from PIL import Image, ImageDraw
import numpy as np

from src.process.comparator import ImageComparator
from src.process.processor import SessionProcessor

@pytest.fixture
def temp_dirs():
    """Creates temporary directories for input and output."""
    input_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    yield input_dir, output_dir
    shutil.rmtree(input_dir)
    shutil.rmtree(output_dir)

def create_dummy_image(path: str, color: str = "white", text: str = "") -> None:
    """Helper to create a dummy image with optional text."""
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

    # Create identical and different images
    create_dummy_image(img1_path, "white")
    create_dummy_image(img2_path, "white")
    create_dummy_image(img3_path, "black")

    comparator = ImageComparator()

    # Identical images should have SSIM of 1.0
    ssim_identical = comparator.calculate_ssim(img1_path, img2_path)
    assert pytest.approx(ssim_identical, abs=1e-4) == 1.0

    # Different images should have SSIM < 1.0
    ssim_different = comparator.calculate_ssim(img1_path, img3_path)
    assert ssim_different < 0.9

def test_session_processor(temp_dirs, monkeypatch):
    input_dir, output_dir = temp_dirs

    # Create 3 screenshots and 3 audio files
    # Slide 0 and Slide 1 will be similar (same slide)
    # Slide 2 will be different (new slide)
    create_dummy_image(os.path.join(input_dir, "screenshot_0000.png"), "white", "Slide A")
    create_dummy_image(os.path.join(input_dir, "screenshot_0001.png"), "white", "Slide A")  # Similar
    create_dummy_image(os.path.join(input_dir, "screenshot_0002.png"), "black", "Slide B")  # Different

    create_dummy_audio(os.path.join(input_dir, "audio_0000.wav"))
    create_dummy_audio(os.path.join(input_dir, "audio_0001.wav"))
    create_dummy_audio(os.path.join(input_dir, "audio_0002.wav"))

    # Mock AudioTranscriber.transcribe
    mock_transcribe = MagicMock()
    mock_transcribe.side_effect = lambda path: {
        "audio_0000.wav": "Hello and welcome to the tutorial.",
        "audio_0001.wav": "In this section we will discuss slide A.",
        "audio_0002.wav": "Now let's move on to slide B."
    }[os.path.basename(path)]
    monkeypatch.setattr("src.process.processor.AudioTranscriber.transcribe", mock_transcribe)

    # Mock ImageComparator.calculate_ssim
    mock_ssim = MagicMock()
    mock_ssim.side_effect = lambda p1, p2: {
        # Comparing screenshot_0000 and screenshot_0001 (similar)
        ("screenshot_0000.png", "screenshot_0001.png"): 0.98,
        # Comparing screenshot_0000 and screenshot_0002 (different)
        ("screenshot_0000.png", "screenshot_0002.png"): 0.10,
    }.get((os.path.basename(p1), os.path.basename(p2)), 0.0)
    monkeypatch.setattr("src.process.processor.ImageComparator.calculate_ssim", mock_ssim)

    # Run processor
    processor = SessionProcessor(
        input_dir=input_dir,
        output_dir=output_dir,
        threshold=0.95,
        model_size="base"
    )
    processor.process()

    # We expect 2 final slides:
    # slide_01.png (screenshot_0000.png) with transcripts of audio_0000 and audio_0001 merged.
    # slide_02.png (screenshot_0002.png) with transcript of audio_0002.
    
    assert os.path.exists(os.path.join(output_dir, "slide_01.png"))
    assert os.path.exists(os.path.join(output_dir, "slide_01.txt"))
    assert os.path.exists(os.path.join(output_dir, "slide_02.png"))
    assert os.path.exists(os.path.join(output_dir, "slide_02.txt"))
    assert not os.path.exists(os.path.join(output_dir, "slide_03.png"))

    # Verify transcripts
    with open(os.path.join(output_dir, "slide_01.txt"), "r") as f:
        content_1 = f.read()
        assert "Hello and welcome to the tutorial." in content_1
        assert "In this section we will discuss slide A." in content_1

    with open(os.path.join(output_dir, "slide_02.txt"), "r") as f:
        content_2 = f.read()
        assert "Now let's move on to slide B." in content_2
        assert "slide A" not in content_2

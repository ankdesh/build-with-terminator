import logging
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

class ImageComparator:
    """Compares two screenshots to determine their structural similarity (SSIM)."""

    def calculate_ssim(self, image_path_1: str, image_path_2: str) -> float:
        """Calculates the Structural Similarity Index (SSIM) between two images.

        Args:
            image_path_1: Path to the first image.
            image_path_2: Path to the second image.

        Returns:
            A float between -1.0 and 1.0 representing the similarity (1.0 means identical).
        """
        try:
            # Load images and convert to grayscale for SSIM
            img1 = Image.open(image_path_1).convert("L")
            img2 = Image.open(image_path_2).convert("L")

            # Handle size differences by resizing the second image to match the first
            if img1.size != img2.size:
                logger.warning(
                    f"Image sizes differ: {image_path_1} ({img1.size}) vs {image_path_2} ({img2.size}). "
                    f"Resizing second image to match."
                )
                img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)

            arr1 = np.array(img1)
            arr2 = np.array(img2)

            # Calculate SSIM
            score = ssim(arr1, arr2)
            logger.debug(f"SSIM between {image_path_1} and {image_path_2}: {score:.4f}")
            return float(score)

        except Exception as e:
            logger.error(f"Failed to calculate SSIM between {image_path_1} and {image_path_2}: {e}")
            # If comparison fails, return 0.0 (totally different) to avoid incorrect merging
            return 0.0

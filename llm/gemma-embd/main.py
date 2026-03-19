import torch
from transformers import AutoProcessor, AutoModel
from PIL import Image
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Extract SigLIP image embeddings and compare with a cropped version.")
    parser.add_argument("image_path", help="Path to the input image file")
    args = parser.parse_args()

    print(f"Loading image from {args.image_path}...")
    try:
        image = Image.open(args.image_path).convert("RGB")
    except Exception as e:
        print(f"Error loading image: {e}")
        sys.exit(1)

    print("Loading Google SigLIP model (used in Gemma 3 / PaliGemma)...")
    model_id = "google/siglip-base-patch16-224"
    
    # Load model and processor
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id)
    
    print(f"Original image size: {image.size}")
    
    # Create a cropped version of the image (e.g., cropping out the center)
    width, height = image.size
    left = width / 4
    top = height / 4
    right = 3 * width / 4
    bottom = 3 * height / 4
    cropped_image = image.crop((left, top, right, bottom))
    
    print(f"Cropped image size: {cropped_image.size}")
    
    # Save the images for verification
    image.save("original_sample.jpg")
    cropped_image.save("cropped_sample.jpg")
    print("Saved 'original_sample.jpg' and 'cropped_sample.jpg'")
    
    print("Extracting embeddings...")
    # Process both images
    inputs_original = processor(images=image, return_tensors="pt")
    inputs_cropped = processor(images=cropped_image, return_tensors="pt")
    
    # Get embeddings using the vision model
    with torch.no_grad():
        features_original = model.get_image_features(**inputs_original).pooler_output
        features_cropped = model.get_image_features(**inputs_cropped).pooler_output
        
    print(f"Original image embedding shape: {features_original.shape}")
    print(f"Cropped image embedding shape: {features_cropped.shape}")
    
    # Calculate cosine similarity to see how different the crop is
    similarity = torch.nn.functional.cosine_similarity(features_original, features_cropped)
    print(f"Cosine similarity between original and cropped image embeddings: {similarity.item():.4f}")

if __name__ == "__main__":
    main()

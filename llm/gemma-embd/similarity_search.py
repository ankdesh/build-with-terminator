import os
import random
import torch
import torch.nn.functional as F
from transformers import AutoProcessor, AutoModel
from PIL import Image

def get_random_crop(image, crop_size):
    width, height = image.size
    # Fallback to copy if crop larger than image
    if width <= crop_size[0] or height <= crop_size[1]:
        return image.copy()
        
    left = random.randint(0, width - crop_size[0])
    top = random.randint(0, height - crop_size[1])
    return image.crop((left, top, left + crop_size[0], top + crop_size[1]))

def main():
    print("Loading Google SigLIP model...")
    model_id = "google/siglip-base-patch16-224"
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id)

    image_dir = "sample_images"
    image_paths = [
        os.path.join(image_dir, f) for f in os.listdir(image_dir) 
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ]
    
    if not image_paths:
        print(f"No original images found in {image_dir}")
        return
        
    print(f"Loading {len(image_paths)} original images...")
    original_images = {}
    original_features = {}
    
    with torch.no_grad():
        for path in image_paths:
            img_name = os.path.basename(path)
            img = Image.open(path).convert("RGB")
            original_images[img_name] = img
            
            inputs = processor(images=img, return_tensors="pt")
            features = model.get_image_features(**inputs).pooler_output
            original_features[img_name] = features
            
    print("Generating 10 random crops...")
    crops = []
    # Generate 10 total crops randomly distributed among the source images
    for i in range(10):
        src_img_name = random.choice(list(original_images.keys()))
        src_img = original_images[src_img_name]
        
        # Choose a random crop size (e.g., between 30% and 60% of original dimensions)
        w, h = src_img.size
        cw, ch = int(w * random.uniform(0.3, 0.6)), int(h * random.uniform(0.3, 0.6))
        
        cropped = get_random_crop(src_img, (cw, ch))
        crops.append({
            "id": f"Crop_{i+1}",
            "source": src_img_name,
            "image": cropped
        })
        
    print("Extracting embeddings for crops and scoring similarity...")
    print("=" * 60)
    
    correct_matches = 0
    with torch.no_grad():
        for crop_info in crops:
            inputs = processor(images=crop_info['image'], return_tensors="pt")
            crop_feature = model.get_image_features(**inputs).pooler_output
            
            print(f"--- {crop_info['id']} (Source Image: {crop_info['source']}) ---")
            
            similarities = {}
            for img_name, orig_feat in original_features.items():
                sim = F.cosine_similarity(crop_feature, orig_feat).item()
                similarities[img_name] = sim
                
            # Sort the comparisons by highest similarity
            sorted_sims = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
            
            # Check if top-1 match is the True source
            if sorted_sims[0][0] == crop_info['source']:
                correct_matches += 1
                
            for img_name, sim in sorted_sims:
                marker = "<-- TRUE SOURCE" if img_name == crop_info['source'] else ""
                print(f"  Similarity vs {img_name}: {sim:.4f} {marker}")
            print()

    print(f"Accuracy: {correct_matches}/10 patches matched to their correct original image.")

if __name__ == "__main__":
    random.seed(42)  # For reproducible random crops
    main()

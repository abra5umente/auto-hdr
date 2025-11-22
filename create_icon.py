from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    size = (64, 64)
    # Dark background
    image = Image.new('RGB', size, color=(20, 20, 20))
    draw = ImageDraw.Draw(image)

    # Gradient-like effect (simple circles)
    draw.ellipse((0, 0, 64, 64), fill=(30, 30, 30), outline=(0, 255, 255), width=2)
    
    # Text "HDR"
    # Try to load a font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()

    text = "HDR"
    
    # Calculate text position to center it
    # getbbox returns (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size[0] - text_width) / 2
    y = (size[1] - text_height) / 2
    
    # Draw text with cyan color
    draw.text((x, y), text, font=font, fill=(0, 255, 255))

    image.save("icon.png")
    print("Icon saved to icon.png")

if __name__ == "__main__":
    create_icon()

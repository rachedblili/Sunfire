import os
import base64
from PIL import Image, ImageOps

# Function to encode the image as base64
def encode_image(image_path: str):
    # check if the image exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

## Example usage
#image_path = 'path/to/your/image.png'
#output_path = 'path/to/your/modified_image.png'
#full_spec = [
#    {"crop": {"x": 75, "y": 0, "width": 1000, "height": 460}},
#    {"scale": {"width": 1920, "height": 1080}},
#    {"pad": {"width": 1920, "height": 1080, "color": "#F2A467"}}
#]
#modify_image(image_path, full_spec, output_path)
def crop_image(image,spec):
    crop_area = (spec["x"], spec["y"], spec["x"] + spec["width"], spec["height"])
    return(image.crop(crop_area))
    
def pad_image(image,spec):
    # Get current size
    w, h = image.size

    # Calculate required padding
    pad_x = (spec['width'] - w) / 2
    pad_y = (spect['height'] - h) / 2

    # Add padding
    padded_image = ImageOps.expand(image, border=(pad_x, pad_y, pad_x, pad_y), fill=spec['color'])

    # Try to fill transparency
    if padded_image.mode in ('RGBA', 'LA') or (padded_image.mode == 'P' and 'transparency' in padded_image.info):
        background = Image.new(padded_image.mode[:-1], padded_image.size, spec['color'])
        background.paste(padded_image, padded_image.split()[-1])  # Paste using alpha channel as mask
        padded_image = background
    return(padded_image)

    
def scale_image(image,spec):
    return(image.resize((spec["width"], spec["height"])))
    
def modify_image(image_path, full_spec, output_path):
    # Open the image
    image = Image.open(image_path)
    for spec in full_spec:
        operation = list(spec.keys())[0]
        if operation == 'crop':
            image = crop_image(image,spec['crop'])
        elif operation == 'scale':
            image = scale_image(image,spec['scale'])
        elif operation == 'pad':
            image = pad_image(image,spec['pad'])
        else:
            print("Unknown operation")
    # Save the modified image
    image.save(output_path)


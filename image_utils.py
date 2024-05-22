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
    pad_y = (spec['height'] - h) / 2

    # Check for non-integer padding and adjust dimensions
    if pad_x % 1 != 0:
        # Adjust width by 1 pixel to make padding an integer
        new_width = w + 1 if w < spec['width'] else w - 1
        image = image.resize((new_width, h), Image.LANCZOS)
        pad_x = (spec['width'] - new_width) / 2

    if pad_y % 1 != 0:
        # Adjust height by 1 pixel to make padding an integer
        new_height = h + 1 if h < spec['height'] else h - 1
        image = image.resize((w, new_height), Image.LANCZOS)
        pad_y = (spec['height'] - new_height) / 2

    # Convert float padding to integer
    pad_x, pad_y = int(pad_x), int(pad_y)
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


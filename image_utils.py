import os
import base64
from PIL import Image, ExifTags, ImageFilter
from pillow_heif import register_heif_opener
import imghdr
from messaging_utils import logger

# Make sure we can open heif files
register_heif_opener()


# Function to encode the image as base64
def encode_image(image_path: str):
    """
    A function that encodes an image file at the specified path to a base64 encoded string.

    Args:
        image_path (str): The path to the image file to be encoded.

    Returns:
        str: The base64 encoded representation of the image file.
    """
    # check if the image exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def rotate_image_according_to_exif(image):
    """
    A function that rotates an image based on its EXIF orientation metadata.

    Args:
        image: The image to be rotated based on its EXIF orientation.

    Returns:
        The rotated image.
    """
    try:
        exif = image._getexif()
        if exif is not None:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break

            if exif[orientation] == 3:
                image = image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image = image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image = image.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError):
        # cases: image doesn't have getexif
        pass
    return image


def hex_to_rgb(hex_color):
    """
    Convert a hexadecimal color string to an RGB tuple.

    Args:
    hex_color (str): Hexadecimal color string (e.g., "#FF5733").

    Returns:
    tuple: A tuple of integers (R, G, B).
    """
    # Remove the '#' character and convert the remaining string to an integer
    hex_color = hex_color.lstrip('#')
    # Convert the hexadecimal string to an integer, and then extract RGB components
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def modify_image(image_path, desired_width, desired_height, pad_color, output_path):
    """
    Modifies an image by resizing it and adding padding to match the desired dimensions. If the image has transparency,
    it will be filled with the specified color. If the image does not have transparency, it will be blurred to create
    extended edges. The modified image is then saved to the specified output path.

    Args:
        image_path (str): The path to the image file.
        desired_width (int): The desired width of the modified image.
        desired_height (int): The desired height of the modified image.
        pad_color (str): The color to use for padding the image, in hexadecimal format (e.g., "#FF5733").
        output_path (str): The path to save the modified image.

    Returns:
        None
    """
    # Open the image
    image = Image.open(image_path)
    # Correct for image orientation based on EXIF data
    image = rotate_image_according_to_exif(image)
    original_width, original_height = image.size

    # Calculate the scaling factor
    scaling_factor = min(desired_width / original_width, desired_height / original_height)
    scaling_factor = min(scaling_factor, 1.5)  # Cap the scaling factor at 1.5

    # Calculate the new size after scaling
    new_width = int(original_width * scaling_factor)
    new_height = int(original_height * scaling_factor)

    # Calculate the position to paste the scaled image
    paste_x = (desired_width - new_width) // 2
    paste_y = (desired_height - new_height) // 2

    # Resize the image
    image = image.resize((new_width, new_height), Image.LANCZOS)
    # Try to fill transparency
    if (image.mode in ('RGBA', 'LA')) or (image.mode == 'P' and 'transparency' in image.info):
        if image.mode in ('RGBA', 'LA'):
            print("Trying to fix transparency in:", image_path)
            base_mode = image.mode[:-1]
            background = Image.new(base_mode, image.size, pad_color)
            background.paste(image, image.split()[-1])  # Paste using alpha channel as mask
            image = background
        elif image.mode == 'P' and 'transparency' in image.info:
            print("Trying to fix transparency in:", image_path)
            image = image.convert("RGBA")
            base_mode = "RGB"
            background = Image.new(base_mode, image.size, pad_color)
            alpha = image.split()[-1]  # Get the alpha channel
            background.paste(image, (0, 0), alpha)  # Use alpha channel as mask
            image = background

        # Create a new image with the desired dimensions
        new_img = Image.new("RGB", (desired_width, desired_height), hex_to_rgb(pad_color))
    else:
        # Blur radius calculation
        blur_radius = ((paste_x + paste_y) // 2) // 4
        blurred_background = image.resize((desired_width, desired_height), Image.LANCZOS).filter(
            ImageFilter.GaussianBlur(blur_radius))

        # Create a new image with extended edges
        new_img = Image.new('RGB', (desired_width, desired_height))
        new_img.paste(blurred_background)

    # Paste the scaled image onto the new image
    new_img.paste(image, (paste_x, paste_y))

    # Save the modified image
    new_img.save(output_path)


def convert_image_to_png(image):
    """
    Converts an input image to PNG format.
    Args:
        image (PIL.Image.Image): An image object opened by Image.open().
    Returns:
        PIL.Image.Image: The converted image in PNG format.
    """
    # Convert the image to PNG format by changing the mode if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # Use BytesIO to simulate saving and reloading the image, ensuring it is in PNG format
    from io import BytesIO
    png_image_io = BytesIO()
    image.save(png_image_io, format='PNG')
    png_image_io.seek(0)
    png_image = Image.open(png_image_io)

    return png_image


def compatible_image_format(image_path):
    allowed_formats = ['png', 'jpeg', 'webp']
    return imghdr.what(image_path) in allowed_formats


def get_platform_specs(platform):
    """
    Return the specifications for a given video platform.

    Args:
    platform (str): The name of the platform.

    Returns:
    tuple: A tuple containing (width, height, aspect_ratio) based on the platform.
    """
    specs = {
        'youtube': (1920, 1080, '16:9'),
        'facebook': (1280, 720, '16:9'),
        'instagram': (1080, 1920, '9:16'),
        'tiktok': (1080, 1920, '9:16'),
        'twitter': (1280, 720, '16:9'),
        'television': (1920, 1080, '16:9'),
        'square': (1080, 1080, '1:1')
    }

    return specs.get(platform, (1920, 1080, '16:9'))

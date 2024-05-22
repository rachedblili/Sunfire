import os
from openai import OpenAI
import logging
import json

logger = logging.getLogger(__name__)

def get_openai_client():
    # Initialize OpenAI client
    OPENAI_API_KEY = os.environ.get('OPENAI_KEY')
    return(OpenAI(api_key=OPENAI_API_KEY))

def describe_and_recommend(client, images,url_maker):
    for image in images:
        print(f"Image: {image['filename']}")
        print(f"S3: {image['s3_key']}")
        # Create pre-signed URL to the S3 objects
        image_url = url_maker(
                'get_object',
                Params={'Bucket': image['bucket'], 'Key': image['s3_key']},
                ExpiresIn=120  # URL expires in 2 minutes
            )
        print(f"URL: {image_url}")
        describe_response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {
                    "role": "system",
                    "content": "You are the assistant. You only answer in pure JSON. Your response will be parsed by a script and should have no formatting characters or extraneous artifacts. This includes newlines and other formatting."
                },
                {
                    "role": "system",
                    "content": "EXPLICIT REQUIREMENT: You only answer in pure JSON. No formatting characters."
                },
                {
                    "role": "system",
                    "content": "EXPLICIT REQUIREMENT: Legal output key names: color, dimensions, height, width, content"
                },
                {
                    "role": "user",
                    "content": "Examine the given image and describe the dominant colour, the dimensions, and content."
                },
                {
                    "role": "assistant",
                    "content": '{"color" : "#DDFFE1", "dimensions" : {"height" : 100, "width" : 200} , "content" : "A beautiful Oak tree in a green field on a sunny day"}'
                },
                {
                    "role": "user",
                    "content": "Examine the given image and describe the dominant colour, the dimensions, and content."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        },
                    ],
                }
            ],
            max_tokens=1500
        )
        descr = json.loads(describe_response.choices[0].message.content)
        image['color'] = descr['color']
        image['height'] = descr['dimensions']['height']
        image['width'] = descr['dimensions']['width']
        image['description'] = descr['content']
        logger.info(f'Received image:{image['description']}')
        strategy_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                    {
                        "role": "system",
                        "content": "You are the assistant. Respond in pure JSON with no formatting characters or extraneous artifacts. Legal output key names: color, x, y, height, width, scale, pad. HARD REQUIREMENT: ensure the proportions of the original image are preserved using symmetrical scaling. Use padding to achieve the desired dimensions. Return the operations (scale, pad) in the correct order. Output should have Standard HD resolution."
                    },
                    {
                        "role": "user",
                        "content": "I have an image with  width 800px and height 530px and the dominant color is #32DF34. I need to fit this image into a video with a 16:9 aspect ratio in Standard HD resolution. Please provide a scaling (while maintaining aspect ratio), and padding recommendation that balances image quality and screen coverage without losing important content."
                    },
                    {
                        "role": "assistant",
                        "content": '[{"scale": {"width": 1600, "height": 1060}}, {"pad": {"width": 1920, "height": 1080, "color": "#32DF34"}}]'
                    },
                    {
                        "role": "user",
                        "content": f"I have an image with width {image['width']} and height {image['height']} and the dominant color is {image['color']}. I need to fit this image into a video with a 16:9 aspect ratio in Standard HD resolution. Please provide a scaling (while maintaining aspect ratio), and padding recommendation that balances image quality and screen coverage without losing important content."
                    }
            ],
            max_tokens=800
        )
        image['strategy'] = json.loads(strategy_response.choices[0].message.content)

    return(images)
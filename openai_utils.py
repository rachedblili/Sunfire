import os
from openai import OpenAI
import json
from messaging_utils import logger


def get_openai_client():
    # Initialize OpenAI client
    return OpenAI(api_key=os.environ.get('OPENAI_KEY'))


def describe_and_recommend(client, images, url_maker):
    for image in images:
        # print(f"Image: {image['filename']}")
        # print(f"S3: {image['s3_key']}")
        # Create pre-signed URL to the S3 objects
        image_url = url_maker(
                'get_object',
                Params={'Bucket': image['bucket'], 'Key': image['s3_key']},
                ExpiresIn=120  # URL expires in 2 minutes
            )
        # print(f"URL: {image_url}")
        describe_response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {
                    "role": "system",
                    "content": "You are the assistant. You only answer in pure JSON. Your response will be parsed by "
                               "a script and should have no formatting characters or extraneous artifacts. This "
                               "includes newlines and other formatting."
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
                    "role": "system",
                    "content": "EXPLICIT REQUIREMENT: COLOR MUST BE IN HEX FORMAT (eg #FF5733)"
                },
                {
                    "role": "user",
                    "content": "Examine the given image and describe the dominant colour, the dimensions, and content."
                },
                {
                    "role": "assistant",
                    "content": '{"color" : "#DDFFE1", "dimensions" : {"height" : 100, "width" : 200} , "content" : "A '
                               'beautiful Oak tree in a green field on a sunny day"}'
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
            max_tokens=800
        )
        descr = json.loads(describe_response.choices[0].message.content)
        image['color'] = descr['color']
        image['height'] = descr['dimensions']['height']
        image['width'] = descr['dimensions']['width']
        image['description'] = descr['content']
        logger('log', f'Received image:{image['description']}')

    return images


def generic_query(client, messages: list, response_type: str = 'txt'):
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=messages,
        max_tokens=800)
    if response_type == 'json':
        return json.loads(response.choices[0].message.content)
    elif response_type == 'txt':
        return response


def create_narration(client, data):
    duration = data['duration']
    images = data['images']
    messages = [{
        "role": "system",
        "content": "You are the assistant. Your job is to be a script writer for short videos. You only respond "
                   "with the text of the requested narration. Your response will be parsed by a script and should "
                   "have no formatting characters or extraneous artifacts. "
    }, {
        "role": "user",
        "content": """
                Please generate a narrative for me.
                
                [General Instructions] 
                The video is 30 seconds long. 
                The narration should start 1 second into the video and finish one second before the end. The speaking 
                rate should be assumed to be 140 words per minute. You should generate a continuous narrative that is 
                simply cognisant of the image on the screen. You do not need to necessarily describe the image, 
                but you should organize your narration to be relevant with what is on the screen, and perhaps point it 
                out if appropriate.

                [HARD REQUIREMENTS] The narrative should fit inside the allotted 28 seconds. That means your 
                narrative must be about 65 words long. DO NOT EXCEED 68 words!"""
    }, {
        "role": "user",
        "content": f"""
                [Overall Topic of the Video]
                {data['topic']}"""
    }]

    # Construct video section
    video_section = ["[Image Sequence, duration and descriptions]"]
    duration_per_image = duration / len(images)
    for i, image in enumerate(images):
        video_section.append(f"{i}. Displayed for {duration_per_image} seconds: {image['description']}")
    video_section.append("\nPlease ensure that the narrative seamlessly aligns with these images.")
    messages.append(
        {
            "role": "user",
            "content": "\n".join(video_section)
        }
    )
    narrative = generic_query(client, messages)
    return narrative

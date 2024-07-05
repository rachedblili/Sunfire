import os
from openai import OpenAI
import json
from messaging_utils import logger


def get_openai_client():
    # Initialize OpenAI client
    return OpenAI(api_key=os.environ.get('OPENAI_KEY'))


def describe_and_recommend(session_id, client, images, url_maker):
    for image in images:

        # Create pre-signed URL to the cloud_storage objects
        image_url = url_maker(
                'get_object',
                Params={'Bucket': image['bucket'], 'Key': image['cloud_storage_key']},
                ExpiresIn=120  # URL expires in 2 minutes
            )
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
                    "content": "INSTRUCTIONS ON COLOR: \n"
                               "  1) For Images with Transparency: Choose a color that would make for a suitable "
                               "background color.  Text in logos should stand out.\n"
                               "  2) For regular Images:  report the colour that would look best for padding the image."
                },
                {
                    "role": "system",
                    "content": "EXPLICIT REQUIREMENT: COLOR MUST BE IN HEX FORMAT (eg #FF5733)"
                },
                {
                    "role": "user",
                    "content": "Examine the given image and describe the color, the dimensions, and content."
                },
                {
                    "role": "assistant",
                    "content": '{"color" : "#DDFFE1", "dimensions" : {"height" : 100, "width" : 200} , "content" : "A '
                               'beautiful Oak tree in a green field on a sunny day"}'
                },
                {
                    "role": "user",
                    "content": "Examine the given image and describe the colour, the dimensions, and content."
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
        logger(session_id, 'log', f'Received image:{image['description']}')

    return images


def generic_query(client, messages: list, response_type: str = 'txt'):
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=messages,
        max_tokens=800)
    content = response.choices[0].message.content

    if response_type == 'json':
        try:
            # Try parsing as JSON if needed, useful if content is expected to be in JSON format sometimes
            return json.loads(content)
        except json.JSONDecodeError:
            # Handle cases where the content isn't valid JSON
            return {'error': 'Content is not valid JSON', 'content': content}
    elif response_type == 'txt':
        # Return content as plain text
        return content


def create_narration(client, session_data):
    duration = session_data['video']['duration']
    if session_data['voice']['speed']:
        syllable_speed = float(session_data['voice']['speed'])
    else:
        syllable_speed = 223.0
    max_syllables = int((syllable_speed/60) * (duration - 1))  # Allow for silence at the ends of the video.
    target_syllables = int(0.92 * max_syllables)  # Aim for about 92% of the words you'd expect
    min_syllables = int(0.85 * max_syllables)  # Aim for about 80% of the words you'd expect
    print(f"Max syllables: {max_syllables}, Target syllables: {target_syllables}, Min syllables: {min_syllables}")
    images = session_data['images']
    messages = [{
        "role": "system",
        "content": "You are the assistant. Your job is to be a script writer for short videos. You only respond "
                   "with the text of the requested narration. Your response will be parsed by a script and should "
                   "have no formatting characters or extraneous artifacts. "
    }, {
        "role": "user",
        "content": f"""
                Please generate a narrative for {session_data['company_name']}.
                
                [General Instructions] 
                The video is {duration} seconds long. 
                The narration should start 1 second into the video and finish one second before the end. The speaking 
                rate should be assumed to be {syllable_speed} syllables per minute.   Base your narrative on the 
                information provided in the "Overall Topic of the Video" section below.  Only use the image descriptions
                to enhance the narrative, not as the primary inspiration for it.

                [HARD REQUIREMENTS] The narrative should fit inside the allotted {duration - 2} seconds. That means your 
                narrative must be about {target_syllables} words long. DO NOT EXCEED {max_syllables} syllables but have 
                at least {min_syllables} syllables!"""
    }, {
        "role": "user",
        "content": f"""
                [Overall Topic of the Video]
                {session_data['topic']}"""
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

    # Fine tune with emphasis and avoids
    if session_data['emphasis'] or session_data['avoid']:
        fine_tuning_section = ["[Additional Instructions]\n"]
        if session_data['emphasis']:
            fine_tuning_section.append(f"The narrative should emphasize the following: {session_data['emphasis']}\n")
        if session_data['avoid']:
            fine_tuning_section.append(f"The narrative should avoid the following: {session_data['avoid']}")
        messages.append(
            {
                "role": "user",
                "content": "\n".join(fine_tuning_section)
            }
        )
    print(messages)
    narrative = generic_query(client, messages)
    return narrative


def generate_music_prompt(client, session_data):
    tone, age_gender = session_data['tone_age_gender'].split(':')
    mood = session_data['mood']
    topic = session_data['audio']['narration_script']
    messages = [{
        "role": "system",
        "content": "You are the assistant. Your job is to be create excellent prompts for other LLMs. Your response "
                   "contain ONLY the requested prompt. Your response will be parsed by a script and should "
                   "have no formatting characters or extraneous artifacts.  It MUST NOT EXCEED 30 words. "
                   "If the specified mood is 'ai', use other context clues to choose the music mood."
    }, {
        "role": "user",
        "content": f"""
                Please generate a prompt that I can use with a music generation LLM to generate a short musical
                piece that will serve as the background music for a promotional video.  The prompt should primarily
                specify genre, vibe and tempo.  Examine the following data and create then return the appropriate
                prompt.
                [DATA]
                Requested mood: {mood} (if 'ai' then use your own judgement)
                Tone: {tone}
                Topic: {topic}
                
                Please keep the prompt to under 30 words and only include tightly worded instructions to the LLM."""
    }]

    prompt = generic_query(client, messages)
    print(f'Music Prompt:{prompt}')

    return prompt
        

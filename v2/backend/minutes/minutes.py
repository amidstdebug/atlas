import os
from dotenv import load_dotenv
from typing import List

from ollama import chat
from ollama import ChatResponse

import anthropic

from .prompts import examples, prompt

def format_transcript(segments: List) -> str:
    """
    Format the transcribed segments into the required format for the prompt.

    Example format:
    speaker0 (10.508, 39.008): If it's not working, it's the back-end...
    """
    formatted_lines = []

    for segment in segments:
        if segment.deprecated:
            continue

        # Format the line as: speaker{label} (start, end): text
        formatted_line = f"{segment.label} ({segment.segment.start:.3f}, {segment.segment.end:.3f}): {segment.text}"
        formatted_lines.append(formatted_line)

    return "\n".join(formatted_lines)

def get_meeting_minutes(
    segments: List, 
    ollama_model: str = "llama3.1:8b-instruct-q8_0",
    anthropic_model: str = "claude-3-7-sonnet-20250219",
    use_anthropic: bool = False
) -> str:
    """
    Generate meeting minutes from transcribed segments.
    
    Args:
        segments: List of transcribed segments
        model: Model name for Ollama (default: "llama3.1:8b-instruct-q8_0")
        use_anthropic: Whether to use Anthropic's Claude instead of Ollama
        
    Returns:
        Generated meeting minutes as a string
    """
    transcript = format_transcript(segments)
    formatted_examples = '\n'.join([f'<example>\n<transcript>{example['transcript']}</transcript>\n<ideal_output>\n{example['ideal_output']}\n</ideal_output>\n</example>' for example in examples])
    formatted_prompt = prompt.format(transcript=transcript, examples=formatted_examples)
    
    if use_anthropic:
        load_dotenv()
        
        anthropic_api_key = os.getenv("ANTHROPIC_TOKEN")
        if not anthropic_api_key:
            raise RuntimeError("ANTHROPIC_TOKEN not found in environment variables")
        
        client = anthropic.Anthropic(api_key=anthropic_api_key)
        
        response = client.beta.messages.create(
            model=anthropic_model,
            max_tokens=20_000,
            thinking={
                "type": "enabled",
                "budget_tokens": 16_000
            },
            messages=[
                {"role": "user", "content": [
                    # {
                    #     "type": "text",
                    #     "text": formatted_examples
                    # },
                    {
                        "type": "text",
                        "text": formatted_prompt
                    },
                ]}
            ],
            betas=["output-128k-2025-02-19"]
        )
        print(response.content)
        
        content = response.content[-1].text
    else:
        response: ChatResponse = chat(
            model=ollama_model, 
            messages=[
                {
                    'role': 'user',
                    'content': formatted_examples,
                },
                {
                    'role': 'user',
                    'content': formatted_prompt,
                }
            ]
        )
        content = response.message.content
    if "<meeting_minutes>" in content and "</meeting_minutes>" in content:
        content = content.split("<meeting_minutes>")[1].split("</meeting_minutes>")[0].strip()
    
    return content
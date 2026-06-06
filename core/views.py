import os
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-pro",
]

def get_gemini_url(model):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def index(request):
    return render(request, 'index.html')


@csrf_exempt
@require_http_methods(["POST"])
def generate_blog(request):
    try:
        data = json.loads(request.body)
        
        if not data.get('topic'):
            return JsonResponse({
                'success': False,
                'error': 'Topic is required'
            }, status=400)
        
        prompt = build_prompt(data)
        last_error = None
        
        for model in GEMINI_MODELS:
            try:
                url = get_gemini_url(model)
                
                response = requests.post(
                    f"{url}?key={GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{
                            "parts": [{"text": prompt}]
                        }],
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 8192,
                            "topP": 0.9,
                            "topK": 40
                        }
                    },
                    timeout=60
                )
                
                response_data = response.json()
                
                if response.status_code == 200:
                    generated_text = response_data['candidates'][0]['content']['parts'][0]['text']
                    return JsonResponse({
                        'success': True,
                        'content': generated_text,
                        'topic': data.get('topic'),
                        'model_used': model
                    })
                
                error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                last_error = error_msg
                
                if 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower():
                    continue
                    
            except Exception as e:
                last_error = str(e)
                continue
        
        return JsonResponse({
            'success': False,
            'error': f'All models failed. Last error: {last_error}'
        }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def build_prompt(data):
    topic = data.get('topic', '')
    audience = data.get('audience', 'general')
    word_count = data.get('word_count', 500)
    outline = data.get('outline', '')
    tone = data.get('tone', 'professional')
    
    tone_descriptions = {
        'professional': 'formal, authoritative, business-appropriate, uses industry terminology, confident and polished',
        'casual': 'conversational, friendly, relaxed, uses everyday language, approachable and warm',
        'enthusiastic': 'energetic, exciting, passionate, uses exclamation points, motivating and vibrant',
        'educational': 'instructive, clear, step-by-step, explanatory, patient and thorough'
    }
    
    tone_desc = tone_descriptions.get(tone, tone_descriptions['professional'])
    
    prompt = f"""Write a detailed blog post about "{topic}".

CRITICAL REQUIREMENTS:
1. EXACT LENGTH: The blog MUST be approximately {word_count} words. Count carefully and aim for {word_count} words (±10% acceptable).
2. TONE: Write in a {tone} tone. This means: {tone_desc}. The entire blog must consistently maintain this tone from start to finish.
3. TOPIC FOCUS: Every paragraph must relate to {topic}. Do NOT write generic filler content.

Additional Requirements:
- Target audience: {audience}
- Format: Use markdown with headers (# ##), bullet points (-), and bold text (**)
- Include a catchy title at the top

"""
    if outline:
        prompt += f"Key points to cover:\n{outline}\n\n"
    
    prompt += f"""Structure:
# [Catchy Title About {topic}]

## Introduction
Hook the reader with something specific about {topic}. Set the {tone} tone immediately.

## What is {topic}?
Explain {topic} clearly for {audience}.

## Why {topic} Matters
Real benefits and impact of {topic}.

## Key Insights About {topic}
- Specific point 1 about {topic}
- Specific point 2 about {topic}
- Specific point 3 about {topic}

## Practical Tips for {topic}
Actionable advice related to {topic}.

## Conclusion
Wrap up with a strong closing thought about {topic} in {tone} style.

WORD COUNT TARGET: {word_count} words. Write naturally but keep this target in mind.
TONE CHECK: Re-read to ensure the tone stays {tone} throughout."""
    
    return prompt
import json
import re
from google import genai
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render


def seo_analyser_page(request):
    return render(request, 'seo_analyser/seo_analyser.html')


@csrf_exempt
@require_http_methods(["POST"])
def analyse_seo(request):
    try:
        body = json.loads(request.body)
        content = body.get('content', '').strip()
        input_type = body.get('input_type', 'text')
        target_keyword = body.get('target_keyword', '').strip()
        meta_title = body.get('meta_title', '').strip()
        meta_description = body.get('meta_description', '').strip()

        if not content:
            return JsonResponse({'success': False, 'error': 'Content is required.'}, status=400)
        if not target_keyword:
            return JsonResponse({'success': False, 'error': 'Target keyword is required.'}, status=400)

        if input_type == 'url':
            content_block = f"URL to analyse: {content}"
        else:
            content_block = content

        prompt = f"""
You are an expert SEO analyst. Analyse the blog content below and return a structured JSON object only (no markdown fences, no extra text).

TARGET KEYWORD: {target_keyword}
META TITLE: {meta_title or '(not provided)'}
META DESCRIPTION: {meta_description or '(not provided)'}

CONTENT:
\"\"\"
{content_block[:8000]}
\"\"\"

Return ONLY valid JSON with this exact structure:
{{
  "score": <integer 0-100>,
  "headline": "<one sentence verdict>",
  "summary": "<2-3 sentence summary of SEO health>",
  "metrics": [
    {{"title": "Keyword Density", "value": <0-100>, "icon": "percent", "icon_class": "icon-blue", "description": "<short description>"}},
    {{"title": "Readability", "value": <0-100>, "icon": "book-open", "icon_class": "icon-green", "description": "<short description>"}},
    {{"title": "Content Length", "value": <0-100>, "icon": "align-left", "icon_class": "icon-amber", "description": "<short description>"}},
    {{"title": "Title & Meta", "value": <0-100>, "icon": "heading", "icon_class": "icon-purple", "description": "<short description>"}},
    {{"title": "Structure", "value": <0-100>, "icon": "list-ul", "icon_class": "icon-pink", "description": "<short description>"}},
    {{"title": "Link Signals", "value": <0-100>, "icon": "link", "icon_class": "icon-cyan", "description": "<short description>"}}
  ],
  "issues": [
    {{"severity": "high|medium|low", "title": "<issue name>", "detail": "<detail>"}}
  ],
  "suggestions": ["<suggestion>"],
  "keywords_found": [{{"word": "<keyword>", "type": "primary|secondary"}}],
  "keywords_missing": ["<keyword>"],
  "full_report": "<detailed markdown report with ## headings — at least 400 words>"
}}
"""

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        raw = response.text.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        data = json.loads(raw)
        data['success'] = True
        return JsonResponse(data)

    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'error': f'Failed to parse AI response: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
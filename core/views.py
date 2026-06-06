import os
import re
import json
import requests
import io
from dotenv import load_dotenv
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER

load_dotenv()  # safe no-op on Vercel

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
]

def get_gemini_url(model):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def index(request):
    return render(request, 'index.html')
def debug_env(request):
    key = os.environ.get('GEMINI_API_KEY', '')
    return JsonResponse({'key_set': bool(key), 'key_preview': key[:6] + '...' if key else 'MISSING'})

@csrf_exempt
@require_http_methods(["POST"])
def generate_blog(request):
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        return JsonResponse({'success': False, 'error': 'API key not configured'}, status=500)
    try:
        data = json.loads(request.body)
        if not data.get('topic'):
            return JsonResponse({'success': False, 'error': 'Topic is required'}, status=400)

        prompt = build_prompt(data)
        last_error = None

        for model in GEMINI_MODELS:
            try:
                url = get_gemini_url(model)
                response = requests.post(
                    f"{url}?key={GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
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

            except Exception as e:
                last_error = str(e)
                continue

        return JsonResponse({'success': False, 'error': f'All models failed. Last error: {last_error}'}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def seo_analyze(request):
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        return JsonResponse({'success': False, 'error': 'API key not configured'}, status=500)
    try:
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        target_keyword = data.get('keyword', data.get('target_keyword', '')).strip()
        meta_title = data.get('meta_title', data.get('title', '')).strip()
        meta_description = data.get('meta_description', '').strip()

        if not content:
            return JsonResponse({'success': False, 'error': 'Content is required'}, status=400)

        if not target_keyword:
            target_keyword = 'AUTO_DETECT'

        seo_prompt = f"""You are an expert SEO analyst. Analyse the blog content below and return a structured JSON object only. No markdown fences, no extra text, just raw JSON.
SCORING GUIDANCE FOR RECOMMENDATIONS:
- If score is 0-40 (poor): Give only 2-3 critical issues that have the biggest impact. Suggestions should focus purely on fixing broken fundamentals.
- If score is 41-70 (medium): Give 3-4 issues focused on what is holding the score back. Suggestions should target specific improvements to reach a high score.
- If score is 71-100 (good): Give 2-3 fine-tuning issues. Suggestions should focus on polishing details to reach a perfect score.
Keep recommendations focused and actionable — quality over quantity.

TARGET KEYWORD: {target_keyword}
If TARGET KEYWORD is AUTO_DETECT, identify the primary keyword/topic from the content first and then perform the SEO analysis based on that topic.
META TITLE: {meta_title or '(not provided)'}
If no meta title or meta description is provided, do not penalize the SEO score for missing metadata.
Evaluate only the content itself.

CONTENT:
{content[:6000]}

Return ONLY this JSON structure with real scores based on the content:
{{
  "score": <integer 0-100>,
  "headline": "<one sentence verdict about the SEO quality>",
  "summary": "<2-3 sentence summary of the SEO health>",
  "metrics": [
    {{"title": "Keyword Density", "value": <0-100>, "icon": "percent", "icon_class": "icon-blue", "description": "<specific finding>"}},
    {{"title": "Readability", "value": <0-100>, "icon": "book-open", "icon_class": "icon-green", "description": "<specific finding>"}},
    {{"title": "Content Length", "value": <0-100>, "icon": "align-left", "icon_class": "icon-amber", "description": "<specific finding>"}},
    {{"title": "Title & Meta", "value": <0-100>, "icon": "heading", "icon_class": "icon-purple", "description": "<specific finding>"}},
    {{"title": "Structure", "value": <0-100>, "icon": "list-ul", "icon_class": "icon-pink", "description": "<specific finding>"}},
    {{"title": "Link Signals", "value": <0-100>, "icon": "link", "icon_class": "icon-cyan", "description": "<specific finding>"}}
  ],
  "issues": [
    {{"severity": "high|medium|low", "title": "<issue>", "detail": "<why it matters and how to fix it>"}}
  ],
  "suggestions": [
    "<actionable suggestion>"
  ],
  "keywords_found": [
    {{"word": "<keyword found in content>", "type": "primary"}}
  ],
  "keywords_missing": ["<related keyword not in content>", "<another missing keyword>"],
}}"""

        last_error = None

        for model in GEMINI_MODELS:
            try:
                url = get_gemini_url(model)
                response = requests.post(
                    f"{url}?key={GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": seo_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "maxOutputTokens": 4096,
                        }
                    },
                    timeout=60
                )

                response_data = response.json()

                if response.status_code == 200:
                    raw = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
                    raw = re.sub(r'```(?:json)?\s*', '', raw)
                    raw = re.sub(r'```', '', raw)
                    raw = raw.strip()
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if match:
                        raw = match.group(0)

                    try:
                        parsed = json.loads(raw)
                        parsed['success'] = True
                        return JsonResponse(parsed)
                    except json.JSONDecodeError:
                        # JSON parsing failed — strip the full_report field which often breaks parsing
                        try:
                            report_match = re.search(r'"full_report"\s*:\s*"(.*?)"\s*[,}]', raw, re.DOTALL)
                            full_report = report_match.group(1) if report_match else ''
                            raw_no_report = re.sub(r'"full_report"\s*:\s*".*?"\s*([,}])', r'"full_report": "See below"\1', raw, flags=re.DOTALL)
                            parsed = json.loads(raw_no_report)
                            parsed['full_report'] = full_report
                            parsed['success'] = True
                            return JsonResponse(parsed)
                        except Exception:
                            return JsonResponse({
                                'success': True,
                                'score': 50,
                                'headline': 'Analysis Complete',
                                'summary': 'SEO analysis completed. See full report below.',
                                'metrics': [
                                    {'title': 'Keyword Density', 'value': 50, 'icon': 'percent', 'icon_class': 'icon-blue', 'description': 'See full report'},
                                    {'title': 'Readability', 'value': 50, 'icon': 'book-open', 'icon_class': 'icon-green', 'description': 'See full report'},
                                    {'title': 'Content Length', 'value': 50, 'icon': 'align-left', 'icon_class': 'icon-amber', 'description': 'See full report'},
                                    {'title': 'Title & Meta', 'value': 50, 'icon': 'heading', 'icon_class': 'icon-purple', 'description': 'See full report'},
                                    {'title': 'Structure', 'value': 50, 'icon': 'list-ul', 'icon_class': 'icon-pink', 'description': 'See full report'},
                                    {'title': 'Link Signals', 'value': 50, 'icon': 'link', 'icon_class': 'icon-cyan', 'description': 'See full report'}
                                ],
                                'issues': [],
                                'suggestions': [],
                                'keywords_found': [],
                                'keywords_missing': [],
                                'full_report': raw
                            })

                last_error = response_data.get('error', {}).get('message', 'Unknown error')

            except Exception as e:
                last_error = str(e)
                continue

        return JsonResponse({'success': False, 'error': f'SEO analysis failed. {last_error}'}, status=500)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def download_pdf(request):
    try:
        data = json.loads(request.body)
        content = data.get('content', '')
        topic = data.get('topic', 'Blog Post')

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                     fontSize=24, spaceAfter=30, alignment=TA_CENTER)
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                       fontSize=16, spaceAfter=12, spaceBefore=12)
        body_style = ParagraphStyle('CustomBody', parent=styles['BodyText'],
                                    fontSize=11, leading=16, spaceAfter=10)

        story = []
        story.append(Paragraph(topic, title_style))
        story.append(Spacer(1, 0.2 * inch))

        for line in content.split('\n'):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.1 * inch))
            elif line.startswith('# '):
                story.append(Paragraph(line[2:], heading_style))
            elif line.startswith('## '):
                story.append(Paragraph(line[3:], heading_style))
            elif line.startswith('### '):
                story.append(Paragraph(line[4:], heading_style))
            elif line.startswith('- '):
                story.append(Paragraph('• ' + line[2:], body_style))
            else:
                line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                line = re.sub(r'\*(.*?)\*', r'<i>\1</i>', line)
                story.append(Paragraph(line, body_style))

        footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
                                      fontSize=8, alignment=TA_CENTER)
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph('Generated by BlogGenAI', footer_style))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{topic.replace(" ", "_")}_blog.pdf"'
        return response

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def build_prompt(data):
    topic = data.get('topic', '')
    audience = data.get('audience', 'general')
    word_count = data.get('word_count', 500)
    outline = data.get('outline', '')
    tone = data.get('tone', 'professional')

    tone_descriptions = {
        'professional': 'formal, authoritative, business-appropriate',
        'casual': 'conversational, friendly, relaxed',
        'enthusiastic': 'energetic, exciting, passionate',
        'educational': 'instructive, clear, step-by-step'
    }

    tone_desc = tone_descriptions.get(tone, tone_descriptions['professional'])

    prompt = f"""Write a detailed blog post about "{topic}".

REQUIREMENTS:
1. LENGTH: Approximately {word_count} words.
2. TONE: {tone} — {tone_desc}
3. Target audience: {audience}
4. Format: Use markdown with headers (# ##), bullet points (-), and bold text (**)

"""
    if outline:
        prompt += f"Key points to cover:\n{outline}\n\n"

    prompt += f"""Structure:
# [Catchy Title About {topic}]

## Introduction
## Main Content
## Key Insights
## Practical Tips
## Conclusion

WORD COUNT TARGET: {word_count} words."""

    return prompt

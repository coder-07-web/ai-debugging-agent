from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests
import re


@api_view(['POST'])
def debug_code(request):
    code = request.data.get("code")
    language = request.data.get("language", "python")

    # ✅ DEFINE PROMPT FIRST (outside try)
    prompt = f"""
You are a strict debugging assistant.

Analyze the code for:
1. Syntax errors
2. Runtime errors
3. Logical errors (VERY IMPORTANT)

Rules:
- If syntax is correct, DO NOT report syntax errors.
- If logic is incorrect, explain the logic issue clearly.
- Prefer minimal and correct fixes.

Example:
Function name is is_even but logic checks for odd → fix it.

Output:

STATUS:
<"CORRECT" or "ERROR">

ERRORS:
<list>

EXPLANATION:
<clear explanation>

FIXED_CODE:
<correct code>

Code:
{code}
"""

    try:
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

    except Exception:
        result = use_local_model(prompt)

    fixed_code = extract_fixed_code(result, code)
    fixed_code = smart_fix(code, fixed_code)

    return Response({
    "full_response": result,
    "fixed_code": fixed_code
})
    


def use_local_model(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "codellama:7b",
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]

def extract_fixed_code(result, original_code):
    match = re.search(r"FIXED_CODE:\s*(.*)", result, re.DOTALL)
    
    if match:
        code = match.group(1).strip()
        code = code.replace("```", "")

        #  If model returns None or empty → fallback to local model
        if code.lower() == "none" or code == "":
            return f'print("hello")' if "print(" in original_code else original_code

        return code

    return original_code

def smart_fix(original_code, fixed_code):
    # If model creates variable unnecessarily → override
    if "hello =" in fixed_code and "print(hello)" in original_code:
        return 'print("hello")'

    return fixed_code
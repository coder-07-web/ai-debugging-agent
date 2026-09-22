from rest_framework.decorators import api_view
from rest_framework.response import Response

import requests
import re
import subprocess
import json
from pathlib import Path


# ============================================================
# MAIN DEBUG API
# ============================================================

@api_view(["POST"])
def debug_code(request):

    code = request.data.get("code", "").strip()
    language = request.data.get("language", "python").strip().lower()

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if not code:
        return Response(
            {
                "error": "Code is required."
            },
            status=400
        )

    if not language:
        language = "python"

    # --------------------------------------------------------
    # Run language-specific validation
    # --------------------------------------------------------

    validation_result = validate_code(code, language)

    # --------------------------------------------------------
    # Create debugging prompt
    # --------------------------------------------------------

    prompt = create_debug_prompt(
        code,
        language,
        validation_result
    )

    # --------------------------------------------------------
    # Try OpenAI first
    # --------------------------------------------------------

    try:

        from openai import OpenAI

        client = OpenAI()

        response = client.chat.completions.create(

            model="gpt-4o-mini",

            temperature=0,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise and reliable "
                        "software debugging assistant. "
                        "Never invent errors."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = response.choices[0].message.content

    # --------------------------------------------------------
    # OpenAI failed -> Ollama fallback
    # --------------------------------------------------------

    except Exception as openai_error:

        try:

            result = use_local_model(prompt)

        except Exception as ollama_error:

            return Response(
                {
                    "error": "Both AI services are unavailable.",
                    "openai_error": str(openai_error),
                    "ollama_error": str(ollama_error)
                },
                status=503
            )

    # --------------------------------------------------------
    # Extract fixed code
    # --------------------------------------------------------

    fixed_code = extract_fixed_code(
        result,
        code
    )

    # --------------------------------------------------------
    # If validator found an actual error,
    # don't allow AI to simply say CORRECT.
    # --------------------------------------------------------

    if validation_result["has_error"]:

        result = build_final_result(
            validation_result,
            result
        )

    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return Response(
        {
            "full_response": result,
            "fixed_code": fixed_code,
            "language": language,
            "validation": validation_result
        }
    )


# ============================================================
# CREATE AI DEBUGGING PROMPT
# ============================================================

def create_debug_prompt(
    code,
    language,
    validation_result
):

    validation_message = validation_result.get(
        "message",
        "No deterministic validation result."
    )

    return f"""
You are a professional software debugging assistant.

The programming language is:

{language}

Analyze ONLY the code provided below.

============================================================
IMPORTANT
============================================================

The code has already been checked by a language-specific
validator where possible.

Validator result:

{validation_message}

Use this information when analyzing the code.

Do not contradict a confirmed validation error unless
there is a clear technical reason.

============================================================
YOUR TASK
============================================================

Check the code for:

1. Syntax errors
2. Runtime errors
3. Undefined variables
4. Undefined functions
5. Invalid function or method calls
6. Type errors
7. Missing imports/includes
8. Invalid API/library usage
9. Incorrect conditions
10. Incorrect loops
11. Incorrect calculations
12. Logical errors
13. Language-specific problems

============================================================
STRICT RULES
============================================================

1. NEVER invent an error.

2. Only report errors that actually exist.

3. Carefully inspect the exact source code.

4. Do NOT assume the code is Python.

5. Use the syntax and semantics of:

{language}

6. Preserve the original purpose of the program.

7. Make the smallest necessary correction.

8. FIXED_CODE must use the SAME programming language.

9. NEVER convert the code to another language.

10. FIXED_CODE must contain ONLY source code.

11. Do not put Markdown code fences inside FIXED_CODE.

12. If the code is correct, return the original code
    as FIXED_CODE.

============================================================
IMPORTANT PYTHON EXAMPLE
============================================================

For Python:

a = rajesh
print(a)

This is NOT an indentation error.

"rajesh" is interpreted as a variable.

If "rajesh" has not been defined, Python raises:

NameError: name 'rajesh' is not defined

If the intention is to store the text "rajesh":

a = "rajesh"
print(a)

============================================================
IMPORTANT JAVASCRIPT EXAMPLE
============================================================

For JavaScript:

let a = 5
consolelog(a)

"consolelog" is not the same as:

console.log

The missing dot causes the function name to be invalid.

The corrected code is:

let a = 5
console.log(a)

============================================================
RESPONSE FORMAT
============================================================

Return exactly:

STATUS:
ERROR or CORRECT

ERRORS:
<actual errors or None>

EXPLANATION:
<clear explanation>

FIXED_CODE:
<complete corrected code>

============================================================
PROGRAMMING LANGUAGE
============================================================

{language}

============================================================
CODE
============================================================

{code}
"""


# ============================================================
# LANGUAGE VALIDATION
# ============================================================

def validate_code(code, language):

    # --------------------------------------------------------
    # Python
    # --------------------------------------------------------

    if language in ["python", "py"]:
        return validate_python(code)

    # --------------------------------------------------------
    # JavaScript
    # --------------------------------------------------------

    if language in ["javascript", "js"]:
        return validate_javascript(
            code,
            "code.js"
        )

    # --------------------------------------------------------
    # TypeScript
    # --------------------------------------------------------

    if language in ["typescript", "ts"]:
        return validate_javascript(
            code,
            "code.ts"
        )

    # --------------------------------------------------------
    # Java
    # --------------------------------------------------------

    if language in ["java"]:
        return validate_java(code)

    # --------------------------------------------------------
    # Other languages
    # --------------------------------------------------------

    return {
        "has_error": False,
        "message": (
            f"No deterministic validator is configured "
            f"for {language}. AI analysis will be used."
        )
    }


# ============================================================
# PYTHON VALIDATION
# ============================================================

def validate_python(code):

    import ast
    import builtins

    # --------------------------------------------------------
    # STEP 1: Check Python syntax
    # --------------------------------------------------------

    try:

        tree = ast.parse(code)

    except SyntaxError as error:

        return {
            "has_error": True,
            "message": (
                f"Python {type(error).__name__}: "
                f"{error.msg} "
                f"at line {error.lineno}, "
                f"column {error.offset}"
            )
        }

    # --------------------------------------------------------
    # STEP 2: Find names that are defined
    # --------------------------------------------------------

    defined_names = set(dir(builtins))

    # Add common Python constants
    defined_names.update({
        "True",
        "False",
        "None",
        "__name__",
        "__file__"
    })

    # --------------------------------------------------------
    # STEP 3: Find imported names
    # --------------------------------------------------------

    for node in ast.walk(tree):

        # import math
        if isinstance(node, ast.Import):

            for alias in node.names:

                if alias.asname:
                    defined_names.add(alias.asname)

                else:
                    defined_names.add(
                        alias.name.split(".")[0]
                    )

        # from math import sqrt
        elif isinstance(node, ast.ImportFrom):

            for alias in node.names:

                if alias.asname:
                    defined_names.add(alias.asname)

                else:
                    defined_names.add(alias.name)

    # --------------------------------------------------------
    # STEP 4: Find variables/functions/classes that are
    # explicitly defined
    # --------------------------------------------------------

    for node in ast.walk(tree):

        # x = 10
        if isinstance(node, ast.Name):

            if isinstance(node.ctx, ast.Store):

                defined_names.add(node.id)

        # def my_function():
        elif isinstance(node, (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef
        )):

            defined_names.add(node.name)

            # Function parameters
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            ):

                for arg in node.args.args:
                    defined_names.add(arg.arg)

                for arg in node.args.kwonlyargs:
                    defined_names.add(arg.arg)

                if node.args.vararg:
                    defined_names.add(
                        node.args.vararg.arg
                    )

                if node.args.kwarg:
                    defined_names.add(
                        node.args.kwarg.arg
                    )

    # --------------------------------------------------------
    # STEP 5: Find variables that are READ but never defined
    # --------------------------------------------------------

    undefined_names = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Name):

            if isinstance(node.ctx, ast.Load):

                if node.id not in defined_names:

                    if node.id not in undefined_names:

                        undefined_names.append(
                            node.id
                        )

    # --------------------------------------------------------
    # STEP 6: Undefined variable found
    # --------------------------------------------------------

    if undefined_names:

        errors = []

        for name in undefined_names:

            errors.append(
                f"NameError: name '{name}' "
                f"is not defined"
            )

        return {
            "has_error": True,

            "message": (
                "Python static analysis found:\n"
                + "\n".join(errors)
            )
        }

    # --------------------------------------------------------
    # STEP 7: No syntax or undefined-name errors
    # --------------------------------------------------------

    return {
        "has_error": False,

        "message": (
            "Python syntax and undefined-name "
            "validation passed."
        )
    }


# ============================================================
# JAVASCRIPT / TYPESCRIPT VALIDATION
# ============================================================

def validate_javascript(
    code,
    filename="code.js"
):

    try:

        # ----------------------------------------------------
        # Find frontend directory
        # ----------------------------------------------------

        current_file = Path(__file__).resolve()

        possible_frontend_paths = [

            current_file.parents[2] / "frontend",

            current_file.parents[1] / "frontend",

            current_file.parents[3] / "frontend",

            Path.cwd() / "frontend"

        ]

        frontend_path = None

        for path in possible_frontend_paths:

            if path.exists():

                frontend_path = path
                break

        # ----------------------------------------------------
        # Frontend not found
        # ----------------------------------------------------

        if frontend_path is None:

            return {
                "has_error": False,
                "message": (
                    "Frontend directory was not found. "
                    "AI analysis will be used."
                )
            }

        # ----------------------------------------------------
        # Find ESLint
        # ----------------------------------------------------

        eslint_path = (
            frontend_path
            / "node_modules"
            / ".bin"
            / "eslint.cmd"
        )

        if not eslint_path.exists():

            return {
                "has_error": False,
                "message": (
                    "ESLint is not installed in the "
                    "frontend. AI analysis will be used."
                )
            }

        # ----------------------------------------------------
        # Run ESLint
        # ----------------------------------------------------

        process = subprocess.run(

            [
                str(eslint_path),
                "--stdin",
                "--stdin-filename",
                filename,
                "-f",
                "json"
            ],

            input=code,

            text=True,

            capture_output=True,

            timeout=15,

            cwd=str(frontend_path)
        )

        # ----------------------------------------------------
        # Parse ESLint result
        # ----------------------------------------------------

        if not process.stdout.strip():

            return {
                "has_error": False,
                "message": (
                    "JavaScript validation completed "
                    "without reported errors."
                )
            }

        try:

            eslint_result = json.loads(
                process.stdout
            )

        except json.JSONDecodeError:

            return {
                "has_error": False,
                "message": (
                    "ESLint returned an unreadable result. "
                    "AI analysis will be used."
                )
            }

        # ----------------------------------------------------
        # Extract errors
        # ----------------------------------------------------

        errors = []

        for file_result in eslint_result:

            for message in file_result.get(
                "messages",
                []
            ):

                severity = message.get(
                    "severity",
                    1
                )

                # 2 = ESLint error
                if severity == 2:

                    line = message.get(
                        "line",
                        "?"
                    )

                    column = message.get(
                        "column",
                        "?"
                    )

                    error_message = message.get(
                        "message",
                        "Unknown error"
                    )

                    errors.append(
                        f"Line {line}, "
                        f"Column {column}: "
                        f"{error_message}"
                    )

        # ----------------------------------------------------
        # Errors found
        # ----------------------------------------------------

        if errors:

            return {
                "has_error": True,
                "message": (
                    "JavaScript static analysis found:\n"
                    + "\n".join(errors)
                )
            }

        # ----------------------------------------------------
        # No errors
        # ----------------------------------------------------

        return {
            "has_error": False,
            "message": (
                "JavaScript static analysis "
                "found no errors."
            )
        }

    except subprocess.TimeoutExpired:

        return {
            "has_error": False,
            "message": (
                "JavaScript validation timed out. "
                "AI analysis will be used."
            )
        }

    except Exception as error:

        return {
            "has_error": False,
            "message": (
                f"JavaScript validation could not run: "
                f"{error}. AI analysis will be used."
            )
        }

# ============================================================
# JAVA VALIDATION
# ============================================================

def validate_java(code):

    import tempfile
    import os

    temp_dir = None
    java_file = None

    try:

        # ----------------------------------------------------
        # Create temporary directory
        # ----------------------------------------------------

        temp_dir = tempfile.mkdtemp()

        java_file = os.path.join(
            temp_dir,
            "Main.java"
        )

        # ----------------------------------------------------
        # Write source code
        # ----------------------------------------------------

        with open(
            java_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(code)

        # ----------------------------------------------------
        # Compile only
        #
        # -proc:none disables annotation processing.
        # We are NOT executing the user's Java program.
        # ----------------------------------------------------

        process = subprocess.run(

            [
                "javac",
                "-proc:none",
                java_file
            ],

            text=True,

            capture_output=True,

            timeout=15
        )

        # ----------------------------------------------------
        # Compilation error
        # ----------------------------------------------------

        if process.returncode != 0:

            error_output = (
                process.stderr.strip()
                or process.stdout.strip()
            )

            return {
                "has_error": True,

                "message": (
                    "Java compiler found an error:\n"
                    + error_output
                )
            }

        # ----------------------------------------------------
        # Compilation successful
        # ----------------------------------------------------

        return {
            "has_error": False,

            "message": (
                "Java compilation validation passed."
            )
        }

    except FileNotFoundError:

        return {
            "has_error": False,

            "message": (
                "javac was not found on the system. "
                "AI analysis will be used for Java."
            )
        }

    except subprocess.TimeoutExpired:

        return {
            "has_error": False,

            "message": (
                "Java compilation validation timed out. "
                "AI analysis will be used."
            )
        }

    except Exception as error:

        return {
            "has_error": False,

            "message": (
                f"Java validation could not run: "
                f"{error}. AI analysis will be used."
            )
        }

    finally:

        # ----------------------------------------------------
        # Clean temporary Java files
        # ----------------------------------------------------

        if temp_dir:

            import shutil

            try:
                shutil.rmtree(temp_dir)

            except Exception:
                pass
# ============================================================
# OLLAMA LOCAL MODEL
# ============================================================

def use_local_model(prompt):

    response = requests.post(

        "http://localhost:11434/api/generate",

        json={
            "model": "codellama:7b",
            "prompt": prompt,
            "stream": False,

            "options": {
                "temperature": 0
            }
        },

        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "response",
        ""
    )


# ============================================================
# EXTRACT FIXED CODE
# ============================================================

def extract_fixed_code(
    result,
    original_code
):

    if not result:

        return original_code

    match = re.search(
        r"FIXED_CODE\s*:\s*(.*)",
        result,
        re.IGNORECASE | re.DOTALL
    )

    if not match:

        return original_code

    fixed_code = match.group(1).strip()

    # --------------------------------------------------------
    # Remove Markdown code fences
    # --------------------------------------------------------

    fixed_code = re.sub(
        r"^```[a-zA-Z0-9_+#.-]*\s*",
        "",
        fixed_code
    )

    fixed_code = re.sub(
        r"\s*```$",
        "",
        fixed_code
    )

    fixed_code = fixed_code.strip()

    # --------------------------------------------------------
    # AI returned no replacement
    # --------------------------------------------------------

    if fixed_code.lower() in [
        "none",
        "null",
        "n/a"
    ]:

        return original_code

    if not fixed_code:

        return original_code

    return fixed_code


# ============================================================
# BUILD FINAL RESULT
# ============================================================

def build_final_result(
    validation_result,
    ai_result
):

    return f"""
STATUS:
ERROR

ERRORS:
{validation_result["message"]}

EXPLANATION:
The language-specific validator detected an issue in the code.

AI ANALYSIS:
{ai_result}
""".strip()
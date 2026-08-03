"""
tools/calculator.py — Real arithmetic, computed by Python, never by an LLM.

Small local LLMs (see OLLAMA_MODEL in .env) hallucinate numbers on even
simple arithmetic — the same question asked three times can produce three
different wrong answers. This module is the fix: `calculate()` evaluates a
math expression with a strict, whitelist-only AST walker (never `eval()` —
no names, no attribute access, no imports, no arbitrary code execution is
even reachable), and `extract_math_expression()` pulls a clean expression
out of natural language ("what is 1000+290/22" -> "1000+290/22"). Callers
(see core/agent.py) pass the real computed result to the LLM only to be
*narrated* in Ultron's voice — the LLM is never trusted to produce the
number itself.

Examples:
    >>> calculate("1000+290/22")
    {"success": True, "result": 1013.181818, "error": None, "expression": "1000+290/22"}
    >>> calculate("(3+4)*2")
    {"success": True, "result": 14, "error": None, "expression": "(3+4)*2"}
    >>> calculate("sqrt(144)")
    {"success": True, "result": 12, "error": None, "expression": "sqrt(144)"}
    >>> calculate("factorial(5)")
    {"success": True, "result": 120, "error": None, "expression": "factorial(5)"}
    >>> calculate("5/0")
    {"success": False, "result": None, "error": "Division by zero.", "expression": "5/0"}

    >>> extract_math_expression("what is 1000+290/22")
    "1000+290/22"
    >>> extract_math_expression("what is 5 plus 3 times 2")
    "5+3*2"
    >>> extract_math_expression("square root of 144")
    "sqrt(144)"
    >>> extract_math_expression("call me at 555-1234")
    None
"""

import ast
import logging
import math
import operator
import re
from typing import Any, Optional

log = logging.getLogger(__name__)


class _UnsafeExpression(Exception):
    """Raised internally when an expression contains anything outside the
    strict whitelist below — never escapes calculate()."""


# ── Whitelist: the ONLY operators/functions this evaluator will ever run ──────

_ALLOWED_BINOPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARYOPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_MAX_FACTORIAL_ARG = 10_000   # guards against a hang/memory blowup, not a security hole
_MAX_POW_EXPONENT = 1_000     # same — int**int has no upper bound otherwise


def _safe_factorial(n: float) -> int:
    if isinstance(n, float) and not n.is_integer():
        raise _UnsafeExpression("factorial() requires a whole number")
    n_int = int(n)
    if n_int < 0:
        raise _UnsafeExpression("factorial() requires a non-negative number")
    if n_int > _MAX_FACTORIAL_ARG:
        raise _UnsafeExpression(f"factorial() argument too large (max {_MAX_FACTORIAL_ARG})")
    return math.factorial(n_int)


_ALLOWED_FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "factorial": _safe_factorial,
    "pow": pow,
}


# ── AST validation (structure only — never evaluates) ─────────────────────────

def _validate_ast(node: ast.AST) -> None:
    """Raise _UnsafeExpression if *node* contains anything outside the
    whitelist. Purely structural — does not evaluate/execute anything, so
    it's safe to use on user input before deciding whether to run it."""
    if isinstance(node, ast.Expression):
        _validate_ast(node.body)
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
            raise _UnsafeExpression(f"Unsupported constant: {node.value!r}")
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in _ALLOWED_BINOPS:
            raise _UnsafeExpression(f"Operator not allowed: {type(node.op).__name__}")
        if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant):
            if abs(node.right.value) > _MAX_POW_EXPONENT:
                raise _UnsafeExpression(f"Exponent too large (max {_MAX_POW_EXPONENT})")
        _validate_ast(node.left)
        _validate_ast(node.right)
    elif isinstance(node, ast.UnaryOp):
        if type(node.op) not in _ALLOWED_UNARYOPS:
            raise _UnsafeExpression(f"Unary operator not allowed: {type(node.op).__name__}")
        _validate_ast(node.operand)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
            raise _UnsafeExpression("Function not allowed")
        if node.keywords:
            raise _UnsafeExpression("Keyword arguments not allowed")
        for arg in node.args:
            _validate_ast(arg)
    else:
        raise _UnsafeExpression(f"Disallowed expression element: {type(node).__name__}")


def _eval_ast(node: ast.AST) -> float:
    """Evaluate *node*, which must already have passed _validate_ast()."""
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp):
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.Call):
        args = [_eval_ast(a) for a in node.args]
        return _ALLOWED_FUNCTIONS[node.func.id](*args)
    raise _UnsafeExpression(f"Disallowed expression element: {type(node).__name__}")


def _is_parseable(expression: str) -> bool:
    """True if *expression* is syntactically a safe, whitelisted expression
    (does NOT evaluate it — a division-by-zero expression is still
    'parseable', it just fails later at calculate() time)."""
    try:
        tree = ast.parse(expression, mode="eval")
        _validate_ast(tree)
    except (SyntaxError, ValueError, _UnsafeExpression):
        return False
    return True


# ── Public: calculate() ────────────────────────────────────────────────────────

def _format_result(value: float) -> float:
    """Whole numbers -> int (1013 not 1013.0); otherwise round to 6 decimal
    places to avoid float artifacts like 1013.1799999999998."""
    if isinstance(value, int):
        return value
    if value == int(value):
        return int(value)
    return round(value, 6)


def calculate(expression: str) -> dict:
    """
    Safely evaluate a pure arithmetic expression. NEVER uses eval() — parses
    to an AST and only executes whitelisted operators/functions (+ - * / //
    % ** parentheses, unary +/-, and sqrt/abs/round/min/max/factorial/pow).

    Returns:
        {"success": bool, "result": int | float | None, "error": str | None,
         "expression": str}
    """
    cleaned = (expression or "").strip()
    if not cleaned:
        return {"success": False, "result": None, "error": "Empty expression.", "expression": expression}

    try:
        tree = ast.parse(cleaned, mode="eval")
        _validate_ast(tree)
        raw_result = _eval_ast(tree)
    except ZeroDivisionError:
        return {"success": False, "result": None, "error": "Division by zero.", "expression": expression}
    except _UnsafeExpression as err:
        return {"success": False, "result": None, "error": f"Invalid expression: {err}", "expression": expression}
    except (SyntaxError, ValueError, TypeError) as err:
        return {"success": False, "result": None, "error": f"Could not parse expression: {err}", "expression": expression}
    except OverflowError:
        return {"success": False, "result": None, "error": "Result too large to compute.", "expression": expression}
    except RecursionError:
        return {"success": False, "result": None, "error": "Expression too complex.", "expression": expression}

    if isinstance(raw_result, complex):
        return {"success": False, "result": None, "error": "Result is a complex number, not supported.", "expression": expression}
    if isinstance(raw_result, float) and (math.isinf(raw_result) or math.isnan(raw_result)):
        return {"success": False, "result": None, "error": "Result is not a finite number.", "expression": expression}

    return {"success": True, "result": _format_result(raw_result), "error": None, "expression": expression}


# ── Public: extract_math_expression() ──────────────────────────────────────────
# Turns natural language into a clean expression string calculate() can run.
# Deliberately conservative: returns None rather than guessing on ambiguous
# text (phone numbers, dates) that superficially looks like "digits +
# operator + digits" the same way arithmetic does.

_PHONE_LIKE = re.compile(r"\b\d{3}-\d{3,4}(?:-\d{4})?\b")
_DATE_LIKE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")

_STRONG_MATH_FRAMING = re.compile(
    r"\bwhat is \d|\bwhat'?s \d|\bcalculate\b|\bsolve\b|\bcompute\b|"
    r"\bhow much is\b|\bwork out\b|\bsquare root\b|\bsqrt\b|\bsquared\b|\bcubed\b|"
    r"\bfactorial\b|\bplus\b|\bminus\b|\btimes\b|\bmultiplied by\b|\bdivided by\b|"
    r"\bwhat'?s the (result|answer|value) of\b|\bwhat is the (result|answer|value) of\b",
    re.IGNORECASE,
)

# Word-based functions -> Python call syntax. Applied before word-operators
# and filler stripping so e.g. "square root of 144" becomes "sqrt(144)"
# before the generic "of"/filler-stripping pass could mangle it.
_FUNCTION_WORD_PATTERNS: list[tuple[str, str]] = [
    (r"square\s+root\s+of\s+(-?\d+(?:\.\d+)?)", r"sqrt(\1)"),
    (r"sqrt\s+of\s+(-?\d+(?:\.\d+)?)", r"sqrt(\1)"),
    (r"factorial\s+of\s+(-?\d+)", r"factorial(\1)"),
    (r"(-?\d+)\s+factorial\b", r"factorial(\1)"),
    (r"(-?\d+(?:\.\d+)?)\s+squared\b", r"(\1)**2"),
    (r"(-?\d+(?:\.\d+)?)\s+cubed\b", r"(\1)**3"),
]

_WORD_OPERATOR_PATTERNS: list[tuple[str, str]] = [
    (r"\bmultiplied\s+by\b", "*"),
    (r"\bdivided\s+by\b", "/"),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\btimes\b", "*"),
    (r"(?<=\d)\s*x\s*(?=\d)", "*"),  # "5 x 3" — only between digits
]

_FILLER_PATTERNS: list[str] = [
    r"\bcan you (please )?(calculate|compute|solve|tell me|figure out)\b",
    r"\bcould you (please )?(calculate|compute|solve|tell me|figure out)\b",
    r"\btell me\b",
    r"\bwhat'?s the (result|answer|value) of\b",
    r"\bwhat is the (result|answer|value) of\b",
    r"\bwhat'?s\b",
    r"\bwhat is\b",
    r"\bcalculate\b",
    r"\bcompute\b",
    r"\bsolve\b",
    r"\bwork out\b",
    r"\bhow much is\b",
    r"\bfor me\b",
    r"\bplease\b",
    r"\bthe\b",
    r"\?",
]


def extract_math_expression(text: str) -> Optional[str]:
    """
    Pull a clean, calculate()-ready expression out of natural language, or
    return None if no math expression can be confidently extracted.

    Deliberately conservative about phone numbers and dates (e.g.
    "555-1234", "3/15"), which share the same "digits + operator + digits"
    shape as arithmetic — those are only accepted if the message also has
    explicit math framing ("what is", "calculate", "divided by", ...).
    """
    if not text or not text.strip():
        return None

    if _PHONE_LIKE.search(text) or _DATE_LIKE.search(text):
        if not _STRONG_MATH_FRAMING.search(text):
            return None

    working = text.lower()

    for pattern, repl in _FUNCTION_WORD_PATTERNS:
        working = re.sub(pattern, repl, working)
    for pattern, repl in _WORD_OPERATOR_PATTERNS:
        working = re.sub(pattern, repl, working)
    for pattern in _FILLER_PATTERNS:
        working = re.sub(pattern, " ", working)

    candidate = re.sub(r"\s+", "", working).strip()
    # Strip stray leading/trailing junk that isn't part of the expression
    # (e.g. leftover punctuation) without touching the interior.
    candidate = candidate.strip(".,!;: ")

    if not candidate or not re.search(r"\d", candidate):
        return None

    # Only digits, operators, parens, decimal points, whitelisted function
    # names, and argument-separating commas may remain at this point.
    if not re.fullmatch(r"[0-9.\+\-\*/%()a-z,]+", candidate):
        return None

    if not _is_parseable(candidate):
        return None

    return candidate

"""함수 그래프용 안전한 수식 평가기.

모델은 그래프의 '식'만 정하고(예: "1/(1+exp(-x))"), 점 좌표는 서버가 계산한다 → 근거 없는 수치가 들어가지 않는다.
eval 을 쓰지 않고 ast 를 허용 목록으로 검사한다: 숫자, 변수 x, 상수 pi·e, 사칙연산·거듭제곱(^ 또는 **),
그리고 아래 FUNCS 의 함수 호출만 허용한다(속성 접근·키워드 인자·그 밖의 이름은 모두 거부).
"""
from __future__ import annotations

import ast
import math
from typing import Callable, Optional

MAX_EXPR_LEN = 80
MAX_NODES = 60
SAMPLES = 121
Y_LIMIT = 1e6

FUNCS: dict[str, Callable[..., float]] = {
    "exp": math.exp, "log": math.log, "ln": math.log, "log10": math.log10, "log2": math.log2,
    "sqrt": math.sqrt, "abs": abs, "sin": math.sin, "cos": math.cos, "tan": math.tan, "tanh": math.tanh,
    "sigmoid": lambda t: 1 / (1 + math.exp(-t)) if t > -700 else 0.0,
    "relu": lambda t: max(0.0, t), "max": max, "min": min,
}
CONSTS = {"pi": math.pi, "e": math.e}
_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b}
_UNOPS = {ast.USub: lambda a: -a, ast.UAdd: lambda a: a}


class ExprError(ValueError):
    pass


def parse_expr(expr: str) -> ast.Expression:
    expr = (expr or "").strip()
    if not (1 <= len(expr) <= MAX_EXPR_LEN):
        raise ExprError(f"함수식은 1~{MAX_EXPR_LEN}자여야 합니다")
    try:
        tree = ast.parse(expr.replace("^", "**"), mode="eval")
    except SyntaxError as e:
        raise ExprError(f"함수식을 해석할 수 없습니다: {expr}") from e
    n = 0
    for node in ast.walk(tree):
        n += 1
        if n > MAX_NODES:
            raise ExprError("함수식이 너무 복잡합니다")
        if isinstance(node, (ast.Expression, ast.Load)) or type(node) in _BINOPS or type(node) in _UNOPS:
            continue
        if isinstance(node, (ast.BinOp, ast.UnaryOp)):
            if type(node.op) not in _BINOPS and type(node.op) not in _UNOPS:
                raise ExprError("허용되지 않는 연산자입니다")
            continue
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise ExprError("숫자만 쓸 수 있습니다")
            continue
        if isinstance(node, ast.Name):
            if node.id != "x" and node.id not in CONSTS and node.id not in FUNCS:
                raise ExprError(f"허용되지 않는 이름: {node.id}")
            continue
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS or node.keywords:
                raise ExprError("허용되지 않는 함수 호출입니다")
            continue
        raise ExprError(f"허용되지 않는 구문: {type(node).__name__}")
    return tree


def _eval(node: ast.AST, x: float) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, x)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return x if node.id == "x" else CONSTS[node.id]
    if isinstance(node, ast.BinOp):
        return _BINOPS[type(node.op)](_eval(node.left, x), _eval(node.right, x))
    if isinstance(node, ast.UnaryOp):
        return _UNOPS[type(node.op)](_eval(node.operand, x))
    if isinstance(node, ast.Call):
        return FUNCS[node.func.id](*[_eval(a, x) for a in node.args])  # type: ignore[union-attr]
    raise ExprError("허용되지 않는 구문")


def sample(expr: str, x_min: float, x_max: float, n: int = SAMPLES) -> list[list[Optional[float]]]:
    """[x, y] 목록. 정의되지 않거나 너무 큰 값은 y=None (그래프에서 선을 끊는다)."""
    tree = parse_expr(expr)
    pts: list[list[Optional[float]]] = []
    for i in range(n):
        x = x_min + (x_max - x_min) * i / (n - 1)
        try:
            y = _eval(tree, x)
            if isinstance(y, complex) or not math.isfinite(y) or abs(y) > Y_LIMIT:
                y = None
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            y = None
        pts.append([round(x, 6), None if y is None else round(float(y), 6)])
    finite = sum(1 for _, y in pts if y is not None)
    if finite < n * 0.5:
        raise ExprError(f"x 범위 [{x_min}, {x_max}] 에서 '{expr}' 의 값이 대부분 정의되지 않습니다")
    return pts

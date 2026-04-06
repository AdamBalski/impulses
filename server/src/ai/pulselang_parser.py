from __future__ import annotations


def validate_pulselang(source: str) -> None:
    _parse(source)


def _parse(source: str) -> None:
    tokens = _tokenize(source)
    index = 0
    while index < len(tokens):
        index = _read_node(tokens, index)


def _read_node(tokens: list[tuple[str, str]], index: int) -> int:
    token_type, token_value = tokens[index]
    if token_type in {"number", "string", "symbol"}:
        return index + 1
    if token_type == "paren":
        if token_value == "(":
            index += 1
            while index < len(tokens):
                next_type, next_value = tokens[index]
                if next_type == "paren" and next_value == ")":
                    return index + 1
                index = _read_node(tokens, index)
            raise ValueError("Unbalanced parentheses in DSL expression")
        raise ValueError("Unexpected closing parenthesis")
    raise ValueError("Unexpected token in DSL expression")


def _tokenize(source: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char == "(":
            tokens.append(("paren", "("))
            index += 1
            continue
        if char == ")":
            tokens.append(("paren", ")"))
            index += 1
            continue
        if char.isspace():
            index += 1
            continue
        if char == ";":
            while index < len(source) and source[index] != "\n":
                index += 1
            continue
        if char == "\"":
            value, index = _read_string(source, index)
            tokens.append(("string", value))
            continue
        number_match = _read_number(source, index)
        if number_match is not None:
            number_value, index = number_match
            tokens.append(("number", number_value))
            continue
        symbol_value, index = _read_symbol(source, index)
        tokens.append(("symbol", symbol_value))
    return tokens


def _read_string(source: str, index: int) -> tuple[str, int]:
    value = []
    index += 1
    while index < len(source) and source[index] != "\"":
        if source[index] == "\\" and index + 1 < len(source):
            value.append(source[index + 1])
            index += 2
            continue
        value.append(source[index])
        index += 1
    if index >= len(source) or source[index] != "\"":
        raise ValueError("Unterminated string literal in DSL expression")
    return ("".join(value), index + 1)


def _read_number(source: str, index: int) -> tuple[str, int] | None:
    end = index
    if source[end] == "-":
        end += 1
    has_digits = False
    while end < len(source) and source[end].isdigit():
        has_digits = True
        end += 1
    if end < len(source) and source[end] == ".":
        end += 1
        decimal_digits = False
        while end < len(source) and source[end].isdigit():
            decimal_digits = True
            end += 1
        has_digits = has_digits and decimal_digits
    if not has_digits:
        return None
    if end < len(source) and not _is_token_boundary(source[end]):
        return None
    return (source[index:end], end)


def _read_symbol(source: str, index: int) -> tuple[str, int]:
    end = index
    while end < len(source) and not source[end].isspace() and source[end] not in "()":
        end += 1
    if end == index:
        raise ValueError(f"Unexpected character '{source[index]}' in DSL expression")
    return (source[index:end], end)


def _is_token_boundary(char: str) -> bool:
    return char.isspace() or char in "()"

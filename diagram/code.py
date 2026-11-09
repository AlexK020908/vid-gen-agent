"""The code panel's lines, split into coloured tokens by Pygments, so Remotion only paints them.

Each line is a list of [text, kind], kind one of KINDS; the panel's palette gives each kind its colour.
"""
from __future__ import annotations

from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Token
from pygments.util import ClassNotFound

KINDS = ("keyword", "name", "func", "string", "number", "comment", "punct", "text")
LEXERS = {"text": "text", "http": "http", "dockerfile": "docker", "bash": "bash", "ini": "ini"}


def _kind(tok) -> str:
    if tok in Comment:
        return "comment"
    if tok in Keyword or tok in Name.Builtin or tok in Name.Tag:
        return "keyword"
    if tok in Name.Function or tok in Name.Class or tok in Name.Decorator:
        return "func"
    if tok in String:
        return "string"
    if tok in Number:
        return "number"
    if tok in Punctuation or tok in Operator:
        return "punct"
    if tok in Name or tok in Name.Variable or tok in Name.Attribute:
        return "name"
    return "text"


def tokens(language: str, lines: list[str]) -> list[list[list[str]]]:
    """Each line as [[text, kind], ...], neighbouring tokens of one kind joined."""
    try:
        lexer = get_lexer_by_name(LEXERS.get(language, language), stripnl=False, ensurenl=False)
    except ClassNotFound:
        lexer = get_lexer_by_name("text")
    out = []
    for line in lines:
        got: list[list[str]] = []
        for tok, text in lex(line, lexer):
            if not text or text == "\n":
                continue
            kind = "text" if text.isspace() else _kind(tok if tok is not Token.Error else Token.Text)
            if got and (got[-1][1] == kind or text.isspace()):
                got[-1][0] += text
            else:
                got.append([text, kind])
        out.append(got)
    return out

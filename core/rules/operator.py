"""Operator — all atomic operators for Rule Engine."""
from enum import Enum


class Op(str, Enum):
    EQ        = "=="
    NEQ       = "!="
    GT        = ">"
    GTE       = ">="
    LT        = "<"
    LTE       = "<="
    IN        = "IN"
    NOT_IN    = "NOT_IN"
    EXISTS    = "EXISTS"
    NOT_EXISTS= "NOT_EXISTS"
    BETWEEN   = "BETWEEN"

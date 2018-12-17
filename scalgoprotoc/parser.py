# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Parse a protocol description and generate an ast
"""
import enum
import typing as ty

from .error import error
from .sp_tokenize import Token, TokenType, tokenize


class AstNode(object):
    __slots__ = ["token", "doc_comment", "bytes", "offset", "docstring"]
    token: Token
    doc_comment: Token
    bytes: int
    offset: int
    docstring: ty.List[str]

    def __init__(self, token: Token, doc_comment: Token = None) -> None:
        self.token = token
        self.doc_comment = doc_comment
        self.bytes = 0
        self.offset = 0
        self.docstring = None


class Namespace(AstNode):
    __slots__ = ["namespace"]
    namespace: str

    def __init__(self, token: Token, namespace: str) -> None:
        super().__init__(token)
        self.namespace = namespace


class Struct(AstNode):
    __slots__ = ["identifier", "members", "name"]
    identifier: Token
    members: ty.List["Value"]
    name: str

    def __init__(
        self,
        token: Token,
        identifier: Token,
        members: ty.List["Value"],
        doc_comment: Token,
    ) -> None:
        super().__init__(token, doc_comment)
        self.identifier = identifier
        self.members = members
        self.name = None


class Enum(AstNode):
    __slots__ = ["identifier", "members", "annotatedValues", "name"]
    identifier: Token
    members: ty.List["Value"]
    name: str
    annotatedValues: ty.Dict[str, int]

    def __init__(
        self,
        token: Token,
        identifier: Token,
        members: ty.List["Value"],
        doc_comment: Token,
    ) -> None:
        super().__init__(token, doc_comment)
        self.identifier = identifier
        self.members = members
        self.name = None
        self.annotatedValues = None


class Table(AstNode):
    __slots__ = ["identifier", "id_", "members", "default", "magic", "name"]
    identifier: Token
    id_: Token
    members: ty.List["Value"]
    default: bytes
    name: str
    magic: int

    def __init__(
        self,
        token: Token,
        identifier: Token,
        id_: Token,
        members: ty.List["Value"],
        doc_comment: Token,
    ) -> None:
        super().__init__(token, doc_comment)
        self.identifier = identifier
        self.id_ = id_
        self.members = members
        self.default = None
        self.magic: int = 0
        self.name = None


class Union(AstNode):
    __slots__ = ["members", "identifier", "name"]
    members: ty.List["Value"]
    identifier: Token
    name: str

    def __init__(
        self,
        token: Token,
        identifier: Token,
        members: ty.List["Value"],
        doc_comment: Token,
    ) -> None:
        super().__init__(token, doc_comment)
        self.members = members
        self.identifier = identifier
        self.name = None


class Value(AstNode):
    __slots__ = [
        "identifier",
        "value",
        "type_",
        "optional",
        "list_",
        "inplace",
        "direct_table",
        "direct_union",
        "has_offset",
        "has_bit",
        "bit",
        "table",
        "enum",
        "struct",
        "union",
        "parsed_value",
        "direct_enum",
        "direct_struct",
    ]
    identifier: Token
    value: Token
    type_: Token
    optional: Token
    list_: Token
    inplace: Token
    direct_table: Table
    direct_union: Union
    direct_enum: Enum
    direct_struct: Struct
    has_offset: int
    has_bit: int
    bit: int
    table: Table
    enum: Enum
    struct: Struct
    union: Union
    parsed_value: ty.Union[int, float]

    def __init__(
        self,
        token: Token,
        identifier: Token,
        value: Token,
        type_: Token,
        optional: Token,
        list_: Token,
        inplace: Token,
        direct_table: Table,
        direct_union: Union,
        direct_enum: Enum,
        direct_struct: Struct,
        doc_comment: Token,
    ) -> None:
        super().__init__(token, doc_comment)
        self.identifier = identifier
        self.value = value
        self.type_ = type_
        self.optional = optional
        self.list_ = list_
        self.inplace = inplace
        self.direct_table = direct_table
        self.direct_union = direct_union
        self.direct_enum = direct_enum
        self.direct_struct = direct_struct
        self.has_offset = 0
        self.has_bit = 0
        self.bit = 0
        self.table = None
        self.enum = None
        self.struct = None
        self.union = None
        self.parsed_value = 0


class ParseError(Exception):
    def __init__(self, token: Token, message: str, context: str) -> None:
        self.token = token
        self.message = message
        self.context = context

    def describe(self, data: str) -> None:
        error(data, self.context, self.token, self.message, "Parse error")


class Parser:
    token: Token = None

    def __init__(self, data: str) -> None:
        self.data = data
        self.tokenizer = tokenize(data)
        self.token = None
        self.next_token()
        self.context = ""

    def check_token(self, t: Token, types: ty.List[TokenType]) -> None:
        if not t.type in types:
            raise ParseError(
                t,
                "Expected one of %s got %s" % (", ".join(map(str, types)), t.type),
                self.context,
            )

    def consume_token(self, types: ty.List[TokenType]) -> Token:
        t = self.token
        self.check_token(t, types)
        self.next_token()
        return t

    def next_token(self) -> None:
        self.token = next(self.tokenizer)

    def parse_content(self) -> ty.List[Value]:
        self.consume_token([TokenType.LBRACE])
        members: ty.List[Value] = []
        doc_comment: Token = None
        while True:
            t = self.consume_token(
                [TokenType.RBRACE, TokenType.IDENTIFIER, TokenType.DOCCOMMENT]
            )
            if t.type == TokenType.DOCCOMMENT:
                doc_comment = t
            elif t.type == TokenType.RBRACE:
                break
            elif t.type == TokenType.IDENTIFIER:
                self.check_token(self.token, [TokenType.COLON, TokenType.LBRACE])
                colon: Token = None
                if self.token.type == TokenType.COLON:
                    colon = self.consume_token([TokenType.COLON])
                optional: Token = None
                list_: Token = None
                inplace: Token = None
                value: Token = None
                direct_table: Table = None
                direct_union: Union = None
                direct_enum: Enum = None
                direct_struct: Struct = None
                modifiers = [TokenType.OPTIONAL, TokenType.LIST, TokenType.INPLACE]
                while self.token.type in modifiers:
                    if self.token.type == TokenType.OPTIONAL:
                        optional = self.consume_token([TokenType.OPTIONAL])
                    elif self.token.type == TokenType.LIST:
                        list_ = self.consume_token([TokenType.LIST])
                    elif self.token.type == TokenType.INPLACE:
                        inplace = self.consume_token([TokenType.INPLACE])
                type_ = self.token
                self.check_token(
                    self.token,
                    [
                        TokenType.BOOL,
                        TokenType.TEXT,
                        TokenType.IDENTIFIER,
                        TokenType.BYTES,
                        TokenType.I8,
                        TokenType.I16,
                        TokenType.I32,
                        TokenType.I64,
                        TokenType.U8,
                        TokenType.U16,
                        TokenType.UI32,
                        TokenType.UI64,
                        TokenType.F32,
                        TokenType.F64,
                        TokenType.UNION,
                        TokenType.TABLE,
                        TokenType.LBRACE,
                        TokenType.ENUM,
                        TokenType.STRUCT,
                    ],
                )
                if type_.type == TokenType.LBRACE:
                    direct_table = Table(
                        type_, None, None, self.parse_content(), doc_comment
                    )
                else:
                    self.next_token()
                    if type_.type == TokenType.UNION:
                        direct_union = Union(
                            type_, None, self.parse_content(), doc_comment
                        )
                    elif type_.type == TokenType.TABLE:
                        id_: Token = None
                        if self.token.type == TokenType.ID:
                            id_ = self.consume_token([TokenType.ID])
                        direct_table = Table(
                            type_, None, id_, self.parse_content(), doc_comment
                        )
                    elif type_.type == TokenType.ENUM:
                        direct_enum = Enum(t, None, self.parse_enum(), doc_comment)
                    elif type_.type == TokenType.STRUCT:
                        direct_struct = Struct(
                            type_, None, self.parse_content(), doc_comment
                        )
                    if self.token.type == TokenType.EQUAL:
                        self.consume_token([TokenType.EQUAL])
                        value = self.consume_token(
                            [
                                TokenType.TRUE,
                                TokenType.FALSE,
                                TokenType.NUMBER,
                                TokenType.IDENTIFIER,
                            ]
                        )
                members.append(
                    Value(
                        colon,
                        t,
                        value,
                        type_,
                        optional,
                        list_,
                        inplace,
                        direct_table,
                        direct_union,
                        direct_enum,
                        direct_struct,
                        doc_comment,
                    )
                )
                doc_comment = None
            else:
                raise AssertionError
            if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
                self.next_token()
        return members

    def parse_enum(self) -> ty.List[Value]:
        self.consume_token([TokenType.LBRACE])
        values: ty.List[Value] = []
        doc_comment = None
        while True:
            self.check_token(
                self.token,
                [TokenType.RBRACE, TokenType.IDENTIFIER, TokenType.DOCCOMMENT],
            )
            if self.token.type == TokenType.RBRACE:
                break
            elif self.token.type == TokenType.DOCCOMMENT:
                doccomment2 = self.token
            elif self.token.type == TokenType.IDENTIFIER:
                ident = self.consume_token([TokenType.IDENTIFIER])
                values.append(
                    Value(
                        ident,
                        ident,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        doc_comment,
                    )
                )
                doc_comment = None
                if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
                    self.next_token()
        self.consume_token([TokenType.RBRACE])
        return values

    def value(self, t: Token) -> str:
        return self.data[t.index : t.index + t.length]

    def parse_document(self) -> ty.List[AstNode]:
        ans: ty.List[AstNode] = []
        doc_comment: Token = None
        while self.token.type != TokenType.EOF:
            self.context = "message"
            t = self.consume_token(
                [
                    TokenType.STRUCT,
                    TokenType.ENUM,
                    TokenType.TABLE,
                    TokenType.NAMESPACE,
                    TokenType.UNION,
                    TokenType.DOCCOMMENT,
                ]
            )
            if t.type == TokenType.DOCCOMMENT:
                doc_comment = t
            elif t.type == TokenType.NAMESPACE:
                namespace = ""
                while True:
                    i = self.consume_token([TokenType.IDENTIFIER])
                    namespace += self.data[i.index : i.index + i.length]
                    tt = self.consume_token([TokenType.COLONCOLON, TokenType.SEMICOLON])
                    if tt.type != TokenType.COLONCOLON:
                        break
                    namespace += "::"
                ans.append(Namespace(t, namespace))
                doc_comment = None
            elif t.type == TokenType.STRUCT:
                i = self.consume_token([TokenType.IDENTIFIER])
                self.context = "struct %s" % self.value(i)
                ans.append(Struct(t, i, self.parse_content(), doc_comment))
                doc_comment = None
            elif t.type == TokenType.TABLE:
                i = self.consume_token([TokenType.IDENTIFIER])
                self.context = "table %s" % self.value(i)
                id_ = (
                    self.consume_token([TokenType.ID])
                    if self.token.type == TokenType.ID
                    else None
                )
                ans.append(Table(t, i, id_, self.parse_content(), doc_comment))
                doc_comment = None
            elif t.type == TokenType.ENUM:
                i = self.consume_token([TokenType.IDENTIFIER])
                self.context = "enum %s" % self.value(i)
                ans.append(Enum(t, i, self.parse_enum(), doc_comment))
                doc_comment = None
            elif t.type == TokenType.UNION:
                i = self.consume_token([TokenType.IDENTIFIER])
                self.context = "union %s" % self.value(i)
                ans.append(Union(t, i, self.parse_content(), doc_comment))
                doc_comment = None
            if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
                self.next_token()
        return ans
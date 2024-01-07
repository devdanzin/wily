"""Visitor for raw metrics."""
import ast
import tokenize
from collections import namedtuple
from typing import Optional, Sequence, Union

import asttokens
from radon.metrics import analyze
from radon.raw import Module
from radon.visitors import GET_ENDLINE, CodeVisitor

BaseRawFuncMetrics = namedtuple(
    "BaseRawFuncMetrics",
    [
        "name",
        "lineno",
        "col_offset",
        "endline",
        "is_method",
        "classname",
        "loc",
        "lloc",
        "sloc",
        "comments",
        "multi",
        "blank",
        "single_comments",
    ],
)

BaseRawClassMetrics = namedtuple(
    "BaseRawClassMetrics",
    [
        "name",
        "lineno",
        "col_offset",
        "endline",
        "methods",
        "loc",
        "lloc",
        "sloc",
        "comments",
        "multi",
        "blank",
        "single_comments",
    ],
)


class RawFunctionMetrics(BaseRawFuncMetrics):
    """Object representing a function block."""

    @property
    def fullname(self) -> str:
        """
        The full name of the function.

        If it is a method, then the full name is:
                {class name}.{method name}
        Otherwise it is just the function name.
        """
        if self.classname is None:
            return self.name
        return f"{self.classname}.{self.name}"


class RawClassMetrics(BaseRawClassMetrics):
    """Object representing a class block."""

    @property
    def fullname(self) -> str:
        """
        The full name of the class. It is just its name.

        This attribute exists for consistency (see :data:`RawFunctionMetrics.fullname`).
        """
        return self.name


class RawVisitor(CodeVisitor):
    """
    A visitor that keeps track of raw metrics for block of code.

    Metrics are provided for modules, functions, classes and class methods.

    :param to_method: If True, every function is treated as a method. In this
        case the *classname* parameter is used as class name.
    :param classname: Name of parent class.
    """

    def __init__(
        self,
        to_method: bool = False,
        classname: Optional[str] = None,
        atok: Optional[asttokens.ASTTokens] = None,
    ) -> None:
        """Set up the Visitor instance."""
        self.functions = []
        self.classes = []
        self.to_method = to_method
        self.classname = classname
        self.atok = atok

        self._max_line = -1
        self.loc = -1
        self.lloc = -1
        self.sloc = -1
        self.comments = -1
        self.multi = -1
        self.blank = -1
        self.single_comments = -1
        self.module: Optional[Module] = None

    @classmethod
    def from_code(cls, code: str, **kwargs) -> "RawVisitor":
        """Instantiate the class from source code (string object)."""
        cls.code = code
        node = asttokens.ASTTokens(code, parse=True).tree
        return cls.from_ast(node, **kwargs)

    @property
    def blocks(
        self,
    ) -> Sequence[
        tuple[str, Union[Optional[Module], RawClassMetrics, RawFunctionMetrics]],
    ]:
        """
        All the blocks visited.

        These include: all the functions, the classes and their methods. The returned
        list is not sorted.
        """
        blocks = [("__ModuleMetrics__", self.module)]
        blocks.extend((f.fullname, f) for f in self.functions)
        for cls in self.classes:
            blocks.append((cls.name, cls))
            blocks.extend((m.fullname, m) for m in cls.methods)
        return blocks

    @property
    def max_line(self) -> int:
        """The maximum line number among the analyzed lines."""
        return self._max_line

    @max_line.setter
    def max_line(self, value: int) -> None:
        """Set the maximum line number among the analyzed lines."""
        if value > self._max_line:
            self._max_line = value

    def generic_visit(self, node) -> None:
        """
        Visit a node, recording max_line.

        Main entry point for the visitor.
        """
        # Check for a lineno attribute
        if hasattr(node, "lineno"):
            self.max_line = node.lineno
        super().generic_visit(node)

    def visit_AsyncFunctionDef(self, node) -> None:
        """
        Visit an async function definition.

        Async function definition is the same thing as the synchronous one.
        """
        self.visit_FunctionDef(node)  # type: ignore

    def get_raw_metrics(self, node, module: bool = False) -> None:
        """Gather metrics about the given node (a module, class or function)."""
        if self.atok is None:
            self.atok = asttokens.ASTTokens(self.code, parse=True)
        # Get the base code for the node
        source_segment = self.atok.get_text(node, False)
        # Add trailing comments, if any
        source_segment += get_trailing_comments(self.atok, node, source_segment)
        assert source_segment in self.code
        if not module:
            # Strip trailing whitespace, but only if node is not a module.
            source_segment = source_segment.strip()
        raw_metrics = analyze(source_segment)
        self.loc = raw_metrics.loc
        self.lloc = raw_metrics.lloc
        self.sloc = raw_metrics.sloc
        self.comments = raw_metrics.comments
        self.multi = raw_metrics.multi
        self.blank = raw_metrics.blank
        self.single_comments = raw_metrics.single_comments

    def visit_FunctionDef(self, node) -> None:
        """
        Visit a function definition.

        When visiting functions a new visitor is created to recursively analyze the function's body.
        """
        self.get_raw_metrics(node)
        func_metrics = RawFunctionMetrics(
            node.name,
            node.lineno,
            node.col_offset,
            max(node.lineno, node.lineno + self.loc - 1),
            self.to_method,
            self.classname,
            self.loc,
            self.lloc,
            self.sloc,
            self.comments,
            self.multi,
            self.blank,
            self.single_comments,
        )

        self.functions.append(func_metrics)

    def visit_ClassDef(self, node) -> None:
        """
        Visit a class definition.

        When visiting classes a new visitor is created to recursively analyze the class' body and methods.
        """
        methods = []
        classname = node.name
        visitors_max_lines = [node.lineno]
        for child in node.body:
            if not isinstance(child, ast.FunctionDef):
                continue
            visitor = RawVisitor(
                True,
                classname,
                atok=self.atok,
            )
            visitor.visit(child)  # type: ignore
            methods.extend(visitor.functions)
            visitors_max_lines.append(visitor.max_line)

        self.get_raw_metrics(node)
        line_loc = [node.lineno + self.loc - 1]
        cls_metrics = RawClassMetrics(
            classname,
            node.lineno,
            node.col_offset,
            max(visitors_max_lines + list(map(GET_ENDLINE, methods)) + line_loc),
            methods,
            self.loc,
            self.lloc,
            self.sloc,
            self.comments,
            self.multi,
            self.blank,
            self.single_comments,
        )
        self.classes.append(cls_metrics)

    def visit_Module(self, node) -> None:
        """
        Visit a whole module.

        When visiting the module, a new visitor is created to recursively analyze the classes and functions
        it contains.
        """
        if self.atok is None:
            self.atok = asttokens.ASTTokens(self.code, parse=True)

        for child in node.body:
            visitor = RawVisitor(atok=self.atok)
            visitor.visit(child)  # type: ignore
            self.classes.extend(visitor.classes)
            self.functions.extend(visitor.functions)

        self.get_raw_metrics(node, module=True)
        self.module = Module(
            self.loc,
            self.lloc,
            self.sloc,
            self.comments,
            self.multi,
            self.blank,
            self.single_comments,
        )


def get_trailing_comments(atok: asttokens.ASTTokens, node, source_segment: str) -> str:
    """Get any trailing comments."""
    first = next(atok.get_tokens(node, True))
    indent = 0
    for c in first.line:
        if c != " ":
            break
        indent += 1
    token = list(atok.get_tokens(node, True))[-1]
    comments_and_newlines = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE)
    while token.type != tokenize.ENDMARKER:
        try:
            next_token = atok.next_token(token, include_extra=True)
            # Stop processing if we find something that isn't a comment/newline
            if next_token.type not in comments_and_newlines:
                break
            # Stop if the comment found is less indented than the node's first line
            elif "#" in next_token.line and next_token.line.index("#") < indent:
                break
            token = next_token
        except IndexError:
            break
    comment = token
    len_source = len(source_segment)
    trailing = ""
    # Recover content of trailing comments if any
    if len_source <= comment.startpos:
        # Expects that the source segment is unique in the code
        index = atok.text.index(source_segment)
        trailing = atok.text[index + len_source : comment.endpos]
    return trailing

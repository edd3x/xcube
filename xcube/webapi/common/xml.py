# The MIT License (MIT)
# Copyright (c) 2022 by the xcube development team and contributors
# 
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import abc
from typing import Optional, Dict, Union, Sequence, List

from xcube.util.assertions import assert_given, assert_false


class Node(abc.ABC):
    """An abstract XML node."""

    @abc.abstractmethod
    def add(self, *elements: 'Element') -> 'Node':
        """
        Adds child elements to this element.
        :param elements: Child elements
        """
        pass

    @abc.abstractmethod
    def to_xml(self, indent: int = 2) -> str:
        """
        Converts this node into valid XML text using UTF-8 encoding.
        :param indent: Indent in spaces. Defaults to 2.
        """
        pass

    def __str__(self):
        """Calls to_xml() with default arguments."""
        return self.to_xml()


class Element(Node):
    """
    An XML element node.

    :param tag: Tag name
    :param attrs: Attributes
    :param text: Text
    :param elements: Child elements
    """

    def __init__(self,
                 tag: str,
                 attrs: Optional[Dict[str, str]] = None,
                 text: Optional[Union[str, Sequence[str]]] = None,
                 elements: Optional[Sequence['Element']] = None):
        assert_given(tag, name='tag')
        assert_false(text and elements,
                     message='text and elements are mutually exclusive')
        self._tag = tag
        self._text = text
        self._attrs = dict(attrs) if attrs else {}
        self._elements = list(elements) if elements else []

    def add(self, *elements: 'Element') -> 'Element':
        self._elements.extend(elements)
        return self

    def to_xml(self, indent: int = 2) -> str:
        lines = []
        self._to_xml(indent, 0, lines)
        return '\n'.join(lines)

    def _to_xml(self, indent: int, level: int, lines: List[str]):
        tab = indent * ' '
        tabs = level * tab
        line = f'{tabs}<{self._tag}'
        attrs = self._attrs
        text = self._text
        elements = self._elements
        if attrs:
            for k, v in attrs.items():
                line += f' {k}="{v}"'
        if text:
            if isinstance(text, str):
                lines.append(f'{line}>{text}</{self._tag}>')
            else:
                lines.append(line + '>')
                for t in text:
                    lines.append(f'{tabs}{tab}{t}')
                lines.append(f'{tabs}</{self._tag}>')
        elif elements:
            lines.append(line + '>')
            for node in elements:
                node._to_xml(indent, level + 1, lines)
            lines.append(f'{tabs}</{self._tag}>')
        else:
            lines.append(line + '/>')


class Document(Node):
    """
    An XML document.
    :param root: The only root element.
    """

    def __init__(self, root: Element):
        self._root = root

    def add(self, *elements: 'Element') -> 'Document':
        self._root.add(*elements)
        return self

    def to_xml(self, indent: int = 2) -> str:
        xml = self._root.to_xml()
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml}\n'

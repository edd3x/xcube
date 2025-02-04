# The MIT License (MIT)
# Copyright (c) 2023 by the xcube team and contributors
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



import unittest
from typing import Optional, Union, Mapping, Any

from test.webapi.helpers import get_api_ctx
from xcube.server.api import Context
from xcube.webapi.datasets.context import DatasetsContext
from xcube.webapi.ows.stac.context import StacContext


def get_stac_ctx(
        server_config: Optional[Union[str, Mapping[str, Any]]] = None
) -> StacContext:
    return get_api_ctx("ows.stac", StacContext, server_config)


class StacContextTest(unittest.TestCase):

    def test_ctx_ok(self):
        ctx = get_stac_ctx()
        self.assertIsInstance(ctx.server_ctx, Context)
        self.assertIsInstance(ctx.datasets_ctx, DatasetsContext)

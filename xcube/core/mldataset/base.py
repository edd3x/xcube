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

from typing import Any, Dict, Optional

import xarray as xr

from xcube.core.gridmapping import GridMapping
from xcube.core.schema import rechunk_cube
from xcube.core.subsampling import AggMethods
from xcube.core.subsampling import get_dataset_agg_methods
from xcube.core.subsampling import subsample_dataset
from xcube.core.tilingscheme import get_num_levels
from xcube.util.assertions import assert_instance
from xcube.util.assertions import assert_true
from .lazy import LazyMultiLevelDataset


class BaseMultiLevelDataset(LazyMultiLevelDataset):
    """A multi-level dataset whose level datasets are
    created by down-sampling a base dataset.

    :param base_dataset: The base dataset for the level at index zero.
    :param grid_mapping: Optional grid mapping for *base_dataset*.
    :param num_levels: Optional number of levels.
    :param ds_id: Optional dataset identifier.
    :param agg_methods: Optional aggregation methods.
        May be given as string or as mapping from variable name pattern
        to aggregation method. Valid aggregation methods are
        None, "first", "min", "max", "mean", "median".
        If None, the default, "first" is used for integer variables
        and "mean" for floating point variables.
    """

    def __init__(self,
                 base_dataset: xr.Dataset,
                 grid_mapping: Optional[GridMapping] = None,
                 num_levels: Optional[int] = None,
                 agg_methods: Optional[AggMethods] = 'first',
                 ds_id: Optional[str] = None):
        assert_instance(base_dataset, xr.Dataset, name='base_dataset')
        if grid_mapping is not None:
            assert_instance(grid_mapping, GridMapping, name='grid_mapping')

        if grid_mapping is None:
            # TODO (forman): why not computing it lazily?
            grid_mapping = GridMapping.from_dataset(base_dataset,
                                                    tolerance=1e-4)

        self._agg_methods = get_dataset_agg_methods(
            base_dataset,
            xy_dim_names=grid_mapping.xy_dim_names,
            agg_methods=agg_methods
        )

        self._base_dataset = base_dataset
        super().__init__(grid_mapping=grid_mapping,
                         num_levels=num_levels,
                         ds_id=ds_id)

    @property
    def agg_methods(self):
        return self._agg_methods

    def _get_num_levels_lazily(self) -> int:
        gm = self.grid_mapping
        return get_num_levels(gm.size, gm.tile_size)

    def _get_dataset_lazily(self,
                            index: int,
                            parameters: Dict[str, Any]) -> xr.Dataset:
        """
        Compute the dataset at level *index*: If *index* is zero, return
        the base image passed to constructor, otherwise down-sample the
        dataset for the level at given *index*.

        :param index: the level index
        :param parameters: currently unused
        :return: the dataset for the level at *index*.
        """
        assert_instance(index, int, name='index')
        if index < 0:
            index = self.num_levels + index
        assert_true(0 <= index < self.num_levels,
                    message='index out of range')

        if index == 0:
            level_dataset = self._base_dataset
        else:
            level_dataset = subsample_dataset(
                self._base_dataset,
                2 ** index,
                xy_dim_names=self.grid_mapping.xy_dim_names,
                agg_methods=self._agg_methods
            )

        # Tile each level according to grid mapping
        tile_size = self.grid_mapping.tile_size
        if tile_size is not None:
            level_dataset, _ = rechunk_cube(level_dataset,
                                            self.grid_mapping,
                                            tile_size=tile_size)
        return level_dataset

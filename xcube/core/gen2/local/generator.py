# The MIT License (MIT)
# Copyright (c) 2021 by the xcube development team and contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import Optional

import xarray as xr

from xcube.core.gridmapping import GridMapping
from xcube.core.store import DataStorePool
from xcube.util.assertions import assert_instance
from xcube.util.progress import observe_progress
from .combiner import CubesCombiner
from .helpers import is_empty_cube
from .informant import CubeInformant
from .opener import CubeOpener
from .rechunker import CubeRechunker
from .resamplert import CubeResamplerT
from .resamplerxy import CubeResamplerXY
from .subsetter import CubeSubsetter
from .mdadjuster import CubeMetadataAdjuster
from .transformer import CubeIdentity
from .transformer import transform_cube
from .usercode import CubeUserCodeExecutor
from .writer import CubeWriter
from .. import CubeConfig
from ..generator import CubeGenerator
from ..progress import ApiProgressCallbackObserver
from ..request import CubeGeneratorRequest
from ..request import CubeGeneratorRequestLike
from ..response import CubeGeneratorResult
from ..response import CubeInfoResult
from ..response import CubeReference


class LocalCubeGenerator(CubeGenerator):
    """
    Generator tool for data cubes.

    Creates cube views from one or more cube stores, resamples them to a
    common grid, optionally performs some cube transformation, and writes
    the resulting cube to some target cube store.

    :param store_pool: An optional pool of pre-configured data stores
        referenced from *gen_config* input/output configurations.
    :param verbosity: Level of verbosity, 0 means off.
    :param raise_on_error: Whether to raise a CubeGeneratorError
        exception on generator failures. If False, the default,
        the returned result will have the "status" field set to "error"
        while other fields such as "message", "traceback", "output"
        provide more failure details.
    """

    def __init__(self,
                 store_pool: DataStorePool = None,
                 raise_on_error: bool = False,
                 verbosity: int = 0):
        super().__init__(raise_on_error=raise_on_error,
                         verbosity=verbosity)
        if store_pool is not None:
            assert_instance(store_pool, DataStorePool, 'store_pool')

        self._store_pool = store_pool if store_pool is not None \
            else DataStorePool()
        self._generated_data_id: Optional[str] = None
        self._generated_cube: Optional[xr.Dataset] = None
        self._generated_gm: Optional[GridMapping] = None

    @property
    def generated_data_id(self) -> Optional[str]:
        """Return the data identifier of the recently generated data cube."""
        return self._generated_data_id

    @property
    def generated_cube(self) -> Optional[xr.Dataset]:
        """Return the recently generated data cube."""
        return self._generated_cube

    @property
    def generated_gm(self) -> Optional[GridMapping]:
        """Return the recently generated data cube."""
        return self._generated_gm

    def _generate_cube(self, request: CubeGeneratorRequestLike) \
            -> CubeGeneratorResult:

        request = CubeGeneratorRequest.normalize(request)
        request = request.for_local()

        observer = None
        if request.callback_config:
            observer = ApiProgressCallbackObserver(request.callback_config)
            observer.activate()

        try:
            return self.__generate_cube(request)
        finally:
            if observer is not None:
                observer.deactivate()

    def __generate_cube(self, request: CubeGeneratorRequest) \
            -> CubeGeneratorResult:

        cube_config = request.cube_config \
            if request.cube_config is not None else CubeConfig()

        opener = CubeOpener(cube_config,
                            store_pool=self._store_pool)

        subsetter = CubeSubsetter()
        resampler_xy = CubeResamplerXY()
        resampler_t = CubeResamplerT()
        combiner = CubesCombiner(cube_config)
        rechunker = CubeRechunker()

        code_config = request.code_config
        if code_config is not None:
            code_executor = CubeUserCodeExecutor(code_config)
            post_rechunker = CubeRechunker()
        else:
            code_executor = CubeIdentity()
            post_rechunker = CubeIdentity()

        md_adjuster = CubeMetadataAdjuster()

        cube_writer = CubeWriter(request.output_config,
                                 store_pool=self._store_pool)

        num_inputs = len(request.input_configs)
        # Estimated workload:
        opener_work = 10
        resampler_t_work = 1
        resampler_xy_work = 20
        subsetter_work = 1
        combiner_work = num_inputs
        rechunker_work = 1
        executor_work = 1
        post_rechunker_work = 1
        metadata_adjuster_work = 1
        writer_work = 100  # this is where dask processing takes place
        total_work = (opener_work
                      + subsetter_work
                      + resampler_t_work
                      + resampler_xy_work) * num_inputs \
                     + combiner_work \
                     + rechunker_work \
                     + executor_work \
                     + post_rechunker_work \
                     + metadata_adjuster_work \
                     + writer_work

        t_cubes = []
        with observe_progress('Generating cube',
                              total_work) as progress:
            for input_config in request.input_configs:
                progress.will_work(opener_work)
                t_cube = opener.open_cube(input_config)

                progress.will_work(subsetter_work)
                t_cube = transform_cube(t_cube, subsetter,
                                        'subsetting')

                progress.will_work(resampler_t_work)
                t_cube = transform_cube(t_cube, resampler_t,
                                        'resampling in time')

                progress.will_work(resampler_xy_work)
                t_cube = transform_cube(t_cube, resampler_xy,
                                        'resampling in space')

                t_cubes.append(t_cube)

            progress.will_work(combiner_work)
            t_cube = combiner.combine_cubes(t_cubes)

            progress.will_work(rechunker_work)
            t_cube = transform_cube(t_cube, rechunker,
                                    'rechunking')

            progress.will_work(executor_work)
            t_cube = transform_cube(t_cube, code_executor,
                                    'executing user code')

            progress.will_work(post_rechunker_work)
            t_cube = transform_cube(t_cube, post_rechunker,
                                    'post-rechunking')

            progress.will_work(metadata_adjuster_work)
            t_cube = transform_cube(t_cube, md_adjuster,
                                    'adjusting metadata')

            progress.will_work(writer_work)
            cube, gm, _ = t_cube
            if not is_empty_cube(cube):
                data_id, cube = cube_writer.write_cube(cube, gm)
                self._generated_data_id = data_id
                self._generated_cube = cube
                self._generated_gm = gm
            else:
                self._generated_data_id = None
                self._generated_cube = None
                self._generated_gm = None

        total_time = progress.state.total_time

        if self._generated_data_id is not None:
            return CubeGeneratorResult(
                status='ok',
                status_code=201,
                result=CubeReference(data_id=data_id),
                message=f'Cube generated successfully'
                        f' after {total_time:.2f} seconds'
            )
        else:
            return CubeGeneratorResult(
                status='warning',
                status_code=422,
                message=f'An empty cube has been generated'
                        f' after {total_time:.2f} seconds.'
                        f' No data has been written at all.'
            )

    def _get_cube_info(self, request: CubeGeneratorRequestLike) \
            -> CubeInfoResult:
        request = CubeGeneratorRequest.normalize(request)
        informant = CubeInformant(request=request.for_local(),
                                  store_pool=self._store_pool)
        cube_info = informant.generate()
        return CubeInfoResult(result=cube_info,
                              status='ok',
                              status_code=200)

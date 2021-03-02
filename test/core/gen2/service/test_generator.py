import unittest

import requests_mock

from test.util.test_progress import TestProgressObserver
from xcube.core.gen2 import CubeGeneratorError
from xcube.core.gen2.request import CubeGeneratorRequest
from xcube.core.gen2.service import CubeGeneratorService
from xcube.core.gen2.service import ServiceConfig
from xcube.core.gen2.service.response import CubeInfoWithCosts
from xcube.util.progress import new_progress_observers


def result(worked, total_work, failed=False, traceback: str = None):
    json = {
        "result": {
            "cubegen_id": "93",
            "status": {
                "failed": True if failed else None,
                "succeeded": True if worked == total_work else None,
                "active": 1 if worked != total_work else None,
            },
            "progress": [
                {
                    "sender": "ignored",
                    "status": {
                        "progress": worked / total_work,
                        "worked": worked,
                        "total_work": total_work,
                    }
                },
            ],
        }
    }
    if traceback:
        json.update(traceback=traceback)
    return dict(json=json)


class CubeGeneratorServiceTest(unittest.TestCase):
    ENDPOINT_URL = 'https://xcube-gen.com/api/v2/'

    CUBE_GEN_CONFIG = dict(input_config=dict(store_id='memory',
                                             data_id='S2L2A'),
                           cube_config=dict(variable_names=['B01', 'B02', 'B03'],
                                            crs='WGS84',
                                            bbox=[12.2, 52.1, 13.9, 54.8],
                                            spatial_res=0.05,
                                            time_range=['2018-01-01', None],
                                            time_period='4D'),
                           output_config=dict(store_id='memory',
                                              data_id='CHL'))

    def setUp(self) -> None:
        self.service = CubeGeneratorService(CubeGeneratorRequest.from_dict(self.CUBE_GEN_CONFIG),
                                            ServiceConfig(endpoint_url=self.ENDPOINT_URL,
                                                          client_id='itzibitzispider',
                                                          client_secret='g3ergd36fd2983457fhjder'),
                                            progress_period=0,
                                            verbose=True)

    @requests_mock.Mocker()
    def test_generate_cube_success(self, m: requests_mock.Mocker):
        m.post(f'{self.ENDPOINT_URL}oauth/token',
               json={
                   "access_token": "4ccsstkn983456jkfde",
                   "token_type": "bearer"
               })

        m.put(f'{self.ENDPOINT_URL}cubegens',
              response_list=[
                  result(0, 4),
              ])

        m.get(f'{self.ENDPOINT_URL}cubegens/93',
              response_list=[
                  result(1, 4),
                  result(2, 4),
                  result(3, 4),
                  result(4, 4),
              ])

        observer = TestProgressObserver()
        with new_progress_observers(observer):
            self.service.generate_cube()

        self.assertEqual(
            [
                ('begin', [('Generating cube', 0.0, False)]),
                ('update', [('Generating cube', 0.25, False)]),
                ('update', [('Generating cube', 0.5, False)]),
                ('update', [('Generating cube', 0.75, False)]),
                ('end', [('Generating cube', 0.75, True)])
            ],
            observer.calls)

    @requests_mock.Mocker()
    def test_generate_cube_failure(self, m: requests_mock.Mocker):
        m.post(f'{self.ENDPOINT_URL}oauth/token',
               json={
                   "access_token": "4ccsstkn983456jkfde",
                   "token_type": "bearer"
               })

        m.put(f'{self.ENDPOINT_URL}cubegens',
              response_list=[
                  result(0, 4),
              ])

        m.get(f'{self.ENDPOINT_URL}cubegens/93',
              response_list=[
                  result(1, 4),
                  result(2, 4, failed=True, traceback='1.that\n2.was\n3.bad'),
              ])

        observer = TestProgressObserver()
        with new_progress_observers(observer):
            with self.assertRaises(CubeGeneratorError) as cm:
                self.service.generate_cube()
            self.assertEqual('Cube generation failed', f'{cm.exception}')
            self.assertEqual('1.that\n2.was\n3.bad', cm.exception.remote_traceback)

        print(observer.calls)
        self.assertEqual(
            [
                ('begin', [('Generating cube', 0.0, False)]),
                ('update', [('Generating cube', 0.25, False)]),
                ('end', [('Generating cube', 0.25, True)])
            ],
            observer.calls)

    @requests_mock.Mocker()
    def test_get_cube_info(self, m: requests_mock.Mocker):
        m.post(f'{self.ENDPOINT_URL}oauth/token',
               json={
                   "access_token": "4ccsstkn983456jkfde",
                   "token_type": "bearer"
               })

        m.post(f'{self.ENDPOINT_URL}cubegens/info',
               json=dict(dims=dict(time=10 * 365, lat=720, lon=1440),
                         chunks=dict(time=10, lat=720, lon=1440),
                         data_vars=dict(CHL=dict(long_name='chlorophyll_concentration',
                                                 units='mg/m^-1')),
                         cost_info=dict(punits_input=300,
                                        punits_output=400,
                                        punits_combined=500)))

        cube_info = self.service.get_cube_info()
        self.assertIsInstance(cube_info, CubeInfoWithCosts)
        self.assertEqual(dict(time=10 * 365, lat=720, lon=1440),
                         cube_info.dims)
        self.assertEqual(dict(time=10, lat=720, lon=1440),
                         cube_info.chunks)
        self.assertEqual(dict(CHL=dict(long_name='chlorophyll_concentration',
                                       units='mg/m^-1')),
                         cube_info.data_vars)
        self.assertEqual(
            {
                "punits_input": 300,
                "punits_output": 400,
                "punits_combined": 500
            },
            cube_info.cost_info.additional_properties)
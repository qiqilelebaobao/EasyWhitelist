import logging

from .client import ClientFactory
from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models


class Regions:
    def __init__(self):
        client = ClientFactory.create_client("cn-hangzhou")
        describe_regions_request = ecs_20140526_models.DescribeRegionsRequest()
        runtime = util_models.RuntimeOptions()
        try:
            response = client.describe_regions_with_options(describe_regions_request, runtime)
            logging.info(f"[aliyun] DescribeRegions response: {response.body.to_map()['Regions']['Region']}")

            self.region_ids = [region['RegionId'] for region in response.body.to_map()['Regions']['Region']]
            self.region_endpoints = [region['RegionEndpoint'] for region in response.body.to_map()['Regions']['Region']]

        except (UnretryableException, TeaException) as e:
            print(f"\033[1;91m[aliyun] Failed to describe regions, reason={e}\033[0m")

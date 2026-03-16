import logging
import os
from typing import List, Optional

from Tea.exceptions import UnretryableException, TeaException
from darabonba.runtime import RuntimeOptions
from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client


def _runtime() -> RuntimeOptions:
    """Return a RuntimeOptions instance; ignore_ssl is enabled when DISABLE_SSL_VERIFY=1 (local debugging only)."""
    return RuntimeOptions(ignore_ssl=os.getenv('DISABLE_SSL_VERIFY') == '1')


class Regions:
    """Fetches and stores all available Alibaba Cloud regions for a given ECS client."""

    def __init__(self, client: Ecs20140526Client, proxy_url: Optional[str] = None):
        """Initialize by calling DescribeRegions and populating region IDs and endpoints.

        Args:
            client: An authenticated Alibaba Cloud ECS client instance.
            proxy_url: Optional proxy URL (e.g. 'http://localhost:7890') to propagate to sub-clients.

        Raises:
            UnretryableException: If the API call cannot be retried.
            TeaException: If the API returns an error response.
            KeyError: If the expected fields are missing from the response.
        """
        self.proxy = proxy_url
        self.region_ids: List[str] = []
        self.region_endpoints: List[str] = []

        describe_regions_request = ecs_20140526_models.DescribeRegionsRequest()
        runtime = _runtime()
        try:
            response = client.describe_regions_with_options(describe_regions_request, runtime)
            regions = response.body.to_map()['Regions']['Region']
            logging.debug("[aliyun] DescribeRegions response: %s", regions)
            # Extract region IDs and their corresponding API endpoints
            self.region_ids = [region['RegionId'] for region in regions]
            self.region_endpoints = [region['RegionEndpoint'] for region in regions]
        except (UnretryableException, TeaException, KeyError) as e:
            print(f"\033[1;91m[aliyun] Failed to describe regions, reason={e}\033[0m")
            logging.exception("[aliyun] Failed to describe regions")
            raise

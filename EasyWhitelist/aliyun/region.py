import logging
from typing import List, Optional

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.cli import echo_err
from .client import ClientFactory
from .defaults import _runtime, DEFAULT_REGION_1, DEFAULT_REGION_2


class Regions:
    """Fetches and stores all available Alibaba Cloud regions for a given ECS client."""

    def __init__(self, proxy_port: Optional[int] = None):
        """Initialize by calling DescribeRegions and populating region IDs and endpoints.

        Args:
            proxy_port: Optional proxy port (1–65535) to propagate to sub-clients.

        Raises:
            UnretryableException: If the API call cannot be retried.
            TeaException: If the API returns an error response.
            KeyError: If the expected fields are missing from the response.
        """
        self.proxy_url = f"http://localhost:{proxy_port}" if proxy_port is not None else None
        self.region_ids: List[str] = []
        self.region_endpoints: List[str] = []

        client: Ecs20140526Client = ClientFactory.create_client(DEFAULT_REGION_1, proxy_port) or ClientFactory.create_client(DEFAULT_REGION_2, proxy_port)

        describe_regions_request = ecs_20140526_models.DescribeRegionsRequest()
        runtime = _runtime(self.proxy_url is not None)
        try:
            response = client.describe_regions_with_options(describe_regions_request, runtime)
            regions = response.body.to_map()['Regions']['Region']
            logging.debug("[aliyun] DescribeRegions response: %s", regions)
            # Extract region IDs and their corresponding API endpoints
            self.region_ids = [region['RegionId'] for region in regions]
            self.region_endpoints = [region['RegionEndpoint'] for region in regions]
        except (UnretryableException, TeaException, KeyError) as e:
            echo_err(f"Failed to describe regions: {e}")
            logging.exception("[aliyun] Failed to describe regions")
            raise

"""Default configuration values used by aliyun helpers.

Keep cloud-specific defaults here (region, vpc, endpoint, limits).
Do NOT store secrets or credentials in this file.
"""

DEFAULT_REGION = 'cn-hangzhou'
# NOTE: DEFAULT_VPC_ID is a placeholder only; inject a real VPC ID via ALIBABA_CLOUD_VPC_ID env var in production.
DEFAULT_VPC_ID = ''
DEFAULT_MAX_ENTRIES = 20

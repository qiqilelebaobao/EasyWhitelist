"""Default configuration values used by aliyun helpers.

Keep cloud-specific defaults here (region, vpc, endpoint, limits).
Do NOT store secrets or credentials in this file.
"""

DEFAULT_REGION = 'cn-hangzhou'
# NOTE: DEFAULT_VPC_ID 仅作示例，生产环境请通过环境变量 ALIBABA_CLOUD_VPC_ID 注入。
DEFAULT_VPC_ID = ''
DEFAULT_MAX_ENTRIES = 20

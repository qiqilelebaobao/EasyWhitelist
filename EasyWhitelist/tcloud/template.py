import json
import random
import sys
import logging

from typing import List, Optional


from ..ip_detector import detectors
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

# ---------- 常量 ----------
TEMPLATE_PREFIX = "EW-TEMPLATE-"
TEMPLATE_ID_PREFIX = "ipm-"
HEADER_WIDTH = 150
COLS = {
    "idx": 10,
    "id": 20,
    "ctime": 30,
    "addrs": 60,
    "name": 30,
}

# 这段是获取和打印模板


def _get_template(common_client) -> Optional[dict]:
    try:
        # templates = common_client.call_json("DescribeAddressTemplates", params, options = {"SkipSign": True})
        return common_client.call_json("DescribeAddressTemplates", {})

    except TencentCloudSDKException as e:
        logging.error("[template] DescribeAddressTemplates failed, %s", e)
        return None


def print_template(common_client) -> List[str]:

    if not (tpl_resp := _get_template(common_client)):
        return []

    template_ids = []

    # 表头
    header = (f"{"#":<{COLS["idx"]}}"
              f"{"Template ID":<{COLS["id"]}}"
              f"{"CreatedTime":<{COLS["ctime"]}}"
              f"{"Addresses":<{COLS["addrs"]}}"
              f"{"AddressTemplateName":<{COLS["name"]}}")

    print(f"{"Tencent Cloud Template List":=^{HEADER_WIDTH}}")
    print(header)
    print(f"-" * HEADER_WIDTH)

    for i, template in enumerate(tpl_resp["Response"]["AddressTemplateSet"], 1):
        template_ids.append(template["AddressTemplateId"])
        addreset = ", ".join(template["AddressSet"][:3])
        if len(template["AddressSet"]) > 3:
            addreset += f" ~~~ {len(template["AddressSet"])-3} more..."
        print(f"{str(i):{COLS["idx"]}}"
              f"{template["AddressTemplateId"]:{COLS["id"]}}"
              f"{template["CreatedTime"]:{COLS["ctime"]}}"
              f"{addreset:<{COLS["addrs"]}}"
              f"{template["AddressTemplateName"]:{COLS["name"]}}"
              )
    print("-" * HEADER_WIDTH)

    return template_ids


def _get_iplist(proxy=None):

    client_ip_list = detectors.get_local_ips(proxy)
    client_ip_list = list(set(client_ip_list))

    return client_ip_list


def _modify_template_address(common_client, target_id, client_ips):

    if not target_id:
        return False

    # 增加描述校验，避免更改错误
    params = {"Filters": [
        {"Name": "address-template-id", "Values": [target_id]}]}
    try:
        respon = common_client.call_json("DescribeAddressTemplates", params)
        if (TemplateSet := respon["Response"]["AddressTemplateSet"]) and TemplateSet[0]["AddressTemplateName"].startswith(TEMPLATE_PREFIX):
            pass
        else:
            print("This is not a template generated from this tool. Shall not be modified.")
            return False
    except (TencentCloudSDKException, IndexError) as err:
        # IndexError catch when there is no match target.Example: "AddressTemplateSet": []
        logging.error("[template] api call failed, reason=exception, detail=%s", err)
        sys.exit(1)

    params = {"AddressTemplateId": target_id,
              "AddressesExtra": [{"Address": ip, "Description": "client_ip"} for ip in client_ips]
              }

    try:
        respon = common_client.call_json(
            "ModifyAddressTemplateAttribute", params)

    except TencentCloudSDKException as err:
        logging.error("[template] api call failed, reason=exception, detail=%s", err)
        return False

    return True


def set_template(common_client, target_id, proxy=None):
    """更新模板 IP，返回是否成功"""
    if not target_id:
        logging.error("[template] missing template_id, reason=empty input")
        return False

    if not target_id.startswith(TEMPLATE_ID_PREFIX):
        logging.warning("[template] set failed, reason=wrong template id, hint=check prefix")
        return False

    client_iplist = _get_iplist(proxy)

    if _modify_template_address(common_client, target_id, client_iplist):
        print(f"✅ [成功] 模板 {target_id} 已更新 -> {client_iplist}")
        return True
    else:
        # 底层修改失败
        logging.error("[template] failed to update template %s", target_id)
        print(f"❌ [失败] 模板 {target_id} 更新失败（请检查网络或模板状态）")
        return False


def create_template_and_associate(common_client, rule_id, proxy=None):

    if not rule_id:
        logging.error("[template] security group ID required but missing")
        return False
    # check rule_id
    pass

    template_id, ret_val = create_template(common_client, proxy)

    if ret_val == 1:
        return True
    elif ret_val == 2:
        return associate_template_2_rule(common_client, template_id, rule_id)
    else:
        return False


def create_template(common_client, proxy=None):
    try:
        params = {"Filters": [{"Name": "address-template-name", "Values": [TEMPLATE_PREFIX]}]}
        respon = common_client.call_json("DescribeAddressTemplates", params)

        logging.debug("[template] API response, detail=%s", json.dumps(respon, ensure_ascii=False))

        if respon["Response"]["AddressTemplateSet"]:
            # 找到第一个符合的模板就设置
            existing_template = respon["Response"]["AddressTemplateSet"][0]
            template_id = existing_template["AddressTemplateId"]
            template_name = existing_template["AddressTemplateName"]

            logging.info("[template] already have template without creation: %s", template_id)

            print(f"🔄 [进行中] 已有模板 {template_id} ({template_name})，直接在模板更新本地公网IP")

            set_template(common_client, template_id)
            return template_id, 1

        ip_list = _get_iplist(proxy)
        random_suffix = random.randint(1, 9999)
        template_name = f"{TEMPLATE_PREFIX}{random_suffix:04d}"
        params = {
            "AddressTemplateName": template_name,
            "AddressesExtra": [{"Address": ip, "Description": "client_ip"} for ip in ip_list]
        }
        print(f"🎯 [开始] 创建模板, 模板名字为：{template_name}")

        respon = common_client.call_json("CreateAddressTemplate", params)
        template_id = respon["Response"]["AddressTemplate"]["AddressTemplateId"]
        logging.info("[template] API response, detail=%s", json.dumps(respon, ensure_ascii=False))

        print(f"🔄 [进行中] 模板 {template_id} 已创建")

        return template_id, 2

    except TencentCloudSDKException as err:
        logging.error("[template] API failed, reason=exception, detail=%s", err)
        return None, 3


def associate_template_2_rule(common_client, template_id, rule_id):

    try:
        # 避免重复关联
        params = {
            "SecurityGroupId": rule_id,
            "Filters": [{"Name": "address-module", "Values": [template_id]}]
        }
        respon = common_client.call_json("DescribeSecurityGroupPolicies", params)

        if respon["Response"]["SecurityGroupPolicySet"]["Ingress"]:
            logging.info("[template] %s already associate to %s", template_id, rule_id)
            print(f"❗ [中止] 已有属于程序创建的模板 {template_id} 关联到 {rule_id}，仅允许关联一次")
            return False

        # 进入规则设置
        params = {"SecurityGroupId": f"{rule_id}",
                  "SecurityGroupPolicySet":
                  {"Ingress": [
                      {"PolicyIndex": 0, "Protocol": "ALL", "AddressTemplate": {
                          "AddressId": f"{template_id}"},
                       "Action": "ACCEPT", "PolicyDescription": "Easy Whitelist"}
                  ]}
                  }

        respon = common_client.call_json("CreateSecurityGroupPolicies", params)
        logging.info("[template] API response, detail=%s", json.dumps(respon, ensure_ascii=False))
        print(f"✅ [成功] 模板 {template_id} 已关联到 {rule_id}")

    except TencentCloudSDKException as err:
        logging.error("[template] api failed, reason=exception, detail=%s", err)
        return False

    return True

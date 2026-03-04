import json
import random
import logging
from typing import List, Optional
from enum import Enum, auto


from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

from ..ip_detector.detectors import get_iplist
from ..util.nm import TEMPLATE_PREFIX, TEMPLATE_ID_PREFIX

HEADER_WIDTH = 150
COLS = {
    "idx": 10,
    "id": 30,
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
    header = (f"{'#':<{COLS['idx']}}"
              f"{'Template ID':<{COLS['id']}}"
              f"{'CreatedTime':<{COLS['ctime']}}"
              f"{'Addresses':<{COLS['addrs']}}"
              f"{'AddressTemplateName':<{COLS['name']}}")

    print(f"{'Tencent Cloud Template List':=^{HEADER_WIDTH}}")
    print(header)
    print("-" * HEADER_WIDTH)

    for i, template in enumerate(tpl_resp["Response"]["AddressTemplateSet"], 1):
        template_ids.append(template["AddressTemplateId"])
        addr_set = template["AddressSet"]
        addreset = ", ".join(addr_set[:3])
        if len(addr_set) > 3:
            addreset += f" ~~~ {len(addr_set) - 3} more..."
        t_id = template["AddressTemplateId"]
        t_time = template["CreatedTime"]
        t_name = template["AddressTemplateName"]
        print(f"{str(i):{COLS['idx']}}"
              f"{t_id:{COLS['id']}}"
              f"{t_time:{COLS['ctime']}}"
              f"{addreset:<{COLS['addrs']}}"
              f"{t_name:{COLS['name']}}"
              )
    print("-" * HEADER_WIDTH)

    return template_ids


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
            logging.error("[template] this is not a template generated from this tool. Shall not be modified.")
            return False
    except (TencentCloudSDKException, IndexError) as err:
        # IndexError catch when there is no match target.Example: "AddressTemplateSet": []
        logging.error("[template] api call failed, reason=exception, detail=%s", err)
        raise RuntimeError(f"[template] api call failed: {err}") from err

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

    client_iplist = get_iplist(proxy)

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

        ip_list = get_iplist(proxy)
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


class CommandAction(Enum):
    CONTINUE = auto()
    BREAK = auto()
    NOTHING = auto()


CMD_LIST = "l"
CMD_EMPTY = ""
CMD_CREATE = "c"
CMD_EXIT = "q"
INPUT_PROMPT = "Please choose # template to set (or [L]ist, [C]reate, [Q]uit): "


def _handle_digit_input(user_input: str, common_client, template_ids: list, proxy: Optional[str]) -> None:
    """
    处理数字输入，选择模板索引

    Args:
        user_input: 用户输入的数字字符串
        common_client: 云服务客户端
        template_ids: 模板ID列表
        proxy: 代理设置，可选
    """

    if not template_ids:
        logging.warning("[template] no template available, reason=no template, hint=create one first")
        return

    try:
        index = int(user_input)
        if 1 <= index <= len(template_ids):
            set_template(common_client, template_ids[index - 1], proxy)
        else:
            logging.warning("[template] select failed, reason=index out of range, hint=available 1~%d", len(template_ids))
    except ValueError:
        logging.warning("[template] select failed, reason=invalid number %s, hint= %d", user_input, len(template_ids))


def _handle_command_input(user_input: str, common_client, template_ids: list, proxy: Optional[str]) -> CommandAction:
    """
    处理命令输入，执行相应操作

    Args:
        user_input: 用户输入的命令
        common_client: 云服务客户端
        template_ids: 模板ID列表
        proxy: 代理设置，可选

    Returns:
        CommandAction: 指示后续操作的动作
    """

    command_handlers = {
        CMD_LIST: (lambda: print_template(common_client), CommandAction.CONTINUE),
        CMD_EMPTY: (lambda: None, CommandAction.CONTINUE),
        CMD_CREATE: (
            lambda: logging.warning("[template] create command not yet implemented, hint=use 'ew template create <sg_id>'"),
            CommandAction.CONTINUE,
        ),
        CMD_EXIT: (lambda: None, CommandAction.BREAK),
        # 可轻松扩展其他命令，例如 "h": show_help
    }

    if user_input in command_handlers:
        handler, action = command_handlers[user_input]
        handler()
        return action
    else:
        logging.warning("[cli] command failed, reason=invalid command %s, hint=l/c/q", user_input)
        return CommandAction.CONTINUE


def loop_list(common_client, proxy: Optional[str] = None) -> None:
    template_ids = print_template(common_client)
    last_input = None

    while True:

        try:
            user_input = input(INPUT_PROMPT).strip().lower()

            if last_input == "" and user_input == "":
                break

            last_input = user_input

            if user_input.isdigit():
                _handle_digit_input(
                    user_input, common_client, template_ids, proxy)
            else:
                action = _handle_command_input(
                    user_input, common_client, template_ids, proxy)
                if action == CommandAction.BREAK:
                    break

        except KeyboardInterrupt:
            logging.warning("[cli] operation cancelled, reason=user interrupt, hint=none")
            break

        except ValueError as e:
            logging.warning("[cli] input failed, reason=value error %s, hint=retry", e)

        except ConnectionError as e:
            logging.error("[http] connection failed, reason=connection error, detail=%s", e)
            break

        except Exception as e:
            logging.error("[http] request failed, reason=unexpected, detail=%s", e)
            break

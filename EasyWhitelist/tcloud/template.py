import json
import logging
from typing import List, Optional, Tuple
from enum import Enum, auto
from datetime import datetime


from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

from ..detector.detectors import retrieve_unique_ip_addresses
from ..util.defaults import TEMPLATE_NAME_PREFIX, TEMPLATE_ID_PREFIX
from ..util.cli import print_header, print_row, print_tail


class CreateResult(Enum):
    """create_template 返回的状态，替代魔法数字 1/2/3。"""
    UPDATED_EXISTING = auto()   # 已有模板，直接更新完毕
    CREATED_NEW = auto()        # 新建模板成功，需要关联
    FAILED = auto()             # 异常失败


def initialize_and_bind_template(common_client, security_rule_id, proxy_port: Optional[int] = None):

    if not security_rule_id:
        logging.error("[template] Security group ID required but missing")
        return False

    template_id, ret_val = _ensure_address_template(common_client, proxy_port=proxy_port)

    if ret_val == CreateResult.UPDATED_EXISTING:
        return 0
    elif ret_val == CreateResult.CREATED_NEW:
        return _associate_template_2_rule(common_client, template_id, security_rule_id)
    else:
        return 1


def update_template(common_client, template_id, proxy_port: Optional[int] = None):
    """更新模板 IP，返回是否成功"""
    if not template_id:
        logging.error("[template] Missing template ID")
        return False

    if not template_id.startswith(TEMPLATE_ID_PREFIX):
        logging.warning("[template] Set failed: invalid template ID (check prefix)")
        return False

    unique_client_ips = retrieve_unique_ip_addresses(proxy_port)

    if _modify_template_address(common_client, template_id, unique_client_ips):
        logging.info("[template] Template %s updated with IPs: %s", template_id, ", ".join(unique_client_ips) if unique_client_ips else "")
        print(f"✅ [成功] 模板 {template_id} 已更新 -> {unique_client_ips}")
        return True
    else:
        # 底层修改失败
        logging.error("[template] Failed to update template %s", template_id)
        print(f"❌ [失败] 模板 {template_id} 更新失败（请检查网络或模板状态）")
        return False


def loop_list(common_client, proxy_port: Optional[int] = None) -> None:
    template_ids = _display_template_list(common_client)
    last_input = None

    while True:

        try:
            user_input = input(INPUT_PROMPT).strip().lower()

            if last_input == "" and user_input == "":
                break

            last_input = user_input

            if user_input.isdigit():
                _handle_digit_input(
                    user_input, common_client, template_ids, proxy_port)
            elif user_input == CMD_LIST:
                # 重新拉取列表并刷新本地 template_ids
                template_ids = _display_template_list(common_client)
            else:
                action = _handle_command_input(user_input, common_client, template_ids, proxy_port)
                if action == CommandAction.BREAK:
                    break

        except KeyboardInterrupt:
            logging.warning("[template] Operation cancelled by user")
            break

        except ValueError as e:
            logging.warning("[template] Input failed: value error: %s", e)

        except ConnectionError as e:
            logging.error("[template] Connection failed: %s", e)
            break

        except Exception as e:
            logging.error("[template] Request failed: %s", e)
            break


def _retrieve_template_info(common_client, params: dict = {}) -> list:
    try:
        # params = {"Filters": [{"Name": "address-template-name", "Values": [TEMPLATE_NAME_PREFIX]}]}
        respon = common_client.call_json("DescribeAddressTemplates", params)

        logging.debug("[template] API response: %s", json.dumps(respon, ensure_ascii=False))

        address_template_set = respon.get("Response", {}).get("AddressTemplateSet", [])
        if address_template_set:
            logging.info("[template] Found %d templates in API response", len(address_template_set))
            return address_template_set
        else:
            logging.info("[template] No existing templates found with prefix '%s'", TEMPLATE_NAME_PREFIX)
            return []

    except TencentCloudSDKException as e:
        logging.error("[template] DescribeAddressTemplates failed: %s", e)
        return []


def _retrieve_template_info_with_filter(common_client) -> list:
    params = {"Filters": [{"Name": "address-template-name", "Values": [TEMPLATE_NAME_PREFIX]}]}
    return _retrieve_template_info(common_client, params)


def _display_template_list(common_client) -> List[str]:

    if not (address_template_set := _retrieve_template_info_with_filter(common_client)):
        return []

    template_ids = []

    print_header('Tencent Cloud Template List')

    for i, template in enumerate(address_template_set, 1):
        template_ids.append(template["AddressTemplateId"])
        addr_set = template["AddressSet"]
        addreset = ", ".join(addr_set[:3])
        if len(addr_set) > 3:
            addreset += f" ~~~ {len(addr_set) - 3} more..."
        t_id = template["AddressTemplateId"]
        t_time = template["CreatedTime"]
        t_name = template["AddressTemplateName"]
        print_row(idx=i, id=t_id, ctime=t_time, addrs=addreset, name=t_name)

    print_tail()

    return template_ids


def _modify_template_address(common_client, template_id, client_ips):

    if not template_id:
        return False

    # 增加描述校验，避免更改错误
    params = {"Filters": [
        {"Name": "address-template-id", "Values": [template_id]}]}
    try:
        respon = common_client.call_json("DescribeAddressTemplates", params)
        if (TemplateSet := respon["Response"]["AddressTemplateSet"]) and TemplateSet[0]["AddressTemplateName"].startswith(TEMPLATE_NAME_PREFIX):
            pass
        else:
            logging.error("[template] Template does not appear to have been created by this tool; aborting modification.")
            return False
    except (TencentCloudSDKException, IndexError) as err:
        # Catch IndexError when there is no matching target (e.g. "AddressTemplateSet": []).
        logging.error("[template] API call failed: %s", err)
        raise RuntimeError(f"[template] API call failed: {err}") from err

    params = {"AddressTemplateId": template_id,
              "AddressesExtra": [{"Address": ip, "Description": "client_ip"} for ip in client_ips]
              }

    try:
        respon = common_client.call_json(
            "ModifyAddressTemplateAttribute", params)

    except TencentCloudSDKException as err:
        logging.error("[template] API call failed: %s", err)
        return False

    return True


def _create_template(common_client, proxy_port: Optional[int] = None) -> Tuple[str, CreateResult]:
    """创建模板并返回模板ID，失败返回None"""

    ip_list = retrieve_unique_ip_addresses(proxy_port)
    template_name = f"{TEMPLATE_NAME_PREFIX}{int(datetime.now().timestamp())}"
    params = {
        "AddressTemplateName": template_name,
        "AddressesExtra": [{"Address": ip, "Description": "client_ip"} for ip in ip_list]
    }
    print(f"🎯 [开始] 创建模板, 模板名字为：{template_name}")

    try:
        respon = common_client.call_json("CreateAddressTemplate", params)
        template_id = respon["Response"]["AddressTemplate"]["AddressTemplateId"]
        print(f"🔄 [进行中] 模板 {template_id} 已创建")
        return template_id, CreateResult.CREATED_NEW
    except TencentCloudSDKException as err:
        logging.error("[template] API failed: %s", err)
        return '', CreateResult.FAILED


def _ensure_address_template(common_client, proxy_port: Optional[int] = None):

    address_template_set = _retrieve_template_info_with_filter(common_client)
    if not address_template_set:
        return _create_template(common_client, proxy_port)

    # 找到第一个符合的模板就设置
    existing_template = address_template_set[0]
    template_id = existing_template.get("AddressTemplateId")
    template_name = existing_template.get("AddressTemplateName")
    logging.info("[template] Existing template found: %s", template_id)

    print(f"🔄 [进行中] 已有模板 {template_id} ({template_name})，直接在模板更新本地公网IP")
    update_template(common_client, template_id, proxy_port)

    return template_id, CreateResult.UPDATED_EXISTING


def _associate_template_2_rule(common_client, template_id, rule_id):

    try:
        # 避免重复关联
        params = {
            "SecurityGroupId": rule_id,
            "Filters": [{"Name": "address-module", "Values": [template_id]}]
        }
        respon = common_client.call_json("DescribeSecurityGroupPolicies", params)

        if respon["Response"]["SecurityGroupPolicySet"]["Ingress"]:
            logging.info("[template] %s already associated with %s", template_id, rule_id)
            print(f"❗ [中止] 已有属于程序创建的模板 {template_id} 关联到 {rule_id}，仅允许关联一次")
            return False

        # 进入规则设置
        params = {"SecurityGroupId": rule_id,
                  "SecurityGroupPolicySet":
                  {"Ingress": [
                      {"PolicyIndex": 0, "Protocol": "ALL", "AddressTemplate": {
                          "AddressId": template_id},
                       "Action": "ACCEPT", "PolicyDescription": "Easy Whitelist"}
                  ]}
                  }

        respon = common_client.call_json("CreateSecurityGroupPolicies", params)
        logging.info("[template] API response: %s", json.dumps(respon, ensure_ascii=False))
        print(f"✅ [成功] 模板 {template_id} 已关联到 {rule_id}")
        return True

    except TencentCloudSDKException as err:
        logging.error("[template] API failed: %s", err)
        return False


class CommandAction(Enum):
    CONTINUE = auto()
    BREAK = auto()
    NOTHING = auto()  # keep for future use, e.g. invalid command but do not want to print warning


CMD_LIST = "l"
CMD_EMPTY = ""
CMD_CREATE = "c"
CMD_EXIT = "q"
INPUT_PROMPT = "Please choose # template to set (or [L]ist, [C]reate, [Q]uit, Enter\u00d72 to exit): "


def _handle_digit_input(user_input: str, common_client, template_ids: list, proxy_port: Optional[int]) -> None:
    """
    处理数字输入，选择模板索引

    Args:
        user_input: 用户输入的数字字符串
        common_client: 云服务客户端
        template_ids: 模板ID列表
        proxy_port: 代理端口，可选
    """

    if not template_ids:
        logging.warning("[template] No templates available; create one first")
        return

    try:
        index = int(user_input)
        if 1 <= index <= len(template_ids):
            update_template(common_client, template_ids[index - 1], proxy_port)
        else:
            logging.warning("[template] Selection failed: index out of range (available: 1~%d)", len(template_ids))
    except ValueError:
        logging.warning("[template] Selection failed: invalid number '%s' (expected 1~%d)", user_input, len(template_ids))


def _handle_command_input(user_input: str, common_client, template_ids: list, proxy_port: Optional[int]) -> CommandAction:
    """
    处理命令输入，执行相应操作

    Args:
        user_input: 用户输入的命令
        common_client: 云服务客户端
        template_ids: 模板ID列表
        proxy_port: 代理端口，可选

    Returns:
        CommandAction: 指示后续操作的动作
    """

    command_handlers = {
        CMD_EMPTY: (lambda: None, CommandAction.CONTINUE),
        CMD_LIST: (lambda: None, CommandAction.CONTINUE),  # list refresh handled by caller; prevents invalid-command fallthrough
        CMD_CREATE: (
            lambda: logging.warning("[template] Create command not yet implemented, hint=use 'ew template create <sg_id>'"),
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
        logging.warning("[template] Invalid command: %s (hint: l/c/q)", user_input)
        return CommandAction.CONTINUE

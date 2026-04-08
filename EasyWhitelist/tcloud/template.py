import json
import logging
from typing import List, Optional, Tuple
from enum import Enum, auto
from datetime import datetime

from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

from ..util.db import normalize_ip_list
from ..config import settings
from ..detector.detectors import retrieve_unique_ip_addresses
from ..util.defaults import RESOURCE_NAME_PREFIX, TEMPLATE_ID_PREFIX
from ..util.cli import print_header, print_row, print_tail, echo_start, echo_progress, echo_success, echo_fail, echo_abort, echo_hint

DEFAULT_MAX_ENTRIES = 20


class CreateResult(Enum):
    """create_template 返回的状态，替代魔法数字 1/2/3。"""
    UPDATED_EXISTING = auto()   # 已有模板，直接更新完毕
    CREATED_NEW = auto()        # 新建模板成功，需要关联
    FAILED = auto()             # 异常失败


def initialize_and_bind_template(common_client, security_rule_id):

    if not security_rule_id:
        logging.error("[template] Security group ID required but missing")
        return 1
    template_id, ret_val = _ensure_address_template(common_client)

    if ret_val == CreateResult.UPDATED_EXISTING or ret_val == CreateResult.CREATED_NEW:
        return _associate_template_to_rule(common_client, template_id, security_rule_id)
    else:
        return 1


def _update_template(common_client, template_id):
    """更新模板 IP，返回是否成功"""
    if not template_id:
        logging.error("[template] Missing template ID")
        return False

    if not template_id.startswith(TEMPLATE_ID_PREFIX):
        logging.error("[template] Set failed: invalid template ID (check prefix)")
        return False

    raw_ips = retrieve_unique_ip_addresses()
    normalized_ips = normalize_ip_list(raw_ips, DEFAULT_MAX_ENTRIES, "tencentcloud", settings.ctx.db_conn)
    echo_hint("已规范化 IP 列表并记录到数据库")

    if _modify_template_address(common_client, template_id, normalized_ips):
        logging.info("[template] Template %s updated with IPs: %s", template_id, ", ".join(normalized_ips) if normalized_ips else "")
        echo_success(f"模板 {template_id} 已更新 -> {normalized_ips}")
        return True
    # 底层修改失败
    logging.error("[template] Failed to update template %s", template_id)
    echo_fail(f"模板 {template_id} 更新失败（请检查网络或模板状态）")
    return False


def update_all_templates(common_client) -> int:

    if not (address_template_set := _retrieve_template_info_with_filter(common_client)):
        return 1

    failed = 0
    for i, template in enumerate(address_template_set, 1):
        ok = _update_template(common_client, template["AddressTemplateId"])
        if not ok:
            failed += 1
            logging.warning("[template] Failed to update template %d/%d: %s", i, len(address_template_set), template["AddressTemplateId"])
        else:
            logging.info("[template] Updated template %d/%d: %s", i, len(address_template_set), template["AddressTemplateId"])
    return 0 if failed == 0 else 1


def process_template_input(common_client) -> int:
    template_ids = _display_template_list(common_client)
    last_input = None

    while True:

        try:
            user_input = input(INPUT_PROMPT).strip().lower()

            if last_input == CMD_EMPTY and user_input == CMD_EMPTY:
                break

            last_input = user_input

            if user_input.isdigit():
                _handle_digit_input(
                    user_input, common_client, template_ids)
            elif user_input == CMD_LIST:
                # 重新拉取列表并刷新本地 template_ids
                template_ids = _display_template_list(common_client)
            else:
                action = _handle_command_input(user_input, common_client)
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

    return 0


def _retrieve_template_info(common_client, params: Optional[dict] = None) -> list:
    if params is None:
        params = {}
    try:
        response = common_client.call_json("DescribeAddressTemplates", params)

        logging.debug("[template] API response: %s", json.dumps(response, ensure_ascii=False))

        address_template_set = response.get("Response", {}).get("AddressTemplateSet", [])
        if address_template_set:
            logging.info("[template] Found %d templates in API response", len(address_template_set))
            return address_template_set
        else:
            logging.info("[template] No existing templates found with prefix '%s'", RESOURCE_NAME_PREFIX)
            return []

    except TencentCloudSDKException as e:
        logging.error("[template] DescribeAddressTemplates failed: %s", e)
        return []


def _retrieve_template_info_with_filter(common_client) -> list:
    params = {"Filters": [{"Name": "address-template-name", "Values": [RESOURCE_NAME_PREFIX]}]}
    return _retrieve_template_info(common_client, params)


def _display_template_list(common_client) -> List[str]:

    if not (address_template_set := _retrieve_template_info_with_filter(common_client)):
        return []

    template_ids = []

    print_header('Tencent Cloud Template List')

    for i, template in enumerate(address_template_set, 1):
        template_ids.append(template["AddressTemplateId"])
        addr_set = template.get("AddressSet", [])
        addreset = ", ".join(addr_set[:3])
        if len(addr_set) > 3:
            addreset += f" ~~~ {len(addr_set) - 3} more..."
        print_row(
            idx=i,
            region=common_client.region,
            id=template["AddressTemplateId"],
            ctime=template["CreatedTime"],
            addrs=addreset,
            name=template["AddressTemplateName"],
        )

    print_tail()

    return template_ids


def _modify_template_address(common_client, template_id, client_ips):

    if not template_id:
        return False

    if not client_ips:
        logging.error("[template] Refusing to update template with empty IP list")
        return False

    params = {"AddressTemplateId": template_id, "AddressesExtra": [{"Address": ip, "Description": "client_ip"} for ip in client_ips]}
    try:
        response = common_client.call_json("ModifyAddressTemplateAttribute", params)
        logging.debug("[template] ModifyAddressTemplateAttribute response: %s", json.dumps(response, ensure_ascii=False))
    except TencentCloudSDKException as err:
        logging.error("[template] API call failed: %s", err)
        return False

    return True


def _create_template(common_client) -> Tuple[str, CreateResult]:
    """创建模板并返回模板ID，失败返回 ('', CreateResult.FAILED)。"""

    raw_ips = retrieve_unique_ip_addresses()
    normalized_ips = normalize_ip_list(raw_ips, DEFAULT_MAX_ENTRIES, "tencentcloud", settings.ctx.db_conn)

    template_name = f"{RESOURCE_NAME_PREFIX}{int(datetime.now().timestamp())}"
    params = {
        "AddressTemplateName": template_name,
        "AddressesExtra": [{"Address": ip, "Description": "client_ip"} for ip in normalized_ips]
    }
    echo_start(f"创建模板, 模板名字为：{template_name}")

    try:
        response = common_client.call_json("CreateAddressTemplate", params)
        template_id = response["Response"]["AddressTemplate"]["AddressTemplateId"]
        echo_progress(f"模板 {template_id} 已创建")
        return template_id, CreateResult.CREATED_NEW
    except (TencentCloudSDKException, KeyError) as err:
        logging.error("[template] API failed: %s", err)
        return '', CreateResult.FAILED


def _ensure_address_template(common_client):

    address_template_set = _retrieve_template_info_with_filter(common_client)
    if not address_template_set:
        return _create_template(common_client)

    # 找到第一个符合的模板就设置
    existing_template = address_template_set[0]
    template_id = existing_template.get("AddressTemplateId")
    template_name = existing_template.get("AddressTemplateName")
    logging.info("[template] Existing template found: %s", template_id)

    echo_progress(f"已有模板 {template_id} ({template_name})，直接在模板更新本地公网IP")
    if not _update_template(common_client, template_id):
        return template_id, CreateResult.FAILED

    return template_id, CreateResult.UPDATED_EXISTING


def _associate_template_to_rule(common_client, template_id, rule_id):

    try:
        # 避免重复关联
        params = {
            "SecurityGroupId": rule_id,
            "Filters": [{"Name": "address-module", "Values": [template_id]}]
        }
        response = common_client.call_json("DescribeSecurityGroupPolicies", params)

        if response.get("Response", {}).get("SecurityGroupPolicySet", {}).get("Ingress"):
            logging.info("[template] %s already associated with %s", template_id, rule_id)
            echo_abort(f"已有属于程序创建的模板 {template_id} 关联到 {rule_id}，仅允许关联一次")
            return 0

        # 进入规则设置
        policy_params = {"SecurityGroupId": rule_id,
                         "SecurityGroupPolicySet":
                         {"Ingress": [
                             {"PolicyIndex": 0, "Protocol": "ALL", "AddressTemplate": {
                                 "AddressId": template_id},
                                 "Action": "ACCEPT", "PolicyDescription": "Easy Whitelist"}
                         ]}
                         }

        response = common_client.call_json("CreateSecurityGroupPolicies", policy_params)
        logging.info("[template] API response: %s", json.dumps(response, ensure_ascii=False))
        echo_success(f"模板 {template_id} 已关联到 {rule_id}")
        return 0

    except TencentCloudSDKException as err:
        logging.error("[template] API failed: %s", err)
        return 1


class CommandAction(Enum):
    CONTINUE = auto()
    BREAK = auto()


CMD_LIST = "l"
CMD_EMPTY = ""
CMD_CREATE = "c"
CMD_EXIT = "q"
INPUT_PROMPT = "Please choose # template to set (or [L]ist, [C]reate, [Q]uit, [\u21b5\u00d72] to exit): "


def _handle_digit_input(user_input: str, common_client, template_ids: list) -> None:
    """
    处理数字输入，选择模板索引

    Args:
        user_input: 用户输入的数字字符串
        common_client: 云服务客户端
        template_ids: 模板ID列表
    """

    if not template_ids:
        logging.warning("[template] No templates available; create one first")
        return

    index = int(user_input)
    if 1 <= index <= len(template_ids):
        _update_template(common_client, template_ids[index - 1])
    else:
        logging.warning("[template] Selection failed: index out of range (available: 1~%d)", len(template_ids))


def _handle_command_input(user_input: str, common_client) -> CommandAction:
    """
    处理命令输入，执行相应操作

    Args:
        user_input: 用户输入的命令
        common_client: 云服务客户端

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

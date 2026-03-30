import os
import logging


def generate_app_directory(app_dir_name="EasyWhitelist"):
    """
    跨平台在用户目录下创建 APP 专属目录
    :param app_dir_name: 自定义 APP 目录名（如 "MyMovieDB"）
    :return: 成功返回目录路径，失败返回 None
    """
    try:
        # 1. 获取用户主目录（跨平台通用）
        user_home = os.path.expanduser("~")
        # 2. 拼接 APP 目录路径
        app_dir = os.path.join(user_home, app_dir_name)

        # 3. 创建目录（exist_ok=True：目录已存在时不报错）
        os.makedirs(app_dir, exist_ok=True)

        return app_dir

    except PermissionError:
        logging.error("Insufficient permissions: cannot create application directory. Run as administrator/root.")
        return None
    except Exception as e:
        logging.error("Failed to create application directory: %s", e)
        return None

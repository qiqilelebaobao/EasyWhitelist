import os
import logging


def generate_app_directory(app_dir_name="EasyWhitelist"):
    """
    Create a dedicated application directory under the user's home directory, cross-platform.
    :param app_dir_name: Custom application directory name (e.g. "MyMovieDB")
    :return: Directory path on success, None on failure
    """
    try:
        # 1. Resolve the user's home directory (cross-platform)
        user_home = os.path.expanduser("~")
        # 2. Build the application directory path
        app_dir = os.path.join(user_home, app_dir_name)

        # 3. Create the directory (exist_ok=True: no error if it already exists)
        os.makedirs(app_dir, exist_ok=True)

        return app_dir

    except PermissionError:
        logging.error("Insufficient permissions: cannot create application directory. Run as administrator/root.")
        return None
    except Exception as e:
        logging.error("Failed to create application directory: %s", e)
        return None

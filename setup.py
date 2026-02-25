from setuptools import setup, find_packages  # type: ignore

with open("README.md", encoding="utf-8") as f:
    long_desc = f.read()

setup(
    name="EasyWhitelist",              # PyPI 上唯一的名字
    version="1.0.104",                   # 每次上传必须 > 旧版本
    author="qiqilelebaobao",
    author_email="qiqilelebaobao@163.com",
    description="A smart tool that detects the local Internet IP address and automatically updates the local Internet IP address to the cloud security group whitelist.",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    keywords=["whitelist", "security-groups", "alibaba-cloud", "tencent-cloud", "security-tools"],
    url="https://github.com/qiqilelebaobao/easy_whitelist",
    license="Apache License 2.0",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Security",
        "Topic :: System :: Networking",
        "Intended Audience :: System Administrators"
    ],
    package_data={
        # "easy_whitelist": ["*.txt"],   # 键=包名，值=glob 列表
    },
    setup_requires=[
        "setuptools>=61.0",
        "wheel",
        "Cython"
    ],
    install_requires=[
        "tencentcloud-sdk-python"
    ],
    entry_points={
        "console_scripts": [
            "ew=EasyWhitelist._core:main",
        ],
    },
    extras_require={
        "cli": [
            "rich",
            "click>=5.0",
        ],
    },
    python_requires=">=3.8"
)

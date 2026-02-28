from setuptools import setup, find_packages  # type: ignore

with open("README.md", encoding="utf-8") as f:
    long_desc = f.read()

setup(
    long_description=long_desc,
    long_description_content_type="text/markdown",
    keywords=["whitelist", "security-groups", "alibaba-cloud", "tencent-cloud", "security-tools"],
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

# EasyWhitelist

[![PyPI version](https://img.shields.io/pypi/v/EasyWhitelist.svg)](https://pypi.org/project/EasyWhitelist/)
[![Python](https://img.shields.io/pypi/pyversions/EasyWhitelist.svg)](https://pypi.org/project/EasyWhitelist/)
[![License](https://img.shields.io/github/license/qiqilelebaobao/easy_whitelist.svg)](https://github.com/qiqilelebaobao/easy_whitelist/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/qiqilelebaobao/easy_whitelist.svg?style=social)](https://github.com/qiqilelebaobao/easy_whitelist)

EasyWhitelist 是一个自动探测本机公网 IP 地址，并将其更新到云安全组白名单的命令行工具，使用 Python 编写。

EasyWhitelist is a CLI tool that detects the local public IP address and automatically updates cloud security group whitelists. Written in Python.

## 主要功能 / Features

* 自动探测本机公网 IP（多源并发，自动去重）
* 支持**腾讯云**地址模板（Address Template）和**阿里云**前缀列表（Prefix List）
* 区域缓存：将 region 列表和安全组信息本地缓存到 SQLite，加速后续操作
* 支持通过本地 HTTP 代理访问云 API

<!-- -->

* Auto-detects local public IP via multiple sources concurrently
* Supports **Tencent Cloud** Address Templates and **Alibaba Cloud** Prefix Lists
* Caches region / security-group info in local SQLite for faster subsequent runs
* Supports routing cloud API calls through a local HTTP proxy

## 适用场景 / Applicable Scenarios

* 场景一：不知道如何探测本机的公网IP的用户，通过本工具自动探测公网 IP，并添加云安全组白名单
* 场景二：IP 地址因为 NAT 环境经常变化，包括家庭环境或者公司无固定出口 IP 的宽带环境，需要安全的使用云环境资源
* 场景三：测试场景，频繁变换客户端环境，需要安全的使用云环境资源

* Scene 1: Users who do not know how to detect the public IP of their local machine can use this tool to automatically detect the public IP and add it to the cloud security group whitelist
* Scene 2: IP addresses often change due to NAT environments, including home environments or broadband environments without fixed export IPs in companies, which require safe use of cloud environment resources
* Scene 3: Test scenarios, frequent changes in client environments, which require safe use of cloud environment resources

## 安装指南 Installation Guide

需要 Python 3.8+ 环境。Python 3.8+ is required.

```shell
pip install EasyWhitelist
```

## 凭据配置 Credentials

工具通过环境变量读取云厂商密钥，无需配置文件。
Credentials are read from environment variables; no config file is needed.

### 腾讯云 Tencent Cloud

```shell
export TENCENTCLOUD_SECRET_ID=your_secret_id
export TENCENTCLOUD_SECRET_KEY=your_secret_key
```

### 阿里云 Alibaba Cloud

```shell
export ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
```

## 使用说明 Basic Usage

```text
ew [-t | -a] [-p PORT] [-v] <init | list | set> [target_id]
```

### 选项 Options

| 参数 | 说明 |
| --- | --- |
| `-t`, `--tencent` | 使用腾讯云（默认） / Use Tencent Cloud (default) |
| `-a`, `--alibaba` | 使用阿里云 / Use Alibaba Cloud |
| `-p PORT`, `--proxy PORT` | 本地 HTTP 代理端口（1-65535）/ Local HTTP proxy port |
| `-v`, `--verbose` | 增加日志详细程度 / Increase log verbosity |

### 操作 Actions

| 命令 | 说明 |
| --- | --- |
| `init [target_id]` | 初始化：绑定地址模板或前缀列表到安全组规则 / Initialize and bind template/prefix to security group |
| `list` | 列出已有模板或前缀列表，交互式选择 / List and interactively select existing template/prefix |
| `set` | 探测当前公网 IP 并更新所有已绑定的模板 / Detect current public IP and update all bound templates |

### 示例 Examples

```shell
# 腾讯云：初始化并绑定安全组规则
ew init sg-xxxxxxxx

# 腾讯云：查看地址模板列表并选择
ew list

# 腾讯云：更新所有已绑定模板为当前公网 IP
ew set

# 阿里云：初始化并绑定前缀列表
ew -a init sg-xxxxxxxx

# 阿里云：更新前缀列表
ew -a set

# 通过本地代理端口 7890 访问云 API
ew -p 7890 set
```

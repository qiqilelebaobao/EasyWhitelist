# EasyWhitelist

EasyWhitelist 是一个探测本机互联网 IP 地址，将并本机互联网IP地址，自动更新到云安全组白名单的小工具。工具使用 Python 编写。

EasyWhitelist is a smart tool that detects the local Internet IP address and automatically updates the local Internet IP address to the cloud security group whitelist. The tool is written in Python.

主要功能包括：

* 自动探测本机互联网 IP 地址
* 支持阿里云、腾讯云的安全组白名单更新
* 腾讯云支持地址模板更新

Main functions include:

* Automatically detect the local Internet IP address
* Support security group whitelist updates for Alibaba Cloud and Tencent Cloud
* Tencent Cloud supports address template updates

## 适用场景 Applicable Scenarios

* 场景一：不知道如何探测本机的公网IP的用户，通过本工具自动探测公网 IP，并添加云安全组白名单
* 场景二：IP 地址因为 NAT 环境经常变化，包括家庭环境或者公司无固定出口 IP 的宽带环境，需要安全的使用云环境资源
* 场景三：测试场景，频繁变换客户端环境，需要安全的使用云环境资源

* Scene1: Users who do not know how to detect the public IP of their local machine can use this tool to automatically detect the public IP and add it to the cloud security group whitelist
* Scene2: IP addresses often change due to NAT environments, including home environments or broadband environments without fixed export IPs in companies, which require safe use of cloud environment resources
* Scene3: Test scenarios, frequent changes in client environments, which require safe use of cloud environment resources

## 安装指南 Installation Guide

需要 Python3 环境
Python3 is required

## 使用说明 Basic Usage

* 通过列表选择模版，设置白名单

```shell
ew template list
```

* 通过新创建模版，设置白名单。需要指定关联的安全组ID

```shell
ew template create rule_id
```

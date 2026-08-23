<!--
云启科技知识库文档元数据

文档编号: YQ-TECH-FASTAPI-031
类别: 技术文档类
来源: fastapi 官方文档
获取方式: GitHub/官网下载
更新日期: 2026-08-18
权限级别: 全员
负责人: 资料管理组
状态: 已清洗
原始来源: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/deployment/index.md
许可证: MIT
-->
# Deployment { #deployment }

Deploying a **FastAPI** application is relatively easy.

## What Does Deployment Mean { #what-does-deployment-mean }

To **deploy** an application means to perform the necessary steps to make it **available to the users**.

For a **web API**, it normally involves putting it in a **remote machine**, with a **server program** that provides good performance, stability, etc, so that your **users** can **access** the application efficiently and without interruptions or problems.

This is in contrast to the **development** stages, where you are constantly changing the code, breaking it and fixing it, stopping and restarting the development server, etc.

## Deployment Strategies { #deployment-strategies }

There are several ways to do it depending on your specific use case and the tools that you use.

You could **deploy a server** yourself using a combination of tools, you could use a **cloud service** that does part of the work for you, or other possible options.

For example, we, the team behind FastAPI, built [**FastAPI Cloud**](https://fastapicloud.com), to make deploying FastAPI apps to the cloud as streamlined as possible, with the same developer experience of working with FastAPI.

I will show you some of the main concepts you should probably keep in mind when deploying a **FastAPI** application (although most of it applies to any other type of web application).

You will see more details to keep in mind and some of the techniques to do it in the next sections. ✨

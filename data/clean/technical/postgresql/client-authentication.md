<!--
云启科技知识库文档元数据

文档编号: YQ-TECH-POSTGRESQL-040
类别: 技术文档类
来源: postgresql 官方文档
获取方式: GitHub/官网下载
更新日期: 2026-08-18
权限级别: 全员
负责人: 资料管理组
状态: 已清洗
原始来源: https://www.postgresql.org/docs/current/client-authentication.html
许可证: PostgreSQL License
备注: PostgreSQL: Documentation: 18: Chapter 20. Client Authentication
-->
## Chapter 20. Client Authentication

### Note

As explained in [Chapter 21](user-manag.html), PostgreSQL actually does privilege management in terms of “roles”. In this chapter, we consistently use *database user* to mean “role with the `LOGIN` privilege”.

*Authentication* is the process by which the database server establishes the identity of the client, and by extension determines whether the client application (or the user who runs the client application) is permitted to connect with the database user name that was requested.

PostgreSQL offers a number of different client authentication methods. The method used to authenticate a particular client connection can be selected on the basis of (client) host address, database, and user.

PostgreSQL database user names are logically separate from user names of the operating system in which the server runs. If all the users of a particular server also have accounts on the server's machine, it makes sense to assign database user names that match their operating system user names. However, a server that accepts remote connections might have many database users who have no local operating system account, and in such cases there need be no connection between database user names and OS user names.

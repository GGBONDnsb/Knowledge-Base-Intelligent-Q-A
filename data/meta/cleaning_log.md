# 数据清洗日志

清洗范围：统一换行、压缩空行、合并表格空行；MDX 转 Markdown；PostgreSQL 页面移除目录。

## 处理统计

- 处理文档数：233

| 处理项 | 文档数 |
| --- | --- |
| MDX 转 Markdown：移除 frontmatter 与 JSX 组件标签 | 30 |
| PostgreSQL 页面：移除 Table of Contents | 14 |

## 面试素材：清洗中遇到的问题

1. GitHub 文档格式不统一：Markdown、MDX、HTML 混用，统一转换为 Markdown 并移除 JSX/frontmatter。
2. PostgreSQL 官方文档为 HTML，需提取正文并转换为 Markdown，同时移除页面目录和导航链接。
3. 表格在生成脚本中行间有空行，清洗时自动合并，保证 Markdown 表格可被解析器正确识别。
4. 网络环境无法访问 raw.githubusercontent.com，改用 jsDelivr CDN 下载相同公开文件，并在元数据中保留原始仓库地址。

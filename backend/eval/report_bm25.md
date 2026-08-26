# BM25 基线评测报告

- 生成时间：2026-08-23T23:49:02
- 评测题数：50
- 命中数：41
- Hit@5：82.0%

## 分类命中率

| 类别 | 命中 / 总数 | 命中率 |
| --- | --- | --- |
| 制度类 | 18 / 18 | 100.0% |
| 产品资料类 | 15 / 16 | 93.8% |
| 技术文档类 | 8 / 16 | 50.0% |

## 难度命中率

| 难度 | 命中 / 总数 | 命中率 |
| --- | --- | --- |
| 简单 | 10 / 13 | 76.9% |
| 中等 | 29 / 35 | 82.9% |
| 难 | 2 / 2 | 100.0% |

## 未命中题目

| 编号 | 问题 | 预期文档 | 实际返回 |
| --- | --- | --- | --- |
| E020 | 如何用低代码平台创建一个审批表单？ | YQ-PROD-002 | YQ-PROD-012, YQ-PROD-003, YQ-PROD-003, YQ-PROD-005, YQ-INST-027 |
| E035 | Docker 容器是什么？ | YQ-TECH-DOCKER-003 | YQ-INST-005, YQ-PROD-011, YQ-INST-010, YQ-PROD-020, YQ-PROD-001 |
| E038 | Dockerfile 如何编写？ | YQ-TECH-DOCKER-007 | YQ-PROD-018, YQ-INST-021, YQ-TECH-DOCKER-027, YQ-PROD-008, YQ-PROD-023 |
| E040 | FastAPI path parameters 怎么用？ | YQ-TECH-FASTAPI-005 | YQ-TECH-FASTAPI-007, YQ-TECH-FASTAPI-006, YQ-TECH-FASTAPI-016, YQ-TECH-FASTAPI-014, YQ-TECH-FASTAPI-007 |
| E043 | FastAPI 如何编写测试？ | YQ-TECH-FASTAPI-019 | YQ-INST-026, YQ-INST-027, YQ-PROD-018, YQ-INST-021, YQ-INST-006 |
| E044 | Redis strings 支持哪些操作？ | YQ-TECH-REDIS-003 | YQ-PROD-003, YQ-PROD-003, YQ-PROD-006, YQ-PROD-008, YQ-PROD-008 |
| E047 | PostgreSQL JOIN 怎么使用？ | YQ-TECH-POSTGRESQL-004 | YQ-PROD-018, YQ-PROD-008, YQ-TECH-POSTGRESQL-016, YQ-INST-006, YQ-INST-030 |
| E048 | PostgreSQL indexes 有哪些类型？ | YQ-TECH-POSTGRESQL-023, YQ-TECH-POSTGRESQL-024 | YQ-PROD-008, YQ-PROD-003, YQ-TECH-POSTGRESQL-020, YQ-TECH-POSTGRESQL-020, YQ-INST-012 |
| E049 | LangChain agents 怎么使用？ | YQ-TECH-LANGCHAIN-007 | YQ-PROD-018, YQ-TECH-LANGCHAIN-027, YQ-TECH-LANGCHAIN-004, YQ-TECH-LANGCHAIN-023, YQ-TECH-LANGCHAIN-005 |

## 结论

- 整体 Hit@5 为 82.0%，共 9 道未命中。
- 最典型失败题：E020，问题“如何用低代码平台创建一个审批表单？”。

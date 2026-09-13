# 云启科技模拟数据包

用途：为“企业员工智能助手 / Agent 工程师面试项目”提供一套可解释、可演示、可扩展的模拟业务数据。

本目录不直接覆盖现有代码，而是作为数据参考资料。后续可以选择：

1. 只用于写演示脚本和面试讲稿。
2. 根据当前项目的数据模型，将其导入 SQLite。
3. 把演示主线涉及的制度文档补入 `data/clean`。

当前项目已提供导入命令：

```bash
cd backend
python -m app.interview_data_import
```

导入器会先校验数据，再按照员工、余额、请假申请的顺序写入，并通过 `app_settings` 记录数据版本。

数据覆盖：

- 员工与直属主管
- 部门负责人
- 2026 年年假余额
- 请假申请与审批状态
- 审批规则
- 面试演示场景

文件说明：

- `employees.json`：员工、部门、岗位、直属主管。
- `leave_balances.json`：2026 年年假总额、已用和剩余。
- `leave_requests.json`：请假单示例。
- `approval_rules.json`：审批边界规则。
- `demo_scenarios.md`：可以直接照着跑的面试演示脚本。
- `data_dictionary.md`：字段、状态和业务口径定义。
- `acceptance_checklist.md`：开发与演示验收标准。
- `validation_report.md`：本次数据校验结果。
- `data_model_plan.md`：JSON 到数据库的字段映射、状态流转和实施顺序。

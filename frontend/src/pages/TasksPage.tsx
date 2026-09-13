import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Empty,
  Input,
  Modal,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  CheckOutlined,
  CloseOutlined,
  ReloadOutlined
} from '@ant-design/icons'
import {
  AuthUser,
  AgentLeaveRequest,
  AgentPendingAction,
  cancelAgentAction,
  confirmAgentAction,
  listMyLeaveRequests,
  listPendingApprovals,
  prepareApproval,
  prepareRejection
} from '../api'

interface TasksPageProps {
  currentUser: AuthUser
}

const STATUS_COLORS: Record<AgentLeaveRequest['status'], string> = {
  待审批: 'orange',
  已批准: 'green',
  已拒绝: 'red',
  已取消: 'default'
}

export default function TasksPage({
  currentUser
}: TasksPageProps) {
  const [activeTab, setActiveTab] = useState('mine')
  const [mine, setMine] = useState<AgentLeaveRequest[]>([])
  const [approvals, setApprovals] = useState<AgentLeaveRequest[]>([])
  const [loading, setLoading] = useState(false)
  const [busyRequestId, setBusyRequestId] = useState('')
  const [pendingAction, setPendingAction] =
    useState<AgentPendingAction | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [rejectTarget, setRejectTarget] =
    useState<AgentLeaveRequest | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const isManager = currentUser.role === 'manager'

  const load = useCallback(async () => {
    if (!currentUser.employee_id) return
    setLoading(true)
    try {
      const mineData = await listMyLeaveRequests()
      setMine(mineData)
      if (isManager) {
        setApprovals(await listPendingApprovals())
      } else {
        setApprovals([])
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载任务失败')
    } finally {
      setLoading(false)
    }
  }, [currentUser.employee_id, isManager])

  useEffect(() => {
    if (!isManager && activeTab === 'approvals') {
      setActiveTab('mine')
    }
    load()
  }, [activeTab, isManager, load])

  const prepareApprove = async (record: AgentLeaveRequest) => {
    setBusyRequestId(record.request_id)
    try {
      setPendingAction(await prepareApproval(record.request_id))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '无法准备批准操作')
    } finally {
      setBusyRequestId('')
    }
  }

  const submitReject = async () => {
    if (!rejectTarget) return
    const reason = rejectReason.trim()
    if (!reason) {
      message.warning('请填写拒绝原因')
      return
    }
    setBusyRequestId(rejectTarget.request_id)
    try {
      setPendingAction(
        await prepareRejection(
          rejectTarget.request_id,
          reason
        )
      )
      setRejectTarget(null)
      setRejectReason('')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '无法准备拒绝操作')
    } finally {
      setBusyRequestId('')
    }
  }

  const confirmPending = async () => {
    if (!pendingAction) return
    setConfirming(true)
    try {
      const result = await confirmAgentAction(pendingAction.action_id)
      message.success(result.message)
      setPendingAction(null)
      await load()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '确认操作失败')
    } finally {
      setConfirming(false)
    }
  }

  const cancelPending = async () => {
    if (!pendingAction) return
    try {
      await cancelAgentAction(pendingAction.action_id)
    } catch {
      // The action may already have expired or been handled.
    } finally {
      setPendingAction(null)
    }
  }

  const columns: ColumnsType<AgentLeaveRequest> = [
    { title: '申请编号', dataIndex: 'request_id', width: 150 },
    { title: '申请人', dataIndex: 'employee_name', width: 90 },
    { title: '部门', dataIndex: 'department', width: 110 },
    {
      title: '请假时间',
      width: 200,
      render: (_, record) => `${record.start_date} 至 ${record.end_date}`
    },
    {
      title: '天数',
      dataIndex: 'days',
      width: 70,
      render: (value: number) => `${value} 天`
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (value: AgentLeaveRequest['status']) => (
        <Tag color={STATUS_COLORS[value]}>{value}</Tag>
      )
    },
    { title: '事由', dataIndex: 'reason', ellipsis: true },
    { title: '审批人', dataIndex: 'approver_id', width: 90 },
    {
      title: '操作',
      width: 150,
      render: (_, record) =>
        isManager && activeTab === 'approvals' ? (
          <Space size={4}>
            <Button
              type="link"
              size="small"
              icon={<CheckOutlined />}
              loading={busyRequestId === record.request_id}
              onClick={() => prepareApprove(record)}
            >
              批准
            </Button>
            <Button
              danger
              type="link"
              size="small"
              icon={<CloseOutlined />}
              onClick={() => {
                setRejectTarget(record)
                setRejectReason('')
              }}
            >
              拒绝
            </Button>
          </Space>
        ) : (
          <Typography.Text type="secondary">-</Typography.Text>
        )
    }
  ]

  return (
    <div style={{ maxWidth: 1180, margin: '0 auto' }}>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16
        }}
      >
        <Typography.Title level={3} style={{ margin: 0 }}>
          任务中心
        </Typography.Title>
        <Space>
          <Typography.Text strong>{currentUser.name}</Typography.Text>
          <Typography.Text type="secondary">
            {currentUser.department}
          </Typography.Text>
          <Tag color={isManager ? 'orange' : 'blue'}>
            {currentUser.employee_id === 'G001'
              ? '总经理'
              : isManager
                ? '主管'
                : currentUser.role === 'admin'
                  ? '管理员'
                  : '员工'}
          </Tag>
          <Button
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={load}
          >
            刷新
          </Button>
        </Space>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'mine',
            label: `我的申请（${mine.length}）`,
            children: (
              <Table
                rowKey="request_id"
                columns={columns}
                dataSource={mine}
                loading={loading}
                size="small"
                pagination={{ pageSize: 10, showSizeChanger: false }}
                locale={{ emptyText: <Empty description="暂无申请" /> }}
              />
            )
          },
          ...(isManager
            ? [
                {
                  key: 'approvals',
                  label: `待我审批（${approvals.length}）`,
                  children: (
                    <Table
                      rowKey="request_id"
                      columns={columns}
                      dataSource={approvals}
                      loading={loading}
                      size="small"
                      pagination={false}
                      locale={{
                        emptyText: <Empty description="暂无待审批任务" />
                      }}
                    />
                  )
                }
              ]
            : [])
        ]}
      />

      <Modal
        open={Boolean(rejectTarget)}
        title="填写拒绝原因"
        okText="下一步"
        cancelText="取消"
        confirmLoading={Boolean(busyRequestId)}
        onOk={submitReject}
        onCancel={() => {
          setRejectTarget(null)
          setRejectReason('')
        }}
      >
        <Input.TextArea
          value={rejectReason}
          onChange={(event) => setRejectReason(event.target.value)}
          autoSize={{ minRows: 3, maxRows: 6 }}
          placeholder="请输入拒绝原因"
        />
      </Modal>

      <Modal
        open={Boolean(pendingAction)}
        title="确认审批操作"
        okText={
          pendingAction?.tool === 'approve_leave_request'
            ? '确认批准'
            : '确认拒绝'
        }
        cancelText="取消"
        confirmLoading={confirming}
        onOk={confirmPending}
        onCancel={cancelPending}
      >
        <Alert
          type="warning"
          showIcon
          message="确认前不会修改申请状态"
          description={pendingAction?.summary}
        />
      </Modal>
    </div>
  )
}

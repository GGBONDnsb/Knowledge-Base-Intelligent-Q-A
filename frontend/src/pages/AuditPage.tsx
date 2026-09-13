import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  Select,
  Space,
  Table,
  Tag,
  Timeline,
  Typography,
  message
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined } from '@ant-design/icons'
import {
  AgentActionAuditDetail,
  AgentActionAuditItem,
  getAgentAction,
  listAgentActions
} from '../api'

const STATUS_COLORS: Record<string, string> = {
  待确认: 'orange',
  已完成: 'green',
  已取消: 'default',
  已过期: 'purple',
  执行失败: 'red'
}

const TOOL_LABELS: Record<string, string> = {
  submit_leave_request: '提交请假',
  approve_leave_request: '批准申请',
  reject_leave_request: '拒绝申请'
}

const EVENT_LABELS: Record<string, string> = {
  created: '已创建',
  confirmed: '用户已确认',
  executed: '执行成功',
  failed: '执行失败',
  cancelled: '用户已取消',
  expired: '确认已过期'
}

const EVENT_COLORS: Record<string, string> = {
  created: 'blue',
  confirmed: 'orange',
  executed: 'green',
  failed: 'red',
  cancelled: 'gray',
  expired: 'purple'
}

function formatTime(value: string | null) {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}

function eventDescription(type: string, detail: Record<string, unknown>) {
  if (type === 'failed') return String(detail.error ?? '')
  if (type === 'expired') return String(detail.reason ?? '')
  if (type === 'executed' && detail.request_id) {
    return `业务单号：${String(detail.request_id)}`
  }
  return ''
}

export default function AuditPage() {
  const [items, setItems] = useState<AgentActionAuditItem[]>([])
  const [detail, setDetail] = useState<AgentActionAuditDetail | null>(null)
  const [status, setStatus] = useState<string>()
  const [toolName, setToolName] = useState<string>()
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listAgentActions(status, toolName))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载操作记录失败')
    } finally {
      setLoading(false)
    }
  }, [status, toolName])

  useEffect(() => {
    load()
  }, [load])

  const openDetail = async (actionId: string) => {
    setDetailLoading(true)
    try {
      setDetail(await getAgentAction(actionId))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const columns: ColumnsType<AgentActionAuditItem> = [
    { title: '动作编号', dataIndex: 'action_id', width: 170 },
    { title: '操作人', dataIndex: 'actor_name', width: 110 },
    {
      title: '工具',
      dataIndex: 'tool_name',
      width: 130,
      render: (value: string) => TOOL_LABELS[value] ?? value
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={STATUS_COLORS[value] ?? 'default'}>{value}</Tag>
      )
    },
    { title: '操作摘要', dataIndex: 'summary', ellipsis: true },
    {
      title: '事件数',
      dataIndex: 'event_count',
      width: 80
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: formatTime
    },
    {
      title: '操作',
      width: 80,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => openDetail(record.action_id)}
        >
          查看
        </Button>
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
          操作记录
        </Typography.Title>
        <Space wrap>
          <Select
            allowClear
            placeholder="全部状态"
            value={status}
            onChange={setStatus}
            options={Object.keys(STATUS_COLORS).map((value) => ({
              label: value,
              value
            }))}
            style={{ width: 130 }}
          />
          <Select
            allowClear
            placeholder="全部工具"
            value={toolName}
            onChange={setToolName}
            options={Object.entries(TOOL_LABELS).map(([value, label]) => ({
              label,
              value
            }))}
            style={{ width: 150 }}
          />
          <Button icon={<ReloadOutlined />} loading={loading} onClick={load}>
            刷新
          </Button>
        </Space>
      </div>

      <Table
        rowKey="action_id"
        columns={columns}
        dataSource={items}
        loading={loading}
        size="small"
        pagination={{ pageSize: 15, showSizeChanger: false }}
        locale={{ emptyText: <Empty description="暂无操作记录" /> }}
      />

      <Drawer
        width={620}
        open={Boolean(detail)}
        loading={detailLoading}
        title={`操作详情 ${detail?.action_id ?? ''}`}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="操作人">
                {detail.actor_name}（{detail.actor_employee_id}）
              </Descriptions.Item>
              <Descriptions.Item label="工具">
                {TOOL_LABELS[detail.tool_name] ?? detail.tool_name}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLORS[detail.status] ?? 'default'}>
                  {detail.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="摘要">
                {detail.summary}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {formatTime(detail.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label="执行时间">
                {formatTime(detail.executed_at)}
              </Descriptions.Item>
              {detail.error_message && (
                <Descriptions.Item label="错误">
                  <Typography.Text type="danger">
                    {detail.error_message}
                  </Typography.Text>
                </Descriptions.Item>
              )}
            </Descriptions>

            <div>
              <Typography.Title level={5}>事件时间线</Typography.Title>
              <Timeline
                items={detail.events.map((event) => ({
                  color: EVENT_COLORS[event.event_type] ?? 'blue',
                  children: (
                    <div>
                      <Space>
                        <Typography.Text strong>
                          {EVENT_LABELS[event.event_type] ?? event.event_type}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          {event.actor_name}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          {formatTime(event.created_at)}
                        </Typography.Text>
                      </Space>
                      {eventDescription(event.event_type, event.detail) && (
                        <div style={{ marginTop: 4 }}>
                          {eventDescription(event.event_type, event.detail)}
                        </div>
                      )}
                    </div>
                  )
                }))}
              />
            </div>
          </Space>
        )}
      </Drawer>
    </div>
  )
}

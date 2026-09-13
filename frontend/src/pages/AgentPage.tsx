import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Collapse,
  Empty,
  Input,
  Space,
  Tag,
  Typography,
  message
} from 'antd'
import {
  CheckOutlined,
  CloseOutlined,
  SendOutlined
} from '@ant-design/icons'
import {
  AuthUser,
  AgentPendingAction,
  Citation,
  agentChat,
  cancelAgentAction,
  confirmAgentAction
} from '../api'

interface PendingMessageAction extends AgentPendingAction {
  status?: 'confirmed' | 'cancelled'
  resultMessage?: string
  busy?: boolean
}

interface AgentMessageItem {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  pendingAction?: PendingMessageAction
}

const EMPLOYEE_SAMPLES = [
  '我的年假余额还有多少？',
  '帮我提交 1 天年假申请',
  '年假申请需要提前几天？'
]

const MANAGER_SAMPLES = [
  '我有哪些待审批的申请？',
  '帮我提交 1 天年假申请',
  '年假申请需要提前几天？'
]

function formatPayload(action: AgentPendingAction) {
  const payload = action.payload as {
    leave_type?: string
    start_date?: string
    end_date?: string
    days?: number
    reason?: string
    employee_name?: string
    action?: string
    request_id?: string
    approver_id?: string
  }
  return [
    payload.employee_name ? `员工：${payload.employee_name}` : '',
    payload.request_id ? `申请编号：${payload.request_id}` : '',
    payload.action === 'approve'
      ? '操作：批准'
      : payload.action === 'reject'
        ? '操作：拒绝'
        : '',
    payload.leave_type ? `假别：${payload.leave_type}` : '',
    payload.start_date ? `日期：${payload.start_date} 至 ${payload.end_date}` : '',
    payload.days ? `天数：${payload.days} 天` : '',
    payload.reason ? `事由：${payload.reason}` : ''
  ]
    .filter(Boolean)
    .join(' · ')
}

interface AgentPageProps {
  currentUser: AuthUser
}

export default function AgentPage({ currentUser }: AgentPageProps) {
  const [messages, setMessages] = useState<AgentMessageItem[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const sessionRef = useRef<string>()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    sessionRef.current = undefined
    setMessages([])
  }, [currentUser.employee_id])

  const isManager = currentUser.role === 'manager'
  const samples = isManager ? MANAGER_SAMPLES : EMPLOYEE_SAMPLES

  const send = async (text?: string) => {
    const question = (text ?? input).trim()
    if (!question || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setLoading(true)
    try {
      const resp = await agentChat(question, sessionRef.current)
      sessionRef.current = resp.session_id
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: resp.answer,
          citations: resp.citations,
          pendingAction: resp.pending_action ?? undefined
        }
      ])
    } catch (err) {
      message.error(err instanceof Error ? err.message : '请求失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  const updateAction = (
    actionId: string,
    update: Partial<PendingMessageAction>
  ) => {
    setMessages((prev) =>
      prev.map((item) =>
        item.pendingAction?.action_id === actionId
          ? {
              ...item,
              pendingAction: { ...item.pendingAction, ...update }
            }
          : item
      )
    )
  }

  const handleConfirm = async (action: PendingMessageAction) => {
    updateAction(action.action_id, { busy: true })
    try {
      const resp = await confirmAgentAction(action.action_id)
      updateAction(action.action_id, {
        status: 'confirmed',
        resultMessage: resp.message,
        busy: false
      })
      message.success(resp.message)
    } catch (err) {
      updateAction(action.action_id, { busy: false })
      message.error(err instanceof Error ? err.message : '确认失败')
    }
  }

  const handleCancel = async (action: PendingMessageAction) => {
    updateAction(action.action_id, { busy: true })
    try {
      const resp = await cancelAgentAction(action.action_id)
      updateAction(action.action_id, {
        status: 'cancelled',
        resultMessage: resp.message,
        busy: false
      })
      message.success(resp.message)
    } catch (err) {
      updateAction(action.action_id, { busy: false })
      message.error(err instanceof Error ? err.message : '取消失败')
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12
        }}
      >
        <Typography.Title level={3} style={{ margin: 0 }}>
          业务助手
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
        </Space>
      </div>
      <Space wrap style={{ marginBottom: 16 }}>
        {samples.map((item) => (
          <Button key={item} size="small" onClick={() => send(item)}>
            {item}
          </Button>
        ))}
      </Space>
      <div
        style={{
          minHeight: 420,
          maxHeight: '60vh',
          overflowY: 'auto',
          background: '#fff',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          padding: 16
        }}
      >
        {messages.length === 0 ? (
          <Empty description="选择员工后开始业务会话" style={{ paddingTop: 120 }} />
        ) : (
          messages.map((item, index) => (
            <div key={index} style={{ marginBottom: 20 }}>
              {item.role === 'user' ? (
                <div style={{ textAlign: 'right' }}>
                  <div
                    style={{
                      display: 'inline-block',
                      background: '#1677ff',
                      color: '#fff',
                      padding: '8px 12px',
                      borderRadius: 8,
                      maxWidth: '75%',
                      whiteSpace: 'pre-wrap',
                      textAlign: 'left'
                    }}
                  >
                    {item.content}
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                    {item.content}
                  </div>
                  {item.pendingAction && (
                    <div
                      style={{
                        marginTop: 12,
                        padding: '10px 12px',
                        border:
                          item.pendingAction.status === 'confirmed'
                            ? '1px solid #b7eb8f'
                            : item.pendingAction.status === 'cancelled'
                              ? '1px solid #ffccc7'
                              : '1px solid #ffd591',
                        background:
                          item.pendingAction.status === 'confirmed'
                            ? '#f6ffed'
                            : item.pendingAction.status === 'cancelled'
                              ? '#fff2f0'
                              : '#fff7e6',
                        borderRadius: 8
                      }}
                    >
                      <Space style={{ marginBottom: 8 }}>
                        <Tag color="orange">待确认写操作</Tag>
                        <Typography.Text strong>
                          {item.pendingAction.summary}
                        </Typography.Text>
                      </Space>
                      <div>
                        <Typography.Text type="secondary">
                          {formatPayload(item.pendingAction)}
                        </Typography.Text>
                      </div>
                      {item.pendingAction.resultMessage && (
                        <Alert
                          type={
                            item.pendingAction.status === 'confirmed'
                              ? 'success'
                              : 'info'
                          }
                          showIcon
                          message={item.pendingAction.resultMessage}
                          style={{ marginTop: 8 }}
                        />
                      )}
                      {!item.pendingAction.status && (
                        <Space style={{ marginTop: 10 }}>
                          <Button
                            size="small"
                            type="primary"
                            icon={<CheckOutlined />}
                            loading={item.pendingAction.busy}
                            onClick={() => handleConfirm(item.pendingAction!)}
                          >
                            {item.pendingAction.tool === 'approve_leave_request'
                              ? '确认批准'
                              : item.pendingAction.tool ===
                                  'reject_leave_request'
                                ? '确认拒绝'
                                : '确认提交'}
                          </Button>
                          <Button
                            size="small"
                            danger
                            icon={<CloseOutlined />}
                            loading={item.pendingAction.busy}
                            onClick={() => handleCancel(item.pendingAction!)}
                          >
                            取消
                          </Button>
                        </Space>
                      )}
                    </div>
                  )}
                  {item.citations && item.citations.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <Typography.Text type="secondary">引用来源</Typography.Text>
                      <Collapse
                        size="small"
                        style={{ marginTop: 8 }}
                        items={item.citations.map((citation, i) => ({
                          key: String(i),
                          label: (
                            <Space size={4}>
                              <span>{citation.title}</span>
                              <Tag>{citation.heading}</Tag>
                              <Tag color="blue">{citation.doc_id}</Tag>
                            </Space>
                          ),
                          children: (
                            <div style={{ whiteSpace: 'pre-wrap' }}>
                              {citation.content}
                            </div>
                          )
                        }))}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入业务问题"
          autoSize={{ minRows: 1, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={loading}
          onClick={() => send()}
          style={{ height: 'auto' }}
        >
          发送
        </Button>
      </div>
    </div>
  )
}

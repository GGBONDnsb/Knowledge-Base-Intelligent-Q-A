import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Collapse, Empty, Input, Segmented, Space, Tag, Typography, message } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { Citation, chat } from '../api'

interface MessageItem {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  refused?: boolean
}

interface ChatPageProps {
  role: 'employee' | 'admin'
  onRoleChange: (value: 'employee' | 'admin') => void
}

const SAMPLES = ['年假怎么休', 'API 网关限流怎么配置', 'Docker 容器是什么']

export default function ChatPage({ role, onRoleChange }: ChatPageProps) {
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text?: string) => {
    const question = (text ?? input).trim()
    if (!question || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setLoading(true)
    try {
      const resp = await chat(question, role)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: resp.answer,
          citations: resp.citations,
          refused: resp.refused
        }
      ])
    } catch (err) {
      message.error(err instanceof Error ? err.message : '请求失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        知识问答
      </Typography.Title>
      <Space wrap style={{ marginBottom: 16 }}>
        {SAMPLES.map((item) => (
          <Button key={item} size="small" onClick={() => send(item)}>
            {item}
          </Button>
        ))}
      </Space>
      <Segmented
        options={[
          { label: '员工', value: 'employee' },
          { label: '管理员', value: 'admin' }
        ]}
        value={role}
        onChange={(value) => onRoleChange(value as 'employee' | 'admin')}
      />
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
          <Empty description="输入问题开始查询企业知识库" style={{ paddingTop: 120 }} />
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
                      whiteSpace: 'pre-wrap'
                    }}
                  >
                    {item.content}
                  </div>
                </div>
              ) : (
                <div>
                  {item.refused ? (
                    <Alert type="warning" showIcon message={item.content} />
                  ) : (
                    <>
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{item.content}</div>
                      {item.citations && item.citations.length > 0 && (
                        <div style={{ marginTop: 12 }}>
                          <Typography.Text type="secondary">引用来源</Typography.Text>
                          <Collapse
                            size="small"
                            style={{ marginTop: 8 }}
                            items={item.citations.map((c, i) => ({
                              key: String(i),
                              label: (
                                <Space size={4}>
                                  <span>{c.title}</span>
                                  <Tag>{c.heading}</Tag>
                                  <Tag color="blue">{c.doc_id}</Tag>
                                </Space>
                              ),
                              children: <div style={{ whiteSpace: 'pre-wrap' }}>{c.content}</div>
                            }))}
                          />
                        </div>
                      )}
                    </>
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
          placeholder="请输入你的问题"
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

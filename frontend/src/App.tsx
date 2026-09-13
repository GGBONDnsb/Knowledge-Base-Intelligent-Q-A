import { useEffect, useState } from 'react'
import {
  Button,
  Layout,
  Menu,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Typography,
  message
} from 'antd'
import {
  FileTextOutlined,
  HistoryOutlined,
  LogoutOutlined,
  MessageOutlined,
  RobotOutlined,
  ScheduleOutlined
} from '@ant-design/icons'
import {
  AuthUser,
  clearAuthToken,
  getAuthToken,
  getMe,
  logout,
  resetDemoData
} from './api'
import AgentPage from './pages/AgentPage'
import AuditPage from './pages/AuditPage'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import LoginPage from './pages/LoginPage'
import TasksPage from './pages/TasksPage'

const { Header, Content, Sider } = Layout

export default function App() {
  const [active, setActive] = useState<
    'chat' | 'agent' | 'tasks' | 'audit' | 'documents'
  >('chat')
  const [role, setRole] = useState<'employee' | 'admin'>('employee')
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)

  useEffect(() => {
    if (!getAuthToken()) {
      setAuthLoading(false)
      return
    }
    getMe()
      .then(setCurrentUser)
      .catch(() => clearAuthToken())
      .finally(() => setAuthLoading(false))
  }, [])

  useEffect(() => {
    const handleUnauthorized = () => setCurrentUser(null)
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    return () =>
      window.removeEventListener('auth:unauthorized', handleUnauthorized)
  }, [])

  const handleLogout = async () => {
    try {
      await logout()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '退出登录失败')
    } finally {
      clearAuthToken()
      setCurrentUser(null)
      setActive('chat')
    }
  }

  const handleResetDemoData = async () => {
    try {
      const result = await resetDemoData()
      message.success(
        `演示数据已重置：${result.employees} 名员工，${result.leave_requests} 条申请`
      )
      window.location.reload()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '重置失败')
    }
  }

  if (authLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!currentUser) {
    return <LoginPage onLogin={setCurrentUser} />
  }

  const roleLabel =
    currentUser.employee_id === 'G001'
      ? '总经理'
      : currentUser.role === 'manager'
        ? '主管'
        : currentUser.role === 'admin'
          ? '管理员'
          : '员工'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingInline: 24
        }}
      >
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600 }}>
          企业智能知识库问答系统
        </div>
        <Space>
          <Typography.Text style={{ color: '#fff' }}>
            {currentUser.name}
          </Typography.Text>
          <Tag color="blue">{roleLabel}</Tag>
          {currentUser.role === 'admin' && (
            <Popconfirm
              title="重置全部演示数据？"
              description="将恢复余额和申请单，并清空操作记录。"
              okText="确认重置"
              cancelText="取消"
              onConfirm={handleResetDemoData}
            >
              <Button ghost>重置演示数据</Button>
            </Popconfirm>
          )}
          <Button
            ghost
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            退出
          </Button>
        </Space>
      </Header>
      <Layout>
        <Sider width={200} theme="light" breakpoint="lg">
          <Menu
            mode="inline"
            selectedKeys={[active]}
            onClick={({ key }) =>
              setActive(
                key as 'chat' | 'agent' | 'tasks' | 'audit' | 'documents'
              )
            }
            style={{ height: '100%', borderRight: 0 }}
            items={[
              { key: 'chat', icon: <MessageOutlined />, label: '知识问答' },
              { key: 'agent', icon: <RobotOutlined />, label: '业务助手' },
              { key: 'tasks', icon: <ScheduleOutlined />, label: '任务中心' },
              { key: 'audit', icon: <HistoryOutlined />, label: '操作记录' },
              { key: 'documents', icon: <FileTextOutlined />, label: '文档管理' }
            ]}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          {active === 'chat' ? (
            <ChatPage role={role} onRoleChange={setRole} />
          ) : active === 'agent' ? (
            <AgentPage currentUser={currentUser} />
          ) : active === 'tasks' ? (
            <TasksPage currentUser={currentUser} />
          ) : active === 'audit' ? (
            <AuditPage />
          ) : (
            <DocumentsPage />
          )}
        </Content>
      </Layout>
    </Layout>
  )
}

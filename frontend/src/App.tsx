import { useState } from 'react'
import { Layout, Menu } from 'antd'
import { FileTextOutlined, MessageOutlined } from '@ant-design/icons'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'

const { Header, Content, Sider } = Layout

export default function App() {
  const [active, setActive] = useState('chat')
  const [role, setRole] = useState<'employee' | 'admin'>('employee')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', paddingInline: 24 }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600 }}>
          企业智能知识库问答系统
        </div>
      </Header>
      <Layout>
        <Sider width={200} theme="light" breakpoint="lg">
          <Menu
            mode="inline"
            selectedKeys={[active]}
            onClick={({ key }) => setActive(key)}
            style={{ height: '100%', borderRight: 0 }}
            items={[
              { key: 'chat', icon: <MessageOutlined />, label: '知识问答' },
              { key: 'documents', icon: <FileTextOutlined />, label: '文档管理' }
            ]}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          {active === 'chat' ? (
            <ChatPage role={role} onRoleChange={setRole} />
          ) : (
            <DocumentsPage />
          )}
        </Content>
      </Layout>
    </Layout>
  )
}

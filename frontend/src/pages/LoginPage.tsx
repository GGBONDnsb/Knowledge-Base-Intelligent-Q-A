import { useState } from 'react'
import {
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Typography,
  message
} from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { AuthUser, login, setAuthToken } from '../api'

const DEMO_ACCOUNTS = [
  {
    label: 'E001 张三 · 普通员工',
    value: 'zhangsan',
    username: 'zhangsan',
    password: 'Demo@123'
  },
  {
    label: 'M001 李明 · 部门主管',
    value: 'liming',
    username: 'liming',
    password: 'Demo@123'
  },
  {
    label: 'G001 周总 · 总经理',
    value: 'zhouzong',
    username: 'zhouzong',
    password: 'Demo@123'
  },
  {
    label: 'A001 王敏 · 管理员',
    value: 'admin',
    username: 'admin',
    password: 'Demo@123'
  }
]

interface LoginPageProps {
  onLogin: (user: AuthUser) => void
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const chooseAccount = (value: string) => {
    const account = DEMO_ACCOUNTS.find((item) => item.value === value)
    if (account) {
      form.setFieldsValue({
        username: account.username,
        password: account.password
      })
    }
  }

  const submit = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const result = await login(values.username, values.password)
      setAuthToken(result.token)
      onLogin(result.user)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        background: '#f5f5f5',
        padding: 24
      }}
    >
      <Card style={{ width: 420 }} title="企业知识增强 Agent">
        <Space direction="vertical" size={18} style={{ width: '100%' }}>
          <div>
            <Typography.Title level={4} style={{ marginBottom: 4 }}>
              登录工作台
            </Typography.Title>
            <Typography.Text type="secondary">
              使用演示账号进入业务助手和任务中心
            </Typography.Text>
          </div>
          <Select
            placeholder="选择演示身份"
            options={DEMO_ACCOUNTS}
            onChange={chooseAccount}
            style={{ width: '100%' }}
          />
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              username: 'zhangsan',
              password: 'Demo@123'
            }}
            onFinish={submit}
          >
            <Form.Item
              label="用户名"
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input prefix={<UserOutlined />} autoComplete="username" />
            </Form.Item>
            <Form.Item
              label="密码"
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                autoComplete="current-password"
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
            >
              登录
            </Button>
          </Form>
        </Space>
      </Card>
    </div>
  )
}

import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Popconfirm,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Upload,
  message
} from 'antd'
import type { UploadProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { InboxOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  DocumentItem,
  Stats,
  deleteDocument,
  getStats,
  listDocuments,
  reindexDocuments,
  uploadDocument
} from '../api'

const CATEGORY_COLORS: Record<string, string> = {
  制度类: 'green',
  产品资料类: 'blue',
  技术文档类: 'purple',
  其他: 'default'
}

const PERMISSION_COLORS: Record<string, string> = {
  全员: 'green',
  部门: 'blue',
  管理员: 'orange'
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [reindexing, setReindexing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [docList, statData] = await Promise.all([listDocuments(), getStats()])
      setDocs(docList)
      setStats(statData)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载文档失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const result = await uploadDocument(file)
      message.success(`已上传：${result.title}，共 ${result.chunk_count} 个文本块`)
      await load()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const uploadProps: UploadProps = {
    accept: '.md,.markdown,.txt,.html,.htm',
    showUploadList: false,
    beforeUpload: (file) => {
      handleUpload(file)
      return false
    }
  }

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId)
      message.success(`已删除 ${docId}`)
      await load()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleReindex = async () => {
    setReindexing(true)
    try {
      const result = await reindexDocuments()
      message.success(`索引已重建：${result.documents} 份文档，${result.chunks} 个文本块`)
      await load()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '重建索引失败')
    } finally {
      setReindexing(false)
    }
  }

  const columns: ColumnsType<DocumentItem> = [
    { title: '文档编号', dataIndex: 'doc_id', width: 190 },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    {
      title: '类别',
      dataIndex: 'category',
      width: 120,
      render: (value: string) => <Tag color={CATEGORY_COLORS[value] ?? 'default'}>{value}</Tag>
    },
    {
      title: '权限',
      dataIndex: 'permission',
      width: 100,
      render: (value: string) => <Tag color={PERMISSION_COLORS[value] ?? 'default'}>{value}</Tag>
    },
    { title: '负责人', dataIndex: 'owner', width: 110 },
    { title: '状态', dataIndex: 'status', width: 90 },
    { title: '文本块数', dataIndex: 'chunk_count', width: 90 },
    {
      title: '操作',
      width: 90,
      render: (_, record) => (
        <Popconfirm
          title="确认删除该文档？"
          description="删除后相关文本块和引用也会失效"
          onConfirm={() => handleDelete(record.doc_id)}
        >
          <Button size="small" danger type="link">
            删除
          </Button>
        </Popconfirm>
      )
    }
  ]

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        文档管理
      </Typography.Title>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="文档总数" value={stats?.documents ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="文本块总数" value={stats?.chunks ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="问答次数" value={stats?.question_count ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Space direction="vertical" size={2}>
              {Object.entries(stats?.categories ?? {}).map(([name, count]) => (
                <Typography.Text key={name} type="secondary">
                  {name}：{count}
                </Typography.Text>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>
      <Card
        size="small"
        style={{ marginBottom: 16 }}
        title="上传新文档"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={handleReindex}
            loading={reindexing}
          >
            重建索引
          </Button>
        }
      >
        <Upload.Dragger {...uploadProps} disabled={uploading}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
          <p className="ant-upload-hint">支持 Markdown、TXT、HTML 格式</p>
        </Upload.Dragger>
      </Card>
      <Table
        rowKey="doc_id"
        columns={columns}
        dataSource={docs}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: false }}
      />
    </div>
  )
}

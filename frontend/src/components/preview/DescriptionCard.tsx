import React, { useState, useRef, useCallback } from 'react';
import { Edit2, FileText, RefreshCw, BarChart3, Table, Image, TrendingUp, Sparkles, Trash } from 'lucide-react';
import { useT } from '@/hooks/useT';
import { useImagePaste } from '@/hooks/useImagePaste';
import { Card, ContextualStatusBadge, Button, Modal, Skeleton, Markdown, ElementEditorModal } from '@/components/shared';
import { MarkdownTextarea, type MarkdownTextareaRef } from '@/components/shared/MarkdownTextarea';
import { useDescriptionGeneratingState } from '@/hooks/useGeneratingState';
import type { Page, DescriptionContent, SlideElement } from '@/types';
import { reuseOutlineForDescription, refinePageDescription, deletePageElement } from '@/api/endpoints';

// DescriptionCard 组件自包含翻译
const descriptionCardI18n = {
  zh: {
    descriptionCard: {
      page: "第 {{num}} 页", regenerate: "重新生成", reuseOutline: "一键复用大纲",
      descriptionTitle: "编辑页面描述", description: "描述",
      noDescription: "还没有生成描述",
      uploadingImage: "正在上传图片...",
      descriptionPlaceholder: "输入页面描述, 可包含页面文字、素材、排版设计等信息，支持粘贴图片",
      coverPage: "封面",
      coverPageTooltip: "第一页为封面页，默认保持简洁风格",
      aiRefine: "AI修改",
      deleteElement: "删除元素",
      confirmDeleteElement: "确定要删除这个元素吗？",
      refinePlaceholder: "请输入修改要求...",
      enableWebSearch: "启用联网搜索",
      refining: "正在修改..."
    },
    elements: {
      sectionTitle: "页面元素",
      labels: "标签",
      table: "表格"
    }
  },
  en: {
    descriptionCard: {
      page: "Page {{num}}", regenerate: "Regenerate", reuseOutline: "Reuse Outline",
      descriptionTitle: "Edit Descriptions", description: "Description",
      noDescription: "No description generated yet",
      uploadingImage: "Uploading image...",
      descriptionPlaceholder: "Enter page description, can include page text, materials, layout design, etc., support pasting images",
      coverPage: "Cover",
      coverPageTooltip: "This is cover page, default to keep simple style",
      aiRefine: "AI Refine",
      deleteElement: "Delete Element",
      confirmDeleteElement: "Are you sure you want to delete this element?",
      refinePlaceholder: "Enter refinement requirement...",
      enableWebSearch: "Enable Web Search",
      refining: "Refining..."
    },
    elements: {
      sectionTitle: "Page Elements",
      labels: "Labels",
      table: "Table"
    }
  }
};

// 从 description_content 提取文本内容（提取到组件外部供 memo 比较器使用）
const getDescriptionText = (descContent: DescriptionContent | undefined): string => {
  if (!descContent) return '';
  if ('text' in descContent && typeof descContent.text === 'string') {
    return descContent.text.trim();
  } else if ('text_content' in descContent && Array.isArray(descContent.text_content)) {
    return descContent.text_content.filter(t => t).join('\n');
  }
  return '';
};

// 从 description_content 提取 elements
const getDescriptionElements = (descContent: DescriptionContent | undefined): SlideElement[] => {
  if (!descContent) return [];
  if ('elements' in descContent && Array.isArray(descContent.elements)) {
    return descContent.elements.filter(el => el && el.type);
  }
  return [];
};

// 从 description_content 提取标题
const getDescriptionTitle = (descContent: DescriptionContent | undefined): string => {
  if (!descContent) return '';
  if ('title' in descContent && typeof descContent.title === 'string') {
    return descContent.title.trim();
  }
  return '';
};

// 图表类型名称映射
const chartTypeNames: Record<string, string> = {
  bar: '柱状图',
  line: '折线图',
  pie: '饼图',
  area: '面积图',
  scatter: '散点图',
};

// 图表类型名称映射
const diagramTypeNames: Record<string, string> = {
  architecture: '架构图',
  flowchart: '流程图',
  mindmap: '思维导图',
  sequence: '时序图',
  timeline: '时间线',
};

// Elements 预览组件
const ElementsPreview: React.FC<{ 
  elements: SlideElement[]; 
  onEdit: (element: SlideElement) => void;
  onDelete: (index: number) => void;
}> = ({ elements, onEdit, onDelete }) => {
  const t = useT(descriptionCardI18n);

  if (!elements || elements.length === 0) return null;

  const renderElement = (el: SlideElement, idx: number) => {
    const elType = el.type;

    if (elType === 'chart') {
      const chartName = chartTypeNames[el.chart_type || 'bar'] || '图表';
      const labels = el.chart_data?.labels || [];
      const datasets = el.chart_data?.datasets || [];
      return (
        <div 
          key={idx} 
          className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 space-y-2 hover:ring-2 hover:ring-banana-400 transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-blue-700 dark:text-blue-400 font-medium text-sm">
              <BarChart3 size={16} />
              <span>{chartName}{el.content ? `: ${el.content}` : ''}</span>
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => onEdit(el)}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={() => onDelete(idx)}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
          {labels.length > 0 && (
            <div className="text-xs text-gray-600 dark:text-gray-400">
              {t('elements.labels')}: {labels.join(', ')}
            </div>
          )}
          {datasets.map((ds, i) => (
            <div key={i} className="text-xs text-gray-600 dark:text-gray-400">
              {ds.label}: [{ds.data.join(', ')}]
            </div>
          ))}
        </div>
      );
    }

    if (elType === 'table') {
      const tableData = el.table_data || [];
      if (tableData.length === 0) return null;
      const headers = tableData[0] || [];
      const rows = tableData.slice(1);
      return (
        <div 
          key={idx} 
          className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 space-y-2 hover:ring-2 hover:ring-banana-400 transition-all group"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-green-700 dark:text-green-400 font-medium text-sm">
              <Table size={16} />
              <span>{t('elements.table')}</span>
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => onEdit(el)}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={() => onDelete(idx)}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs border-collapse">
              <thead>
                <tr>
                  {headers.map((h, i) => (
                    <th key={i} className="border border-gray-300 dark:border-gray-600 px-2 py-1 bg-gray-100 dark:bg-gray-800 text-left font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j} className="border border-gray-300 dark:border-gray-600 px-2 py-1">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }
    
    if (elType === 'image') {
      const diagramName = el.diagram_type ? (diagramTypeNames[el.diagram_type] || '图片') : '图片';
      return (
        <div 
          key={idx} 
          className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3 hover:ring-2 hover:ring-banana-400 transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-purple-700 dark:text:purple-400 font-medium text-sm">
              <Image size={16} />
              <span>{diagramName}{el.content ? `: ${el.content}` : ''}</span>
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => onEdit(el)}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={() => onDelete(idx)}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
        </div>
      );
    }
    
    if (elType === 'kpi') {
      return (
        <div 
          key={idx} 
          className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3 hover:ring-2 hover:ring-banana-400 transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-orange-700 dark:text-orange-400 font-medium text-sm">
              <TrendingUp size={16} />
              <span>KPI: {el.kpi_label} = {el.kpi_value}</span>
              {el.kpi_trend && (
                <span className={`text-xs ${el.kpi_trend_color === 'green' ? 'text-green-600' : el.kpi_trend_color === 'red' ? 'text-red-600' : ''}`}>
                  {el.kpi_trend}
                </span>
              )}
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => onEdit(el)}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={() => onDelete(idx)}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
        </div>
      );
    }

    return null;
  };

  const visibleElements = elements.filter((el: SlideElement) =>
    ['chart', 'table', 'image', 'kpi'].includes(el.type)
  );

  if (visibleElements.length === 0) return null;

  return (
    <div className="mb-4 space-y-2">
      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {t('elements.sectionTitle')}
      </div>
      <div className="space-y-2">
        {visibleElements.map((el, idx) => renderElement(el, idx))}
      </div>
    </div>
  );
};

export interface DescriptionCardProps {
  page: Page;
  index: number;
  projectId?: string;
  showToast: (props: { message: string; type: 'success' | 'error' | 'info' | 'warning' }) => void;
  onUpdate: (data: Partial<Page>) => void;
  onRegenerate: () => void;
  isAiRefining?: boolean;
}

export const DescriptionCard: React.FC<DescriptionCardProps> = React.memo(({
  page,
  index,
  projectId,
  showToast,
  onUpdate,
  onRegenerate,
  isAiRefining = false,
}) => {
  const t = useT(descriptionCardI18n);

  const text = getDescriptionText(page.description_content);
  const elements = getDescriptionElements(page.description_content);
  const title = getDescriptionTitle(page.description_content);
  
  const [isEditing, setIsEditing] = useState(false);
  const [localAiRefining, setLocalAiRefining] = useState(false);
  const [showAiRefineInput, setShowAiRefineInput] = useState(false);
  const [aiRefineInput, setAiRefineInput] = useState('');
  const [enableWebSearch, setEnableWebSearch] = useState(true);
  const [editingElement, setEditingElement] = useState<SlideElement | null>(null);
  const [editContent, setEditContent] = useState('');
  const textareaRef = useRef<MarkdownTextareaRef>(null);

  // Callback to insert at cursor position in textarea
  const insertAtCursor = useCallback((markdown: string) => {
    textareaRef.current?.insertAtCursor(markdown);
  }, []);

  const { handlePaste, handleFiles, isUploading } = useImagePaste({
    projectId,
    setContent: setEditContent,
    showToast,
    insertAtCursor,
  });

  // 通过 page.status 驱动骨架屏，与图片生成的 GENERATING 状态互不干扰
  const generating = useDescriptionGeneratingState(page, isAiRefining);

  const handleEditReuseOutline = async () => {
    try {
      if (!projectId || !page.page_id) {
        showToast({
          message: '页面信息不完整，无法复用大纲',
          type: 'error'
        });
        return;
      }

      const response = await reuseOutlineForDescription(projectId, page.page_id);
      if (response.success) {
        showToast({
          message: '已成功复用大纲生成描述',
          type: 'success'
        });
        if (response.data?.page) {
          onUpdate(response.data.page);
        }
      } else {
        showToast({
          message: response.message || '复用大纲失败',
          type: 'error'
        });
      }
    } catch (error: any) {
      console.error('复用大纲时发生错误:', error);
      showToast({
        message: error.message || '复用大纲时发生错误',
        type: 'error'
      });
    }
  };

  const handleEdit = () => {
    // 在打开编辑对话框时，从当前的 page 获取最新值
    const currentText = getDescriptionText(page.description_content);
    setEditContent(currentText);
    setIsEditing(true);
  };

  const handleSave = () => {
    const currentDesc = page.description_content as any;
    const existingElements = currentDesc?.elements || [];
    const currentTitle = getDescriptionTitle(page.description_content);
 
    onUpdate({
      description_content: {
        text: editContent,
        title: currentTitle,
        elements: existingElements,
        generated_at: currentDesc?.generated_at,
      } as DescriptionContent,
    });
    setIsEditing(false);
  };

  const handleAiRefine = async () => {
    if (!projectId || !page.page_id || !aiRefineInput.trim()) {
      if (!projectId || !page.page_id) {
        showToast({ message: '页面信息不完整，无法修改', type: 'error' });
      }
      return;
    }

    setLocalAiRefining(true);
    try {
      const response = await refinePageDescription(projectId, page.page_id, aiRefineInput, enableWebSearch);
      if (response.success) {
        onUpdate(response.data.page);
        showToast({ message: '描述修改成功', type: 'success' });
        setShowAiRefineInput(false);
        setAiRefineInput('');
      } else {
        showToast({ message: response.message || '描述修改失败', type: 'error' });
      }
    } catch (error: any) {
      console.error('描述修改失败:', error);
      showToast({ message: error.message || '描述修改失败', type: 'error' });
    } finally {
      setLocalAiRefining(false);
    }
  };

  const handleDeleteElement = async (elementIndex: number) => {
    if (!projectId || !page.page_id) {
      showToast({ message: '页面信息不完整，无法删除元素', type: 'error' });
      return;
    }

    try {
      const response = await deletePageElement(projectId, page.page_id, elementIndex, 'description');
      if (response.success) {
        onUpdate(response.data.page);
        showToast({ message: '元素删除成功', type: 'success' });
      } else {
        showToast({ message: response.message || '元素删除失败', type: 'error' });
      }
    } catch (error: any) {
      console.error('元素删除失败:', error);
      showToast({ message: error.message || '元素删除失败', type: 'error' });
    }
  };

  return (
    <>
      <Card className="p-0 overflow-hidden flex flex-col">
        {/* 标题栏 */}
        <div className="bg-banana-50 dark:bg-background-hover px-4 py-3 border-b border-gray-100 dark:border-border-primary">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900 dark:text-foreground-primary">{t('descriptionCard.page', { num: index + 1 })}</span>
              {index === 0 && (
                <span
                  className="text-xs px-1.5 py-0.5 bg-banana-100 dark:bg-banana-900/30 text-banana-700 dark:text-banana-400 rounded"
                  title={t('descriptionCard.coverPageTooltip')}
                >
                  {t('descriptionCard.coverPage')}
                </span>
              )}
              {page.part && (
                <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded">
                  {page.part}
                </span>
              )}
            </div>
            <ContextualStatusBadge page={page} context="description" />
          </div>
        </div>

        {/* 内容 */}
        <div className="p-4 flex-1 max-h-96 overflow-y-auto desc-card-scroll" data-testid="description-card-content">
          {generating ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <div className="text-center py-4 text-gray-500 dark:text-foreground-tertiary text-sm">
                {t('common.generating')}
              </div>
            </div>
          ) : (text || title || elements.length > 0) ? (
            <>
              {title && (
                <h4 className="font-semibold text-gray-900 dark:text-foreground-primary mb-3 text-base">
                  {title}
                </h4>
              )}
              {text && (
                <div className="text-sm text-gray-700 dark:text-foreground-secondary mb-3">
                  <Markdown>{text}</Markdown>
                </div>
              )}
              <ElementsPreview 
                elements={elements} 
                onEdit={setEditingElement}
                onDelete={handleDeleteElement}
              />
              
              {/* AI修改输入框 */}
              {showAiRefineInput && (
                <div className="mt-3 p-3 bg-banana-50 dark:bg-banana-900/20 rounded-lg border border-banana-200 dark:border-banana-800">
                  <textarea
                    value={aiRefineInput}
                    onChange={(e) => setAiRefineInput(e.target.value)}
                    placeholder={t('descriptionCard.refinePlaceholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500 resize-none"
                    rows={3}
                  />
                  <div className="flex items-center justify-between mt-2">
                    <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                      <input
                        type="checkbox"
                        checked={enableWebSearch}
                        onChange={(e) => setEnableWebSearch(e.target.checked)}
                        className="rounded border-gray-300 text-banana-500 focus:ring-banana-500"
                      />
                      {t('descriptionCard.enableWebSearch')}
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setShowAiRefineInput(false)}
                        className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                      >
                        {t('common.cancel')}
                      </button>
                      <button
                        onClick={handleAiRefine}
                        disabled={localAiRefining || !aiRefineInput.trim()}
                        className="px-3 py-1.5 text-sm bg-banana-500 text-white rounded-lg hover:bg-banana-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {localAiRefining ? t('descriptionCard.refining') : t('descriptionCard.aiRefine')}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-8 text-gray-400 dark:text-foreground-tertiary">
              <div className="flex text-3xl mb-2 justify-center"><FileText className="text-gray-400 dark:text-foreground-tertiary" size={48} /></div>
              <p className="text-sm">{t('descriptionCard.noDescription')}</p>
            </div>
          )}
        </div>

        {/* 操作栏 */}
        <div className="border-t border-gray-100 dark:border-border-primary px-4 py-3 flex justify-end gap-2 mt-auto">
          <Button
            variant="ghost"
            size="sm"
            icon={<Sparkles size={16} />}
            onClick={() => setShowAiRefineInput(!showAiRefineInput)}
            disabled={generating}
            title={t('descriptionCard.aiRefine')}
          >
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<Edit2 size={16} />}
            onClick={handleEdit}
            disabled={generating}
          >
            {t('common.edit')}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={16} className={generating ? 'animate-spin' : ''} />}
            onClick={onRegenerate}
            disabled={generating}
          >
            {generating ? t('common.generating') : t('descriptionCard.regenerate')}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleEditReuseOutline}
            disabled={generating}
          >
            {t('descriptionCard.reuseOutline')}
          </Button>
        </div>
      </Card>

      {/* 编辑对话框 */}
      <Modal
        isOpen={isEditing}
        onClose={() => setIsEditing(false)}
        title={t('descriptionCard.descriptionTitle')}
        size="lg"
      >
        <div className="space-y-4">
          <MarkdownTextarea
            ref={textareaRef}
            label={t('descriptionCard.description')}
            value={editContent}
            onChange={setEditContent}
            onPaste={handlePaste}
            onFiles={handleFiles}
            rows={12}
            placeholder={t('descriptionCard.descriptionPlaceholder')}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setIsEditing(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="primary" onClick={handleSave} disabled={isUploading}>
              {t('common.save')}
            </Button>
          </div>
        </div>
      </Modal>
      
      {/* 元素编辑对话框 */}
      {editingElement && (
        <ElementEditorModal
          isOpen={!!editingElement}
          onClose={() => setEditingElement(null)}
          element={editingElement}
          projectId={projectId}
          pageId={page.page_id}
          source="description"
          elementIndex={elements.findIndex((el: SlideElement) => el === editingElement)}
          onSave={(updatedElement) => {
            const currentDesc = page.description_content as any;
            const existingElements = currentDesc?.elements || [];
            const index = existingElements.findIndex((el: SlideElement) => el === editingElement);
            
            if (index !== -1) {
              const newElements = [...existingElements];
              newElements[index] = updatedElement;
              onUpdate({
                description_content: {
                  ...currentDesc,
                  elements: newElements,
                },
              });
            }
            setEditingElement(null);
          }}
        />
      )}
    </>
  );
}, (prev, next) =>
  prev.index === next.index &&
  prev.isAiRefining === next.isAiRefining &&
  prev.projectId === next.projectId &&
  prev.page.id === next.page.id &&
  prev.page.status === next.page.status &&
  prev.page.part === next.page.part &&
  getDescriptionTitle(prev.page.description_content) === getDescriptionTitle(next.page.description_content) &&
  getDescriptionText(prev.page.description_content) === getDescriptionText(next.page.description_content) &&
  JSON.stringify(getDescriptionElements(prev.page.description_content)) === JSON.stringify(getDescriptionElements(next.page.description_content))
);

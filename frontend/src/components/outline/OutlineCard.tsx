import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GripVertical, Edit2, Trash2, Check, X, Sparkles, Trash } from 'lucide-react';
import { useT } from '@/hooks/useT';
import { useImagePaste } from '@/hooks/useImagePaste';
import { Card, useConfirm, Markdown, ShimmerOverlay, ElementEditorModal } from '@/components/shared';
import { MarkdownTextarea, type MarkdownTextareaRef } from '@/components/shared/MarkdownTextarea';
import type { Page, SlideElement } from '@/types';
import { refinePageOutline, deletePageElement } from '@/api/endpoints';

// OutlineCard 组件自包含翻译
const outlineCardI18n = {
  zh: {
    outlineCard: {
      page: "第 {{num}} 页", chapter: "章节", titleLabel: "标题",
      keyPointsPlaceholder: "要点（每行一个，支持粘贴图片）", confirmDeletePage: "确定要删除这一页吗？",
      confirmDeleteTitle: "确认删除",
      uploadingImage: "正在上传图片...",
      coverPage: "封面",
      coverPageTooltip: "第一页为封面页，通常包含标题和副标题",
      table: "表格",
      chart: "图表",
      image: "图片",
      kpi: "指标",
      aiRefine: "AI修改",
      deleteElement: "删除元素",
      confirmDeleteElement: "确定要删除这个元素吗？",
      refinePlaceholder: "请输入修改要求...",
      enableWebSearch: "启用联网搜索",
      refining: "正在修改...",
      webSearching: "正在联网搜索..."
    }
  },
  en: {
    outlineCard: {
      page: "Page {{num}}", chapter: "Chapter", titleLabel: "Title",
      keyPointsPlaceholder: "Key points (one per line, paste images supported)", confirmDeletePage: "Are you sure you want to delete this page?",
      confirmDeleteTitle: "Confirm Delete",
            uploadingImage: "Uploading image...",
      coverPage: "Cover",
      coverPageTooltip: "This is the cover page, usually containing the title and subtitle",
      table: "Table",
      chart: "Chart",
      image: "Image",
      kpi: "KPI",
      aiRefine: "AI Refine",
      deleteElement: "Delete Element",
      confirmDeleteElement: "Are you sure you want to delete this element?",
      refinePlaceholder: "Enter refinement requirement...",
      enableWebSearch: "Enable Web Search",
      refining: "Refining...",
      webSearching: "Web searching..."
    }
  }
};

// 元素预览组件
const ElementPreview: React.FC<{ 
  element: SlideElement; 
  t: any; 
  onEdit: (element: SlideElement) => void;
  onDelete: () => void;
}> = ({ element, t, onEdit, onDelete }) => {
  const handleClick = () => {
    onEdit(element);
  };

  switch (element.type) {
    case 'table':
      return (
        <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 hover:ring-2 hover:ring-banana-400 transition-all group">
          <div className="flex items-center justify-between mb-1">
            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">
              📊 {t('outlineCard.table')}
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleClick}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(); }}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
          {element.table_data && element.table_data.length > 0 && (
            <>
              <div className="text-xs text-gray-600 dark:text-gray-400 font-medium">
                {element.table_data[0]?.join(' | ') || ''}
              </div>
              {element.table_data.slice(1, 3).map((row: string[], i: number) => (
                <div key={i} className="text-xs text-gray-500 dark:text-gray-500">
                  {row.join(' | ')}
                </div>
              ))}
              {element.table_data.length > 3 && (
                <div className="text-xs text-gray-400 dark:text-gray-600 mt-1">
                  +{element.table_data.length - 3} rows...
                </div>
              )}
            </>
          )}
        </div>
      );
    
    case 'chart':
      return (
        <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800 hover:ring-2 hover:ring-banana-400 transition-all group">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-blue-700 dark:text-blue-400">
              📈 {element.chart_type} {t('outlineCard.chart')}: {element.content || ''}
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleClick}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(); }}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
        </div>
      );
    
    case 'image':
      return (
        <div className="mt-2 p-2 bg-purple-50 dark:bg-purple-900/20 rounded border border-purple-200 dark:border-purple-800 hover:ring-2 hover:ring-banana-400 transition-all group">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-purple-700 dark:text-purple-400">
              🖼️ {element.diagram_type || t('outlineCard.image')}: {element.content || element.image_prompt || ''}
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleClick}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(); }}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
        </div>
      );
    
    case 'kpi':
      return (
        <div className="mt-2 p-2 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800 hover:ring-2 hover:ring-banana-400 transition-all group">
          <div className="flex items-center justify-between">
            <div className="text-sm font-bold text-green-700 dark:text-green-400">
              {element.kpi_value} <span className="text-xs font-normal">{element.kpi_label}</span>
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleClick}
                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                title="Edit"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(); }}
                className="p-1 text-red-600 hover:bg-red-100 rounded"
                title="Delete"
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
          {element.kpi_trend && (
            <div className="text-xs text-green-600 dark:text-green-500">
              {element.kpi_trend}
            </div>
          )}
        </div>
      );
    
    default:
      return null;
  }
};

interface OutlineCardProps {
  page: Page;
  index: number;
  projectId?: string;
  showToast: (props: { message: string; type: 'success' | 'error' | 'info' | 'warning' }) => void;
  onUpdate: (data: Partial<Page>) => void;
  onDelete: () => void;
  onClick: () => void;
  isSelected: boolean;
  dragHandleProps?: React.HTMLAttributes<HTMLDivElement>;
  isAiRefining?: boolean;
}

export const OutlineCard: React.FC<OutlineCardProps> = ({
  page,
  index,
  projectId,
  showToast,
  onUpdate,
  onDelete,
  onClick,
  isSelected,
  dragHandleProps,
  isAiRefining = false,
}) => {
  const t = useT(outlineCardI18n);
  const { confirm, ConfirmDialog } = useConfirm();
  const outline = page.outline_content ?? { title: '', points: [] as string[] };
  const elements = (page.outline_content as any)?.elements || [];
  const [isEditing, setIsEditing] = useState(false);
  const [localAiRefining, setLocalAiRefining] = useState(false);
  const [showAiRefineInput, setShowAiRefineInput] = useState(false);
  const [aiRefineInput, setAiRefineInput] = useState('');
  const [enableWebSearch, setEnableWebSearch] = useState(true);
  const [editingElement, setEditingElement] = useState<SlideElement | null>(null);
  const [editTitle, setEditTitle] = useState(outline.title);
  const [editPoints, setEditPoints] = useState(outline.points.join('\n'));
  const [editPart, setEditPart] = useState(page.part || '');
  const textareaRef = useRef<MarkdownTextareaRef>(null);

  // Callback to insert at cursor position in textarea
  const insertAtCursor = useCallback((markdown: string) => {
    textareaRef.current?.insertAtCursor(markdown);
  }, []);

  const { handlePaste, handleFiles, isUploading } = useImagePaste({
    projectId,
    setContent: setEditPoints,
    showToast,
    insertAtCursor,
  });

  // 当 page prop 变化时，同步更新本地编辑状态（如果不在编辑模式）
  useEffect(() => {
    if (!isEditing) {
      setEditTitle(outline.title);
      setEditPoints(outline.points.join('\n'));
      setEditPart(page.part || '');
    }
  }, [outline.title, outline.points, page.part, isEditing]);

  const handleSave = () => {
    const currentOutline = page.outline_content as any;
    const existingElements = currentOutline?.elements || [];
    const existingSlideType = currentOutline?.slide_type;
    const existingLayoutStyle = currentOutline?.layout_style;
    const existingLayoutVariant = currentOutline?.layout_variant;
    
    onUpdate({
      outline_content: {
        title: editTitle,
        points: editPoints.split('\n').filter((p) => p.trim()),
        elements: existingElements,
        slide_type: existingSlideType,
        layout_style: existingLayoutStyle,
        layout_variant: existingLayoutVariant,
      },
      part: editPart.trim() || undefined,
    });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditTitle(outline.title);
    setEditPoints(outline.points.join('\n'));
    setEditPart(page.part || '');
    setIsEditing(false);
  };

  const handleAiRefine = async () => {
    if (!projectId || !aiRefineInput.trim()) return;
    
    setLocalAiRefining(true);
    try {
      const response = await refinePageOutline(projectId, page.page_id, aiRefineInput, enableWebSearch);
      if (response.success) {
        onUpdate(response.data.page);
        showToast({ message: '大纲修改成功', type: 'success' });
        setShowAiRefineInput(false);
        setAiRefineInput('');
      } else {
        showToast({ message: response.message || '大纲修改失败', type: 'error' });
      }
    } catch (error: any) {
      showToast({ message: error.message || '大纲修改失败', type: 'error' });
    } finally {
      setLocalAiRefining(false);
    }
  };

  const handleDeleteElement = async (elementIndex: number) => {
    if (!projectId) return;
    
    try {
      const response = await deletePageElement(projectId, page.page_id, elementIndex, 'outline');
      if (response.success) {
        onUpdate(response.data.page);
        showToast({ message: '元素删除成功', type: 'success' });
      } else {
        showToast({ message: response.message || '元素删除失败', type: 'error' });
      }
    } catch (error: any) {
      showToast({ message: error.message || '元素删除失败', type: 'error' });
    }
  };

  return (
    <Card
      className={`p-4 relative ${
        isSelected ? 'border-2 border-banana-500 shadow-yellow' : ''
      }`}
      onClick={!isEditing ? onClick : undefined}
    >
      <ShimmerOverlay show={isAiRefining || localAiRefining} />

      <div className="flex items-start gap-3 relative z-10">
        {/* 拖拽手柄 */}
        <div
          {...dragHandleProps}
          className="flex-shrink-0 cursor-move text-gray-400 hover:text-gray-600 pt-1"
        >
          <GripVertical size={20} />
        </div>

        {/* 内容区 */}
        <div className="flex-1 min-w-0">
          {/* 页码和章节 */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-semibold text-gray-900 dark:text-foreground-primary">
              {t('outlineCard.page', { num: index + 1 })}
            </span>
            {index === 0 && !isEditing && (
              <span
                className="text-xs px-1.5 py-0.5 bg-banana-100 dark:bg-banana-900/30 text-banana-700 dark:text-banana-400 rounded"
                title={t('outlineCard.coverPageTooltip')}
              >
                {t('outlineCard.coverPage')}
              </span>
            )}
            {isEditing ? (
              <input
                type="text"
                value={editPart}
                onChange={(e) => setEditPart(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="text-xs px-2 py-0.5 w-24 border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder={t('outlineCard.chapter')}
              />
            ) : (
              page.part && (
                <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded">
                  {page.part}
                </span>
              )
            )}
          </div>

          {isEditing ? (
            /* 编辑模式 */
            <div className="space-y-3" onClick={(e) => e.stopPropagation()}>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-border-primary bg-white dark:bg-background-secondary text-gray-900 dark:text-foreground-primary rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500"
                placeholder={t('outlineCard.titleLabel')}
              />
              <div>
                <MarkdownTextarea
                  ref={textareaRef}
                  value={editPoints}
                  onChange={setEditPoints}
                  onPaste={handlePaste}
                  onFiles={handleFiles}
                  rows={5}
                  placeholder={t('outlineCard.keyPointsPlaceholder')}
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  onClick={handleCancel}
                  className="px-3 py-1.5 text-sm text-gray-700 dark:text-foreground-secondary hover:bg-gray-100 dark:hover:bg-background-hover rounded-lg transition-colors"
                >
                  <X size={16} className="inline mr-1" />
                  {t('common.cancel')}
                </button>
                <button
                  onClick={handleSave}
                  disabled={isUploading}
                  className="px-3 py-1.5 text-sm bg-banana-500 text-black dark:text-white rounded-lg hover:bg-banana-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Check size={16} className="inline mr-1" />
                  {t('common.save')}
                </button>
              </div>
            </div>
          ) : (
            /* 查看模式 */
            <div>
              <h4 className="font-semibold text-gray-900 dark:text-foreground-primary mb-2">
                {outline.title}
              </h4>
              
              {/* 展示要点 */}
              <div className="text-gray-600 dark:text-foreground-tertiary mb-2">
                <Markdown>{outline.points.join('\n')}</Markdown>
                           </div>
              
              {/* 展示元素预览 */}
              {elements.length > 0 && (
                <div className="space-y-1">
                  {elements.map((element: SlideElement, idx: number) => (
                    <ElementPreview 
                      key={idx} 
                      element={element} 
                      t={t} 
                      onEdit={setEditingElement}
                      onDelete={() => handleDeleteElement(idx)}
                    />
                  ))}
                </div>
              )}
              
              {/* AI修改输入框 */}
              {showAiRefineInput && (
                <div className="mt-3 p-3 bg-banana-50 dark:bg-banana-900/20 rounded-lg border border-banana-200 dark:border-banana-800">
                  <textarea
                    value={aiRefineInput}
                    onChange={(e) => setAiRefineInput(e.target.value)}
                    placeholder={t('outlineCard.refinePlaceholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500 resize-none"
                    rows={3}
                  />
                  <div className="flex items-center justify-between mt-2">
                    <label className="flex items-center gap-2 text-sm text-gray-600 dark:text:text-gray-400">
                      <input
                        type="checkbox"
                        checked={enableWebSearch}
                        onChange={(e) => setEnableWebSearch(e.target.checked)}
                        className="rounded border-gray-300 text-banana-500 focus:ring-banana-500"
                      />
                      {t('outlineCard.enableWebSearch')}
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
                        {localAiRefining ? t('outlineCard.refining') : t('outlineCard.aiRefine')}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 操作按钮 */}
        {!isEditing && (
          <div className="flex-shrink-0 flex gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowAiRefineInput(!showAiRefineInput);
              }}
              className="p-1.5 text-gray-500 dark:text-foreground-tertiary hover:text-banana-600 hover:bg-banana-50 dark:hover:bg-background-hover rounded transition-colors"
              title={t('outlineCard.aiRefine')}
            >
              <Sparkles size={16} />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsEditing(true);
              }}
              className="p-1.5 text-gray-500 dark:text-foreground-tertiary hover:text-banana-600 hover:bg-banana-50 dark:hover:bg-background-hover rounded transition-colors"
            >
              <Edit2 size={16} />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                confirm(
                  t('outlineCard.confirmDeletePage'),
                  onDelete,
                  { title: t('outlineCard.confirmDeleteTitle'), variant: 'danger' }
                );
              }}
              className="p-1.5 text-gray-500 dark:text-foreground-tertiary hover:text-red-600 hover:bg-red-50 rounded transition-colors"
            >
              <Trash2 size={16} />
            </button>
          </div>
        )}
      </div>
      {ConfirmDialog}
      
      {/* 元素编辑对话框 */}
      {editingElement && (
        <ElementEditorModal
          isOpen={!!editingElement}
          onClose={() => setEditingElement(null)}
          element={editingElement}
          projectId={projectId}
          pageId={page.page_id}
          source="outline"
          elementIndex={elements.findIndex((el: SlideElement) => el === editingElement)}
          onSave={(updatedElement) => {
            const currentOutline = page.outline_content as any;
            const existingElements = currentOutline?.elements || [];
            const index = existingElements.findIndex((el: SlideElement) => el === editingElement);
            
            if (index !== -1) {
              const newElements = [...existingElements];
              newElements[index] = updatedElement;
              onUpdate({
                outline_content: {
                  ...currentOutline,
                  elements: newElements,
                },
              });
            }
            setEditingElement(null);
          }}
        />
      )}
    </Card>
  );
};

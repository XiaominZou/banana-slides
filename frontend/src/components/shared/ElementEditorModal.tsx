import React, { useState } from 'react';
import { Modal } from './Modal';
import { TableEditor } from './element-editors/TableEditor';
import { ChartEditor } from './element-editors/ChartEditor';
import { ImageEditor } from './element-editors/ImageEditor';
import { KPIEditor } from './element-editors/KPIEditor';
import type { SlideElement } from '@/types';
import { refinePageElement } from '@/api/endpoints';

interface ElementEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  element: SlideElement;
  projectId?: string;
  pageId?: string;
  source?: 'outline' | 'description';
  elementIndex?: number;
  onSave: (updatedElement: SlideElement) => void;
  showToast?: (props: { message: string; type: 'success' | 'error' | 'info' | 'warning' }) => void;
}

// 获取元素类型的中文名称
const getElementTypeName = (type: string): string => {
  const typeNames: Record<string, string> = {
    table: '表格',
    chart: '图表',
    image: '图片',
    kpi: 'KPI指标',
  };
  return typeNames[type] || '元素';
};

export const ElementEditorModal: React.FC<ElementEditorModalProps> = ({
  isOpen,
  onClose,
  element,
  projectId,
  pageId,
  source = 'outline',
  elementIndex,
  onSave,
  showToast,
}) => {
  const [activeTab, setActiveTab] = useState<'manual' | 'ai'>('manual');
  const [aiRefineInput, setAiRefineInput] = useState('');
  const [enableWebSearch, setEnableWebSearch] = useState(true);
  const [isAiRefining, setIsAiRefining] = useState(false);

  const handleSave = (updatedElement: SlideElement) => {
    onSave(updatedElement);
    onClose();
  };

  const handleAiRefine = async () => {
    if (!projectId || !pageId || elementIndex === undefined || !aiRefineInput.trim()) return;
    
    setIsAiRefining(true);
    try {
      const response = await refinePageElement(
        projectId,
        pageId,
        elementIndex,
        source,
        aiRefineInput,
        enableWebSearch
      );
      
      if (response.success && response.data.page) {
        const updatedPage = response.data.page;
        const updatedElements = source === 'outline' 
          ? (updatedPage.outline_content as any)?.elements || []
          : (updatedPage.description_content as any)?.elements || [];
        
        if (updatedElements[elementIndex]) {
          onSave(updatedElements[elementIndex]);
          onClose();
          if (showToast) {
            showToast({ message: '元素修改成功', type: 'success' });
          }
        }
      } else {
        if (showToast) {
          showToast({ message: response.message || '元素修改失败', type: 'error' });
        }
      }
    } catch (error: any) {
      if (showToast) {
        showToast({ message: error.message || '元素修改失败', type: 'error' });
      }
    } finally {
      setIsAiRefining(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`编辑${getElementTypeName(element.type)}`}
      size="xl"
    >
      {/* 标签页切换 */}
      <div className="flex gap-2 mb-4 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setActiveTab('manual')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'manual'
              ? 'text-banana-600 dark:text-banana-400 border-b-2 border-banana-500'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          手动编辑
        </button>
        <button
          onClick={() => setActiveTab('ai')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'ai'
              ? 'text-banana-600 dark:text-banana-400 border-b-2 border-banana-500'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          AI修改
        </button>
      </div>

      {/* 手动编辑标签页 */}
      {activeTab === 'manual' && (() => {
        switch (element.type) {
          case 'table':
            return <TableEditor element={element as any} onChange={handleSave} />;
          case 'chart':
            return <ChartEditor element={element as any} onChange={handleSave} />;
          case 'image':
            return <ImageEditor element={element as any} onChange={handleSave} />;
          case 'kpi':
            return <KPIEditor element={element as any} onChange={handleSave} />;
          default:
            return (
              <div className="text-center py-8 text-gray-500">
                暂不支持编辑此类型元素
              </div>
            );
        }
      })()}

      {/* AI修改标签页 */}
      {activeTab === 'ai' && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              修改要求
            </label>
            <textarea
              value={aiRefineInput}
              onChange={(e) => setAiRefineInput(e.target.value)}
              placeholder="请输入修改要求，例如：添加2024年数据、调整图表样式等"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500 resize-none"
              rows={4}
            />
          </div>
          
          <div>
            <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <input
                type="checkbox"
                checked={enableWebSearch}
                onChange={(e) => setEnableWebSearch(e.target.checked)}
                className="rounded border-gray-300 text-banana-500 focus:ring-banana-500"
              />
              启用联网搜索
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleAiRefine}
              disabled={isAiRefining || !aiRefineInput.trim()}
              className="px-4 py-2 text-sm bg-banana-500 text-white rounded-lg hover:bg-banana-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isAiRefining ? '正在修改...' : '修改'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
};

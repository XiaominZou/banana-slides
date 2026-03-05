import React, { useCallback } from 'react';
import { Textarea } from '../Textarea';
import { Button } from '../Button';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import type { SlideElement } from '@/types';

interface ImageEditorState {
  diagramType: string;
  content: string;
}

interface ImageEditorProps {
  element: SlideElement & { type: 'image' };
  onChange: (updatedElement: SlideElement) => void;
}

// 图片类型选项
const diagramTypeOptions = [
  { value: 'architecture', label: '架构图' },
  { value: 'flowchart', label: '流程图' },
  { value: 'mindmap', label: '思维导图' },
  { value: 'sequence', label: '时序图' },
  { value: 'timeline', label: '时间线' },
  { value: '', label: '图片' },
];

// 将 element 转换为编辑器状态
const convertImageElementToState = (element: any): ImageEditorState => {
  return {
    diagramType: element.diagram_type || '',
    content: element.content || '',
  };
};

// 将编辑器状态转换回 element
const convertStateToImageElement = (state: ImageEditorState) => {
  return {
    diagram_type: state.diagramType || undefined,
    content: state.content || '',
  };
};

export const ImageEditor: React.FC<ImageEditorProps> = ({ element, onChange }) => {
  const initialState = convertImageElementToState(element);
  
  // 使用撤销/重做 Hook（默认20步历史记录）
  const {
    state,
    setState,
    saveToHistory,
    undo,
    redo,
    canUndo,
    canRedo,
    historySize,
    redoSize,
  } = useUndoRedo(initialState, { maxSize: 20 });
  
  // 更新单个字段
  const handleChange = useCallback((key: keyof ImageEditorState, value: any) => {
    saveToHistory(state); // 保存到撤销栈
    setState(prev => ({ ...prev, [key]: value }));
    
    // 调用 onChange，传递更新后的元素对象
    const updatedState = { ...state, [key]: value };
    onChange({
      ...element,
      ...convertStateToImageElement(updatedState),
    });
  }, [state, saveToHistory, setState, element, onChange]);
  
  return (
    <div className="space-y-4">
      {/* 图片类型 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          图片类型
        </label>
        <select
          value={state.diagramType}
          onChange={(e) => handleChange('diagramType', e.target.value)}
          className="w-full px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-banana-500"
        >
          {diagramTypeOptions.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      
      {/* 图片说明 */}
      <Textarea
        label="图片说明"
        value={state.content}
        onChange={(e) => handleChange('content', e.target.value)}
        placeholder="例如：系统架构图，展示各个模块之间的关系"
        rows={4}
      />
      
      {/* 撤销/重做 */}
      <div className="flex gap-2 pt-4 border-t border-gray-200 dark:border-gray-600">
        <Button
          variant="ghost"
          size="sm"
          onClick={undo}
          disabled={!canUndo}
          title={`撤销 (${historySize} 步可用)`}
        >
          撤销
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={redo}
          disabled={!canRedo}
          title={`重做 (${redoSize} 步可用)`}
        >
          重做
        </Button>
      </div>
      
      {/* 提示信息 */}
      <div className="text-xs text-gray-500 dark:text-gray-400">
        <p>💡 提示：</p>
        <ul className="list-disc list-inside mt-1 space-y-1">
          <li>选择合适的图片类型</li>
          <li>添加详细的图片说明有助于生成更准确的图片</li>
          <li>支持撤销/重做操作（最多20步）</li>
        </ul>
      </div>
    </div>
  );
};

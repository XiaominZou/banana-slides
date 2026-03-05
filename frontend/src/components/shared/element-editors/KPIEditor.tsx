import React, { useCallback } from 'react';
import { Input } from '../Input';
import { Textarea } from '../Textarea';
import { Button } from '../Button';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import type { SlideElement } from '@/types';

interface KPIEditorState {
  kpiValue: string;
  kpiLabel: string;
  kpiTrend: string;
  kpiTrendColor?: 'green' | 'red' | undefined;
}

interface KPIEditorProps {
  element: SlideElement & { type: 'kpi' };
  onChange: (updatedElement: SlideElement) => void;
}

// 将 element 转换为编辑器状态
const convertKPIElementToState = (element: any): KPIEditorState => {
  return {
    kpiValue: element.kpi_value || '',
    kpiLabel: element.kpi_label || '',
    kpiTrend: element.kpi_trend || '',
    kpiTrendColor: element.kpi_trend_color,
  };
};

// 将编辑器状态转换回 element
const convertStateToKPIElement = (state: KPIEditorState) => {
  return {
    kpi_value: state.kpiValue,
    kpi_label: state.kpiLabel,
    kpi_trend: state.kpiTrend,
    kpi_trend_color: state.kpiTrendColor,
  };
};

export const KPIEditor: React.FC<KPIEditorProps> = ({ element, onChange }) => {
  const initialState = convertKPIElementToState(element);
  
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
  const handleChange = useCallback((key: keyof KPIEditorState, value: any) => {
    saveToHistory(state); // 保存到撤销栈
    setState(prev => ({ ...prev, [key]: value }));
    
    // 调用 onChange，传递更新后的元素对象
    const updatedState = { ...state, [key]: value };
    onChange({
      ...element,
      ...convertStateToKPIElement(updatedState),
    });
  }, [state, saveToHistory, setState, element, onChange]);
  
  return (
    <div className="space-y-4">
      {/* KPI数值 */}
      <Input
        label="KPI数值"
        value={state.kpiValue}
        onChange={(e) => handleChange('kpiValue', e.target.value)}
        placeholder="例如：1000"
      />
      
      {/* KPI标签 */}
      <Input
        label="KPI标签"
        value={state.kpiLabel}
        onChange={(e) => handleChange('kpiLabel', e.target.value)}
        placeholder="例如：销售额（万元）"
      />
      
      {/* KPI趋势 */}
      <Textarea
        label="KPI趋势"
        value={state.kpiTrend}
        onChange={(e) => handleChange('kpiTrend', e.target.value)}
        placeholder="例如：环比增长20%"
        rows={2}
      />
      
      {/* KPI趋势颜色 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          趋势颜色
        </label>
        <div className="space-y-2">
          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="radio"
              name="trendColor"
              value=""
              checked={state.kpiTrendColor === undefined}
              onChange={() => handleChange('kpiTrendColor', undefined)}
              className="w-4 h-4 text-banana-500 focus:ring-banana-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">无颜色</span>
          </label>
          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="radio"
              name="trendColor"
              value="green"
              checked={state.kpiTrendColor === 'green'}
              onChange={() => handleChange('kpiTrendColor', 'green')}
              className="w-4 h-4 text-green-600 focus:ring-green-500"
            />
            <span className="text-sm text-green-600 dark:text-green-400">绿色（增长）</span>
          </label>
          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="radio"
              name="trendColor"
              value="red"
              checked={state.kpiTrendColor === 'red'}
              onChange={() => handleChange('kpiTrendColor', 'red')}
              className="w-4 h-4 text-red-600 focus:ring-red-500"
            />
            <span className="text-sm text-red-600 dark:text-red-400">红色（下降）</span>
          </label>
        </div>
      </div>
      
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
          <li>填写KPI的数值、标签和趋势信息</li>
          <li>根据趋势方向选择合适的颜色（绿色表示增长，红色表示下降）</li>
          <li>支持撤销/重做操作（最多20步）</li>
        </ul>
      </div>
    </div>
  );
};

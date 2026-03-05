import React, { useCallback } from 'react';
import { Input } from '../Input';
import { Textarea } from '../Textarea';
import { Button } from '../Button';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import type { SlideElement } from '@/types';

interface ChartEditorState {
  chartType: 'bar' | 'line' | 'pie' | 'scatter' | 'area';
  content: string;
  labels: string;
  datasets: Dataset[];
}

interface Dataset {
  label: string;
  data: string; // 逗号分隔的数字字符串
}

interface ChartEditorProps {
  element: SlideElement & { type: 'chart'; chart_data: any };
  onChange: (updatedElement: SlideElement) => void;
}

// 将 chart_data 转换为编辑器状态
const convertChartDataToState = (element: any): ChartEditorState => {
  const chartType = element.chart_type || 'bar';
  const content = element.content || '';
  const labels = element.chart_data?.labels?.join(', ') || '';
  const datasets = (element.chart_data?.datasets || []).map((ds: any) => ({
    label: ds.label || '',
    data: ds.data?.join(', ') || '',
  }));
  
  return {
    chartType,
    content,
    labels,
    datasets: datasets.length > 0 ? datasets : [{ label: '数据集1', data: '' }],
  };
};

// 将编辑器状态转换回 chart_data
const convertStateToChartData = (state: ChartEditorState) => {
  const chartData: any = {
    labels: state.labels
      .split(',')
      .map(l => l.trim())
      .filter(l => l),
    datasets: state.datasets.map(ds => ({
      label: ds.label,
      data: ds.data
        .split(',')
        .map(d => parseFloat(d.trim()))
        .filter(d => !isNaN(d)),
    })),
  };
  
  return {
    chart_type: state.chartType,
    content: state.content,
    chart_data: chartData,
  };
};

export const ChartEditor: React.FC<ChartEditorProps> = ({ element, onChange }) => {
  const initialState = convertChartDataToState(element);
  
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
  const handleChange = useCallback((key: keyof ChartEditorState, value: any) => {
    saveToHistory(state); // 保存到撤销栈
    setState(prev => ({ ...prev, [key]: value }));
    
    // 调用 onChange，传递更新后的元素对象
    const updatedState = { ...state, [key]: value };
    onChange({
      ...element,
      ...convertStateToChartData(updatedState),
    });
  }, [state, saveToHistory, setState, element, onChange]);
  
  // 添加数据集
  const addDataset = useCallback(() => {
    saveToHistory(state); // 保存到撤销栈
    const updatedState = {
      ...state,
      datasets: [
        ...state.datasets,
        { label: `数据集${state.datasets.length + 1}`, data: '' },
      ],
    };
    setState(updatedState);
    onChange({
      ...element,
      ...convertStateToChartData(updatedState),
    });
  }, [state, saveToHistory, setState, element, onChange]);
  
  // 删除数据集
  const deleteDataset = useCallback((index: number) => {
    if (state.datasets.length <= 1) return; // 至少保留一个数据集
    
    saveToHistory(state); // 保存到撤销栈
    const updatedState = {
      ...state,
      datasets: state.datasets.filter((_, i) => i !== index),
    };
    setState(updatedState);
    onChange({
      ...element,
      ...convertStateToChartData(updatedState),
    });
  }, [state, saveToHistory, setState, element, onChange]);
  
  // 更新数据集
  const handleDatasetChange = useCallback(
    (index: number, key: keyof Dataset, value: string) => {
      saveToHistory(state); // 保存到撤销栈
      const updatedState = {
        ...state,
        datasets: state.datasets.map((ds, i) =>
          i === index ? { ...ds, [key]: value } : ds
        ),
      };
      setState(updatedState);
      onChange({
        ...element,
        ...convertStateToChartData(updatedState),
      });
    },
    [state, saveToHistory, setState, element, onChange]
  );
  
  const chartTypeOptions = [
    { value: 'bar', label: '柱状图' },
    { value: 'line', label: '折线图' },
    { value: 'pie', label: '饼图' },
    { value: 'scatter', label: '散点图' },
    { value: 'area', label: '面积图' },
  ];
  
  return (
    <div className="space-y-4">
      {/* 图表类型 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          图表类型
        </label>
        <select
          value={state.chartType}
          onChange={(e) => handleChange('chartType', e.target.value)}
          className="w-full px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-banana-500"
        >
          {chartTypeOptions.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      
      {/* 图表标题 */}
      <Input
        label="图表标题"
        value={state.content}
        onChange={(e) => handleChange('content', e.target.value)}
        placeholder="例如：2024年销售数据"
      />
      
      {/* X轴标签 */}
      <Textarea
        label="X轴标签（逗号分隔）"
        value={state.labels}
        onChange={(e) => handleChange('labels', e.target.value)}
        placeholder="例如：一月, 二月, 三月, 四月"
        rows={2}
      />
      
      {/* 数据集 */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          数据集
        </label>
        {state.datasets.map((dataset, index) => (
          <div key={index} className="border border-gray-200 dark:border-gray-600 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <Input
                label={`数据集 ${index + 1} 名称`}
                value={dataset.label}
                onChange={(e) => handleDatasetChange(index, 'label', e.target.value)}
                placeholder="例如：销售额"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => deleteDataset(index)}
                disabled={state.datasets.length <= 1}
              >
                删除
              </Button>
            </div>
            <Input
              label="数据值（逗号分隔的数字）"
              value={dataset.data}
              onChange={(e) => handleDatasetChange(index, 'data', e.target.value)}
              placeholder="例如：100, 200, 300, 400"
            />
          </div>
        ))}
        <Button
          variant="secondary"
          size="sm"
          onClick={addDataset}
          className="w-full"
        >
          + 添加数据集
        </Button>
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
          <li>选择合适的图表类型</li>
          <li>X轴标签和数据值用逗号分隔</li>
          <li>数据值必须是数字</li>
          <li>支持撤销/重做操作（最多20步）</li>
        </ul>
      </div>
    </div>
  );
};

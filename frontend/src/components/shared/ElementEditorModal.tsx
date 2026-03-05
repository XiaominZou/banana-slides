import React from 'react';
import { Modal } from './Modal';
import { TableEditor } from './element-editors/TableEditor';
import { ChartEditor } from './element-editors/ChartEditor';
import { ImageEditor } from './element-editors/ImageEditor';
import { KPIEditor } from './element-editors/KPIEditor';
import type { SlideElement } from '@/types';

interface ElementEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  element: SlideElement;
  onSave: (updatedElement: SlideElement) => void;
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
  onSave,
}) => {
  const handleSave = (updatedElement: SlideElement) => {
    onSave(updatedElement);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`编辑${getElementTypeName(element.type)}`}
      size="xl"
    >
      {(() => {
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
    </Modal>
  );
};

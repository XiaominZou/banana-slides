import React, { useState, useCallback } from 'react';
import { Button } from '../Button';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import type { SlideElement } from '@/types';

// 单元格数据结构
interface TableCell {
  rowSpan: number;        // 行跨度（默认1）
  colSpan: number;        // 列跨度（默认1）
  value: string;          // 单元格内容
  isMerged: boolean;      // 是否是被合并的单元格（隐藏）
  isMergeOrigin: boolean; // 是否是合并的起始单元格
}

// 选中状态
interface Selection {
  startRow: number;
  startCol: number;
  endRow: number;
  endCol: number;
  isSelecting: boolean;
}

interface TableEditorProps {
  element: SlideElement & { type: 'table'; table_data: string[][] };
  onChange: (updatedElement: SlideElement) => void;
}

// 将 table_data 转换为 cells 格式
const convertTableDataToCells = (tableData: string[][]): TableCell[][] => {
  if (!tableData || tableData.length === 0) {
    // 默认3行3列
    return Array.from({ length: 3 }, () =>
      Array.from({ length: 3 }, () => ({
        rowSpan: 1,
        colSpan: 1,
        value: '',
        isMerged: false,
        isMergeOrigin: false,
      }))
    );
  }

  return tableData.map(row =>
    row.map(cell => ({
      rowSpan: 1,
      colSpan: 1,
      value: cell || '',
      isMerged: false,
      isMergeOrigin: false,
    }))
  );
};

// 将 cells 转换回 table_data
const convertCellsToTableData = (cells: TableCell[][]): string[][] => {
  const tableData: string[][] = [];
  
  cells.forEach(row => {
    const rowData: string[] = [];
    row.forEach(cell => {
      rowData.push(cell.value);
    });
    tableData.push(rowData);
  });
  
  return tableData;
};

export const TableEditor: React.FC<TableEditorProps> = ({ element, onChange }) => {
  // 初始化表格数据
  const initialCells = convertTableDataToCells(element.table_data || []);
  
  // 使用撤销/重做 Hook（默认20步历史记录）
  const {
    state: cells,
    setState: setCells,
    saveToHistory,
    undo,
    redo,
    canUndo,
    canRedo,
    historySize,
    redoSize,
  } = useUndoRedo(initialCells, { maxSize: 20 });
  
  const [selection, setSelection] = useState<Selection>({
    startRow: 0,
    startCol: 0,
    endRow: 0,
    endCol: 0,
    isSelecting: false,
  });
  
  const rows = cells.length;
  const cols = cells[0]?.length || 3;
  
  // 判断单元格是否被选中
  const isCellSelected = useCallback((row: number, col: number): boolean => {
    const { startRow, startCol, endRow, endCol } = selection;
    const minRow = Math.min(startRow, endRow);
    const maxRow = Math.max(startRow, endRow);
    const minCol = Math.min(startCol, endCol);
    const maxCol = Math.max(startCol, endCol);
    
    return row >= minRow && row <= maxRow && col >= minCol && col <= maxCol;
  }, [selection]);
  
  // 检查是否可以合并
  const canMerge = selection.startRow !== selection.endRow || 
                  selection.startCol !== selection.endCol;
  
  // 检查是否可以取消合并
  const canUnmerge = selection.startRow === selection.endRow && 
                     selection.startCol === selection.endCol &&
                     cells[selection.startRow]?.[selection.startCol]?.isMergeOrigin;
  
  // 单元格鼠标按下
  const handleCellMouseDown = useCallback((row: number, col: number) => {
    const cell = cells[row]?.[col];
    // 只能选择未被合并的单元格
    if (!cell || cell.isMerged) return;
    
    setSelection({
      startRow: row,
      startCol: col,
      endRow: row,
      endCol: col,
      isSelecting: true,
    });
  }, [cells]);
  
  // 单元格鼠标移动
  const handleCellMouseOver = useCallback((row: number, col: number) => {
    if (selection.isSelecting) {
      const cell = cells[row]?.[col];
      // 只能选择未被合并的单元格
      if (!cell || cell.isMerged) return;
      
      setSelection(prev => ({
        ...prev,
        endRow: row,
        endCol: col,
      }));
    }
  }, [selection.isSelecting, cells]);
  
  // 单元格鼠标抬起
  const handleCellMouseUp = useCallback(() => {
    setSelection(prev => ({ ...prev, isSelecting: false }));
  }, []);
  
  // 单元格内容变化
  const handleCellChange = useCallback((row: number, col: number, value: string) => {
    saveToHistory(cells); // 保存到撤销栈
    
    setCells(prevCells => {
      const newCells = prevCells.map(row => row.map(cell => ({ ...cell })));
      newCells[row][col].value = value;
      return newCells;
    });
    
    // 调用 onChange，传递更新后的元素对象
    const updatedCells = cells.map(row => row.map(cell => ({ ...cell })));
    updatedCells[row][col].value = value;
    onChange({
      ...element,
      table_data: convertCellsToTableData(updatedCells),
    });
  }, [cells, saveToHistory, element, onChange]);
  
  // 合并单元格
  const mergeCells = useCallback(() => {
    const { startRow, startCol, endRow, endCol } = selection;
    const minRow = Math.min(startRow, endRow);
    const maxRow = Math.max(startRow, endRow);
    const minCol = Math.min(startCol, endCol);
    const maxCol = Math.max(startCol, endCol);
    
    const rowSpan = maxRow - minRow + 1;
    const colSpan = maxCol - minCol + 1;
    
    saveToHistory(cells); // 保存到撤销栈
    
    setCells(prevCells => {
      const newCells = prevCells.map(row => row.map(cell => ({ ...cell })));
      const startCell = newCells[minRow][minCol];
      
      // 执行合并
      startCell.rowSpan = rowSpan;
      startCell.colSpan = colSpan;
      startCell.isMergeOrigin = true;
      
      // 标记其他单元格为已合并
      for (let r = minRow; r <= maxRow; r++) {
        for (let c = minCol; c <= maxCol; c++) {
          if (r !== minRow || c !== minCol) {
            newCells[r][c].isMerged = true;
          }
        }
      }
      
      return newCells;
    });
  }, [selection, cells, saveToHistory]);
  
  // 取消合并
  const unmergeCells = useCallback(() => {
    const { startRow, startCol } = selection;
    const startCell = cells[startRow]?.[startCol];
    
    if (!startCell || !startCell.isMergeOrigin) return;
    
    saveToHistory(cells); // 保存到撤销栈
    
    setCells(prevCells => {
      const newCells = prevCells.map(row => row.map(cell => ({ ...cell })));
      
      const rowSpan = startCell.rowSpan;
      const colSpan = startCell.colSpan;
      const value = startCell.value;
      
      // 恢复起始单元格
      startCell.rowSpan = 1;
      startCell.colSpan = 1;
      startCell.isMergeOrigin = false;
      
      // 恢复被合并的单元格（方案A：相同内容）
      for (let r = startRow; r < startRow + rowSpan; r++) {
        for (let c = startCol; c < startCol + colSpan; c++) {
          if (r !== startRow || c !== startCol) {
            newCells[r][c].isMerged = false;
            newCells[r][c].value = value;
          }
        }
      }
      
      return newCells;
    });
  }, [selection, cells, saveToHistory]);
  
  // 添加行
  const addRow = useCallback(() => {
    saveToHistory(cells); // 保存到撤销栈
    
    setCells(prevCells => {
      const newCells = prevCells.map(row => row.map(cell => ({ ...cell })));
      const newRow: TableCell[] = Array.from({ length: cols }, () => ({
        rowSpan: 1,
        colSpan: 1,
        value: '',
        isMerged: false,
        isMergeOrigin: false,
      }));
      
      newCells.push(newRow);
      return newCells;
    });
  }, [cells, cols, saveToHistory]);
  
  // 删除行（方案B：自动调整合并单元格）
  const deleteRow = useCallback((rowIndex: number) => {
    if (rows <= 1) return; // 至少保留一行
    
    saveToHistory(cells); // 保存到撤销栈
    
    setCells(prevCells => {
      const newCells = prevCells.map(row => row.map(cell => ({ ...cell })));
      
      // 检查并调整跨行的合并单元格
      for (let c = 0; c < cols; c++) {
        const cell = newCells[rowIndex][c];
        
        // 如果删除的行是合并的起始行，将起始行上移
        if (cell.isMergeOrigin && cell.rowSpan > 1 && rowIndex > 0) {
          const prevRowCell = newCells[rowIndex - 1][c];
          if (!prevRowCell.isMergeOrigin && !prevRowCell.isMerged) {
            prevRowCell.rowSpan = cell.rowSpan;
            prevRowCell.colSpan = cell.colSpan;
            prevRowCell.value = cell.value;
            prevRowCell.isMergeOrigin = true;
          }
        }
      }
      
      // 如果删除的行在合并范围内，减少 rowSpan
      for (let r = 0; r < rowIndex; r++) {
        for (let c = 0; c < cols; c++) {
          const cell = newCells[r][c];
          if (cell.isMergeOrigin && r + cell.rowSpan > rowIndex) {
            cell.rowSpan -= 1;
          }
        }
      }
      
      // 删除行
      newCells.splice(rowIndex, 1);
      return newCells;
    });
  }, [cells, rows, cols, saveToHistory]);
  
  // 添加列
  const addCol = useCallback(() => {
    saveToHistory(cells); // 保存到撤销栈
    
    setCells(prevCells => {
      const newCells = prevCells.map(row => row.map(cell => ({ ...cell })));
      
      newCells.forEach(row => {
        row.push({
          rowSpan: 1,
          colSpan: 1,
          value: '',
          isMerged: false,
          isMergeOrigin: false,
        });
      });
      
      return newCells;
    });
  }, [cells, saveToHistory]);
  
  // 删除列（方案B：自动调整合并单元格）
  const deleteCol = useCallback((colIndex: number) => {
    if (cols <= 1) return; // 至少保留一列
    
    saveToHistory(cells); // 保存到撤销栈
    
    setCells(prevCells => {
      const newCells = prevCells.map(row => row.map(cell => ({ ...cell })));
      
      // 检查并调整跨列的合并单元格
      newCells.forEach((row, rowIndex) => {
        // 如果删除的列在合并范围内，减少 colSpan
        for (let c = 0; c < colIndex; c++) {
          const cell = newCells[rowIndex][c];
          if (cell.isMergeOrigin && c + cell.colSpan > colIndex) {
            cell.colSpan -= 1;
          }
        }
      });
      
      // 删除列
      newCells.forEach(row => {
        row.splice(colIndex, 1);
      });
      
      return newCells;
    });
  }, [cells, cols, saveToHistory]);
  
  return (
    <div className="space-y-4" onMouseUp={handleCellMouseUp}>
      {/* 表格 */}
      <div className="overflow-x-auto border border-gray-300 dark:border-gray-600">
        <table className="min-w-full">
          <tbody>
            {cells.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, colIndex) => {
                  // 如果单元格是被合并的（隐藏的），不渲染
                  if (cell.isMerged) return null;
                  
                  const isSelected = isCellSelected(rowIndex, colIndex);
                  
                  return (
                    <td
                      key={`${rowIndex}-${colIndex}`}
                      rowSpan={cell.rowSpan}
                      colSpan={cell.colSpan}
                      contentEditable={true}
                      className={`
                        border border-gray-300 dark:border-gray-600 px-2 py-1 min-w-[80px]
                        text-sm text-gray-900 dark:text-gray-100
                        focus:outline-none focus:ring-2 focus:ring-blue-500
                        ${isSelected ? 'bg-blue-100 dark:bg-blue-900/30' : 'bg-white dark:bg-gray-800'}
                        ${cell.isMergeOrigin ? 'border-blue-500 border-2' : ''}
                      `}
                      onMouseDown={() => handleCellMouseDown(rowIndex, colIndex)}
                      onMouseOver={() => handleCellMouseOver(rowIndex, colIndex)}
                      onBlur={(e) => handleCellChange(rowIndex, colIndex, e.currentTarget.textContent || '')}
                    >
                      {cell.value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* 操作按钮 */}
      <div className="space-y-3">
        {/* 撤销/重做 */}
        <div className="flex gap-2">
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
        
        {/* 行操作 */}
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={addRow}>
            添加行
          </Button>
          {Array.from({ length: rows }, (_, rowIndex) => (
            <Button
              key={rowIndex}
              variant="ghost"
              size="sm"
              onClick={() => deleteRow(rowIndex)}
              disabled={rows <= 1}
              title={`删除第 ${rowIndex + 1} 行`}
            >
              删除行 {rowIndex + 1}
            </Button>
          ))}
        </div>
        
        {/* 列操作 */}
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={addCol}>
            添加列
          </Button>
          {Array.from({ length: cols }, (_, colIndex) => (
            <Button
              key={colIndex}
              variant="ghost"
              size="sm"
              onClick={() => deleteCol(colIndex)}
              disabled={cols <= 1}
              title={`删除第 ${colIndex + 1} 列`}
            >
              删除列 {colIndex + 1}
            </Button>
          ))}
        </div>
        
        {/* 合并/取消合并 */}
        <div className="flex gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={mergeCells}
            disabled={!canMerge}
            title="选中多个单元格后合并"
          >
            合并单元格
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={unmergeCells}
            disabled={!canUnmerge}
            title="取消选中的合并单元格"
          >
            取消合并
          </Button>
        </div>
      </div>
      
      {/* 提示信息 */}
      <div className="text-xs text-gray-500 dark:text-gray-400">
        <p>💡 提示：</p>
        <ul className="list-disc list-inside mt-1 space-y-1">
          <li>点击单元格可直接编辑内容</li>
          <li>拖动鼠标可选中多个单元格</li>
          <li>选中多个单元格后可合并</li>
          <li>点击合并的单元格可取消合并</li>
          <li>支持撤销/重做操作（最多20步）</li>
        </ul>
      </div>
    </div>
  );
};

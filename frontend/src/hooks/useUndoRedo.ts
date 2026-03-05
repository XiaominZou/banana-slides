import { useState, useCallback } from 'react';

interface UseUndoRedoOptions<T> {
  maxSize?: number;  // 最大历史记录数，默认20
}

export interface UseUndoRedoReturn<T> {
  state: T;
  setState: React.Dispatch<React.SetStateAction<T>>;
  saveToHistory: (currentState: T) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  historySize: number;
  redoSize: number;
}

export const useUndoRedo = <T extends any>(
  initialState: T,
  options: UseUndoRedoOptions<T> = {}
): UseUndoRedoReturn<T> => {
  const { maxSize = 20 } = options;
  
  const [state, setState] = useState<T>(initialState);
  const [history, setHistory] = useState<T[]>([]);
  const [redoStack, setRedoStack] = useState<T[]>([]);
  
  // 保存状态到历史记录
  const saveToHistory = useCallback((currentState: T) => {
    setHistory(prev => {
      const newHistory = [...prev, currentState];
      // 限制历史记录大小
      if (newHistory.length > maxSize) {
        newHistory.shift();
      }
      return newHistory;
    });
    // 清空重做栈（有新操作时，重做栈失效）
    setRedoStack([]);
  }, [maxSize]);
  
  // 撤销
  const undo = useCallback(() => {
    setHistory(prevHistory => {
      if (prevHistory.length === 0) return prevHistory;
      
      const currentState = state;
      const previousState = prevHistory[prevHistory.length - 1];
      
      // 将当前状态移到重做栈
      setRedoStack(prev => [...prev, currentState]);
      
      // 恢复上一个状态
      setState(previousState);
      
      return prevHistory.slice(0, -1);
    });
  }, [state]);
  
  // 重做
  const redo = useCallback(() => {
    setRedoStack(prevRedoStack => {
      if (prevRedoStack.length === 0) return prevRedoStack;
      
      const nextState = prevRedoStack[prevRedoStack.length - 1];
      
      // 将下一个状态移到历史记录
      setHistory(prev => [...prev, nextState]);
      
      // 恢复下一个状态
      setState(nextState);
      
      return prevRedoStack.slice(0, -1);
    });
  }, []);
  
  // 检查是否可以撤销
  const canUndo = history.length > 0;
  
  // 检查是否可以重做
  const canRedo = redoStack.length > 0;
  
  const historySize = history.length;
  const redoSize = redoStack.length;
  
  return {
    state,
    setState,
    saveToHistory,
    undo,
    redo,
    canUndo,
    canRedo,
    historySize,
    redoSize,
  };
};

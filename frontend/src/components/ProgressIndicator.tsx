import React from 'react';
import { Loader2, Search, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProgressIndicatorProps {
  stage: string;
  message: string;
  className?: string;
}

const stageIcons: Record<string, React.ReactNode> = {
  'init': <Loader2 className="w-5 h-5 animate-spin text-blue-500" />,
  'preparing': <Search className="w-5 h-5 text-blue-500" />,
  'generating': <Sparkles className="w-5 h-5 text-purple-500 animate-pulse" />,
  'optimizing': <Sparkles className="w-5 h-5 text-purple-500 animate-pulse" />,
  'complete': <CheckCircle2 className="w-5 h-5 text-green-500" />,
  'error': <AlertCircle className="w-5 h-5 text-red-500" />,
  'timeout': <AlertCircle className="w-5 h-5 text-yellow-500" />,
};

const stageLabels: Record<string, string> = {
  'init': '初始化',
  'preparing': '准备中',
  'generating': '生成中',
  'optimizing': '优化中',
  'complete': '完成',
  'error': '错误',
  'timeout': '超时',
};

export function ProgressIndicator({ stage, message, className }: ProgressIndicatorProps) {
  const icon = stageIcons[stage] || <Loader2 className="w-5 h-5 animate-spin text-blue-500" />;
  const label = stageLabels[stage] || stage;

  return (
    <div className={cn(
      'flex items-center gap-3 px-4 py-3 rounded-lg',
      'bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-100',
      'animate-in fade-in slide-in-from-top-2 duration-300',
      className
    )}>
      <div className="flex-shrink-0">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900">{label}</span>
          <span className="text-xs text-gray-500">•</span>
          <span className="text-sm text-gray-600 truncate">{message}</span>
        </div>
        {stage !== 'complete' && stage !== 'error' && (
          <div className="mt-1.5 h-1 w-full bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full animate-pulse" 
                 style={{ width: '60%' }} />
          </div>
        )}
      </div>
    </div>
  );
}

interface OutlineGenerationProgressProps {
  progress: { stage: string; message: string } | null;
  isStreaming: boolean;
}

export function OutlineGenerationProgress({ progress, isStreaming }: OutlineGenerationProgressProps) {
  if (!isStreaming || !progress) return null;

  return (
    <div className="mb-4">
      <ProgressIndicator stage={progress.stage} message={progress.message} />
    </div>
  );
}

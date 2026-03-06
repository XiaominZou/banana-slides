import React, { Component } from 'react';
import { Button } from '@/components/shared';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] 捕获到错误:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  handleGoBack = () => {
    window.history.back();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-gray-50 dark:bg-background-primary">
          <div className="max-w-md w-full bg-white dark:bg-background-secondary rounded-lg shadow-md p-6 text-center">
            <div className="text-red-500 text-4xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-foreground-primary mb-2">
              页面出现错误
            </h2>
            <p className="text-gray-600 dark:text-foreground-secondary mb-4">
              页面遇到了一些问题，请尝试刷新页面或返回上一页。
            </p>
            {this.state.error && (
              <details className="text-left text-sm text-gray-500 dark:text-foreground-tertiary mb-4">
                <summary>错误详情（开发者）</summary>
                <pre className="mt-2 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs overflow-auto">
                  {this.state.error.message}
                </pre>
              </details>
            )}
            <div className="flex gap-3 justify-center">
              <Button
                onClick={() => window.location.reload()}
                variant="primary"
              >
                刷新页面
              </Button>
              <Button
                onClick={this.handleGoBack}
                variant="secondary"
              >
                返回上一页
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
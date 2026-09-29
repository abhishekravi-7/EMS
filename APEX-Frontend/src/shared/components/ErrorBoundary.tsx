import React, { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught Error caught by ErrorBoundary:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "40px",
            margin: "40px auto",
            maxWidth: "800px",
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "12px",
            color: "#991b1b",
            fontFamily: "sans-serif",
          }}
        >
          <h2 style={{ marginTop: 0, color: "#991b1b" }}>⚠️ Application Settings Exception</h2>
          <p style={{ fontSize: "15px", color: "#7f1d1d" }}>
            An unexpected error occurred while rendering the page:
          </p>
          <pre
            style={{
              padding: "16px",
              backgroundColor: "#ffffff",
              borderRadius: "8px",
              border: "1px solid #fca5a5",
              overflowX: "auto",
              fontSize: "13px",
              color: "#dc2626",
            }}
          >
            {this.state.error?.toString()}
            {"\n\n"}
            {this.state.errorInfo?.componentStack}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: "16px",
              padding: "10px 20px",
              backgroundColor: "#dc2626",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

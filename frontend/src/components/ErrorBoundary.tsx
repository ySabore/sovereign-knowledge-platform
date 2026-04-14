import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; fallback?: ReactNode };

type State = { hasError: boolean; message: string | null };

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: null };
  }

  static getDerivedStateFromError(err: Error): State {
    return { hasError: true, message: err.message };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error boundary:", error, info.componentStack);
  }

  override render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="sk-panel" style={{ margin: "2rem", maxWidth: 560 }}>
            <h2 style={{ marginTop: 0 }}>Something went wrong</h2>
            <p className="sk-muted">{this.state.message ?? "Unexpected error"}</p>
            <button type="button" className="sk-btn secondary" onClick={() => this.setState({ hasError: false, message: null })}>
              Try again
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}

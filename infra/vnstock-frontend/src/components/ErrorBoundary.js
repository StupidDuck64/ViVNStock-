import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full bg-bg-primary text-text-secondary">
          <p className="text-lg mb-2">Chart encountered an error</p>
          <p className="text-xs text-red-400 mb-4 max-w-md text-center">
            {this.state.error?.message || "Unknown error"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-500"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

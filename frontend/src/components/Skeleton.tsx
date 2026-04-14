import type { CSSProperties } from "react";

export function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return <div className={`sk-skeleton ${className}`.trim()} style={style} aria-hidden />;
}

export function SkeletonBlock({ lines = 3 }: { lines?: number }) {
  return (
    <div className="sk-stack" style={{ width: "100%", maxWidth: 420 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} style={{ width: i === lines - 1 ? "60%" : "100%" }} />
      ))}
    </div>
  );
}

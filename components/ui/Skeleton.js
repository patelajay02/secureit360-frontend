// components/ui/Skeleton.js
// SecureIT360 — Loading skeleton component
// Shows grey placeholder shapes while pages load

export function Skeleton({ className = "" }) {
  return (
    <div
      className={`bg-gray-800 animate-pulse rounded ${className}`}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
      <Skeleton className="h-4 w-24 mb-4" />
      <Skeleton className="h-8 w-16 mb-2" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

export function SkeletonTable({ rows = 3 }) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-6 py-4">
          <Skeleton className="h-8 w-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-48" />
            <Skeleton className="h-3 w-32" />
          </div>
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonDashboard() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SkeletonCard />
        <SkeletonCard />
      </div>
      <SkeletonTable rows={4} />
    </div>
  );
}
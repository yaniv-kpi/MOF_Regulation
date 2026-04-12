export default function LoadingState() {
  return (
    <div className="flex flex-col gap-4 w-full" dir="rtl">
      {[...Array(5)].map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-5 sm:p-6 overflow-hidden"
        >
          {/* Badges row */}
          <div className="flex gap-2 mb-3">
            <div className="h-5 w-20 rounded-full bg-slate-200 dark:bg-slate-700 animate-pulse" />
            <div className="h-5 w-16 rounded-full bg-slate-200 dark:bg-slate-700 animate-pulse" />
          </div>
          {/* Title */}
          <div className="h-5 w-3/4 rounded-lg bg-slate-200 dark:bg-slate-700 animate-pulse mb-3" />
          {/* Snippet lines */}
          <div className="space-y-2 mb-4">
            <div className="h-3.5 w-full rounded bg-slate-100 dark:bg-slate-700/50 animate-pulse" />
            <div className="h-3.5 w-5/6 rounded bg-slate-100 dark:bg-slate-700/50 animate-pulse" />
            <div className="h-3.5 w-4/5 rounded bg-slate-100 dark:bg-slate-700/50 animate-pulse" />
          </div>
          {/* Footer */}
          <div className="flex justify-between items-center pt-3 border-t border-slate-100 dark:border-slate-700">
            <div className="h-3 w-32 rounded bg-slate-100 dark:bg-slate-700/50 animate-pulse" />
            <div className="h-8 w-24 rounded-lg bg-slate-200 dark:bg-slate-700 animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}

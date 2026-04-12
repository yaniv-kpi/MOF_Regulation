import { SearchX } from "lucide-react";

interface EmptyStateProps {
  query: string;
}

export default function EmptyState({ query }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center py-20 text-center gap-4 animate-fade-in"
      dir="rtl"
    >
      <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
        <SearchX className="w-8 h-8 text-slate-400" />
      </div>
      <div>
        <h3 className="text-lg font-semibold text-slate-800 dark:text-white mb-1">
          לא נמצאו תוצאות
        </h3>
        <p className="text-slate-500 dark:text-slate-400 text-sm max-w-sm">
          לא מצאנו מסמכים עבור &ldquo;
          <span className="font-medium text-slate-700 dark:text-slate-300">{query}</span>
          &rdquo;. נסה מילות חיפוש אחרות.
        </p>
      </div>
      <div className="mt-2 flex flex-col gap-1.5 text-sm text-slate-400 dark:text-slate-500">
        <p>✦ בדוק שאין שגיאות כתיב</p>
        <p>✦ נסה מילה אחת או שתי מילים</p>
        <p>✦ נסה מונחים כלליים יותר</p>
      </div>
    </div>
  );
}

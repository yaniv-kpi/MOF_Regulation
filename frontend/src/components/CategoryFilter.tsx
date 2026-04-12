"use client";

import { useEffect, useState } from "react";
import { getCategories } from "@/lib/api";
import clsx from "clsx";

interface CategoryFilterProps {
  selected: string;
  onChange: (cat: string) => void;
}

export default function CategoryFilter({ selected, onChange }: CategoryFilterProps) {
  const [categories, setCategories] = useState<string[]>([]);

  useEffect(() => {
    getCategories()
      .then(setCategories)
      .catch(() => {});
  }, []);

  if (!categories.length) return null;

  return (
    <div className="flex flex-wrap gap-2" dir="rtl">
      <button
        onClick={() => onChange("")}
        className={clsx(
          "px-3 py-1.5 rounded-full text-sm font-medium transition-all",
          !selected
            ? "bg-brand-600 text-white shadow-sm"
            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
        )}
      >
        הכל
      </button>
      {categories.map((cat) => (
        <button
          key={cat}
          onClick={() => onChange(cat === selected ? "" : cat)}
          className={clsx(
            "px-3 py-1.5 rounded-full text-sm font-medium transition-all",
            cat === selected
              ? "bg-brand-600 text-white shadow-sm"
              : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
          )}
        >
          {cat}
        </button>
      ))}
    </div>
  );
}

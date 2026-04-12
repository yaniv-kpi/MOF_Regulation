"use client";

import { useRef, useState, useEffect } from "react";
import { Search, X, Loader2 } from "lucide-react";
import { useAutocomplete } from "@/hooks/useSearch";
import clsx from "clsx";

interface SearchBarProps {
  value: string;
  onChange: (v: string) => void;
  onSearch: (q: string) => void;
  loading?: boolean;
  size?: "hero" | "compact";
}

export default function SearchBar({
  value,
  onChange,
  onSearch,
  loading = false,
  size = "hero",
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { suggestions, fetchSuggestions, clearSuggestions } = useAutocomplete();
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    onChange(v);
    fetchSuggestions(v);
    setShowSuggestions(true);
    setActiveSuggestion(-1);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    clearSuggestions();
    setShowSuggestions(false);
    if (value.trim()) onSearch(value.trim());
  };

  const handleSuggestionClick = (s: string) => {
    onChange(s);
    clearSuggestions();
    setShowSuggestions(false);
    onSearch(s);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!suggestions.length || !showSuggestions) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSuggestion((p) => Math.min(p + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSuggestion((p) => Math.max(p - 1, -1));
    } else if (e.key === "Enter" && activeSuggestion >= 0) {
      e.preventDefault();
      handleSuggestionClick(suggestions[activeSuggestion]);
    } else if (e.key === "Escape") {
      clearSuggestions();
      setShowSuggestions(false);
    }
  };

  // Close suggestions on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (inputRef.current && !inputRef.current.closest("form")?.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const isHero = size === "hero";

  return (
    <form onSubmit={handleSubmit} className="relative w-full" dir="rtl">
      <div
        className={clsx(
          "relative flex items-center rounded-2xl border bg-white dark:bg-slate-800 shadow-lg transition-all duration-200",
          "border-slate-200 dark:border-slate-700",
          "focus-within:border-brand-400 dark:focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-100 dark:focus-within:ring-brand-900/30",
          isHero ? "text-lg" : "text-sm"
        )}
      >
        {/* Search icon */}
        <div className={clsx("flex-shrink-0 flex items-center", isHero ? "pr-5 pl-2" : "pr-4 pl-2")}>
          {loading ? (
            <Loader2 className={clsx("animate-spin text-brand-500", isHero ? "w-6 h-6" : "w-4 h-4")} />
          ) : (
            <Search className={clsx("text-slate-400", isHero ? "w-6 h-6" : "w-4 h-4")} />
          )}
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          placeholder="חפש תקנות, חוקים, נהלים... (עברית / English)"
          className={clsx(
            "flex-1 bg-transparent outline-none text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 text-right",
            isHero ? "py-4" : "py-2.5"
          )}
          dir="rtl"
          lang="he"
          autoComplete="off"
          spellCheck={false}
        />

        {/* Clear button */}
        {value && (
          <button
            type="button"
            onClick={() => { onChange(""); clearSuggestions(); inputRef.current?.focus(); }}
            className="flex-shrink-0 p-1.5 ml-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-full hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={!value.trim() || loading}
          className={clsx(
            "flex-shrink-0 flex items-center gap-2 font-medium rounded-xl transition-all",
            "bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed",
            "text-white shadow-sm",
            isHero ? "px-6 py-3 mr-2 text-base" : "px-4 py-2 mr-1.5 text-sm"
          )}
        >
          <span>חפש</span>
        </button>
      </div>

      {/* Autocomplete dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <ul className="absolute z-50 w-full mt-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-xl overflow-hidden">
          {suggestions.map((s, i) => (
            <li key={s}>
              <button
                type="button"
                onMouseDown={(e) => { e.preventDefault(); handleSuggestionClick(s); }}
                className={clsx(
                  "w-full text-right px-4 py-2.5 text-sm flex items-center gap-3 transition-colors",
                  i === activeSuggestion
                    ? "bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300"
                    : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/50"
                )}
              >
                <Search className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                <span>{s}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

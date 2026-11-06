import React, { useState } from 'react';
import { Sparkles, Send, Plus, ArrowRight, Loader2 } from 'lucide-react';

export interface Suggestion {
  label: string;
  prompt: string;
}

interface AIStageCreatorBarProps {
  category: 'cleaning' | 'analysis' | 'visualization';
  title?: string;
  subtitle?: string;
  placeholder?: string;
  suggestions: Suggestion[];
  onSubmit: (prompt: string) => void;
  onAddManual?: () => void;
  disabled?: boolean;
  busy?: boolean;
}

export const AIStageCreatorBar: React.FC<AIStageCreatorBarProps> = ({
  category,
  title,
  subtitle,
  placeholder,
  suggestions,
  onSubmit,
  onAddManual,
  disabled = false,
  busy = false,
}) => {
  const [prompt, setPrompt] = useState('');

  const defaultTitle =
    category === 'cleaning'
      ? 'Create or refine cleaning stages with AI'
      : category === 'analysis'
      ? 'Create or refine analysis stages with AI'
      : 'Create or refine visualizations with AI';

  const defaultSubtitle =
    category === 'cleaning'
      ? 'Describe what data cleaning is required. AI will analyze columns and propose Python transformations.'
      : category === 'analysis'
      ? 'Describe metrics, aggregations, or trends to compute. AI will generate Python code and output tables.'
      : 'Describe the charts, metric cards, or tables to add to the dashboard.';

  const defaultPlaceholder =
    category === 'cleaning'
      ? 'e.g. Drop rows with null values, convert timestamps to UTC, filter out invalid readings...'
      : category === 'analysis'
      ? 'e.g. Calculate monthly consumption by category, compute 7-day moving averages, top 5 items...'
      : 'e.g. Bar chart comparing totals by category, KPI cards for key metrics...';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = prompt.trim();
    if (!text || disabled || busy) return;
    onSubmit(text);
    setPrompt('');
  };

  const handleSuggestionClick = (suggestionPrompt: string) => {
    if (disabled || busy) return;
    onSubmit(suggestionPrompt);
  };

  return (
    <section className="ai-creator-bar" aria-label={title || defaultTitle}>
      <div className="ai-creator-header">
        <div className="ai-creator-title-group">
          <span className="ai-sparkle-mark" aria-hidden="true">
            <Sparkles size={18} />
          </span>
          <div>
            <h3>{title || defaultTitle}</h3>
            <p className="muted">{subtitle || defaultSubtitle}</p>
          </div>
        </div>
        {onAddManual && (
          <button
            type="button"
            className="manual-add-button"
            disabled={disabled || busy}
            onClick={onAddManual}
            title={`Add custom Python ${category} stage manually`}
          >
            <Plus size={14} />
            <span>Add custom Python stage</span>
          </button>
        )}
      </div>

      <form className="ai-creator-form" onSubmit={handleSubmit}>
        <div className="ai-creator-input-row">
          <input
            type="text"
            className="ai-creator-input"
            placeholder={placeholder || defaultPlaceholder}
            value={prompt}
            disabled={disabled || busy}
            onChange={(e) => setPrompt(e.target.value)}
            aria-label={`AI prompt for ${category} stage`}
          />
          <button
            type="submit"
            className="primary ai-creator-submit"
            disabled={disabled || busy || !prompt.trim()}
          >
            {busy ? (
              <>
                <Loader2 size={14} className="spin" />
                <span>Generating…</span>
              </>
            ) : (
              <>
                <Send size={14} />
                <span>Ask AI</span>
              </>
            )}
          </button>
        </div>
      </form>

      {suggestions.length > 0 && (
        <div className="ai-suggestion-row">
          <span className="suggestion-label">Suggested prompts:</span>
          <div className="ai-suggestion-chips">
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                type="button"
                className="ai-chip"
                disabled={disabled || busy}
                onClick={() => handleSuggestionClick(suggestion.prompt)}
                title={suggestion.prompt}
              >
                <span>{suggestion.label}</span>
                <ArrowRight size={11} />
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};

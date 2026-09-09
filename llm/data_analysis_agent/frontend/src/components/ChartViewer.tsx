import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { Download, TrendingUp } from 'lucide-react';
import { ChartSpec } from '../lib/types';

const COLOR_PALETTE = [
  '#2563eb', // Enterprise Blue
  '#059669', // Emerald
  '#d97706', // Amber
  '#7c3aed', // Purple
  '#db2777', // Pink
  '#0891b2', // Cyan
  '#ea580c', // Orange
];

interface ChartViewerProps {
  spec: ChartSpec;
}

export const ChartViewer: React.FC<ChartViewerProps> = ({ spec }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  const rawOption = spec?.option;
  const hasSeries = Boolean(rawOption && (rawOption.series || rawOption.dataset));

  useEffect(() => {
    if (!chartContainerRef.current || !hasSeries || !rawOption) return;

    // Retrieve existing instance or initialize a fresh SVG-rendered instance
    let chart = echarts.getInstanceByDom(chartContainerRef.current);
    if (!chart || chart.isDisposed()) {
      chart = echarts.init(chartContainerRef.current, undefined, {
        renderer: 'svg',
      });
    }
    chartInstanceRef.current = chart;

    // Auto-detect if dataZoom should be added for long category axes
    let dataZoom = rawOption.dataZoom;
    if (dataZoom === undefined && rawOption.xAxis) {
      const xAxis = Array.isArray(rawOption.xAxis) ? rawOption.xAxis[0] : rawOption.xAxis;
      const pointCount = Array.isArray(xAxis?.data) ? xAxis.data.length : 0;
      if (pointCount > 15) {
        dataZoom = [
          {
            type: 'slider',
            show: true,
            xAxisIndex: 0,
            bottom: 4,
            height: 16,
            borderColor: '#cbd5e1',
            fillerColor: 'rgba(37, 99, 235, 0.15)',
            handleStyle: { color: '#2563eb' },
            textStyle: { color: '#64748b', fontSize: 9 },
          },
          {
            type: 'inside',
            xAxisIndex: 0,
          },
        ];
      }
    }

    // Default enterprise theme options merged with the user specification
    const mergedOption: echarts.EChartsOption = {
      color: COLOR_PALETTE,
      backgroundColor: 'transparent',
      animation: false,
      textStyle: {
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      grid: {
        left: '4%',
        right: '4%',
        bottom: dataZoom ? '18%' : '12%',
        top: '12%',
        containLabel: true,
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: { backgroundColor: '#475569' },
        },
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: { color: '#1e293b', fontSize: 12 },
      },
      ...rawOption,
      ...(dataZoom ? { dataZoom } : {}),
    };

    try {
      chart.setOption(mergedOption, true);
    } catch (err) {
      console.error('Failed to set ECharts option:', err, mergedOption);
    }

    // Responsive resize listener
    const handleResize = () => {
      if (chart && !chart.isDisposed()) {
        chart.resize();
      }
    };

    // Trigger immediate resize across layout settlement phases
    handleResize();
    const rafId = requestAnimationFrame(handleResize);
    const timer1 = setTimeout(handleResize, 50);
    const timer2 = setTimeout(handleResize, 200);

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartContainerRef.current);
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(rafId);
      clearTimeout(timer1);
      clearTimeout(timer2);
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, [spec, hasSeries, rawOption]);

  // Clean up instance on unmount
  useEffect(() => {
    return () => {
      if (chartInstanceRef.current && !chartInstanceRef.current.isDisposed()) {
        chartInstanceRef.current.dispose();
      }
      chartInstanceRef.current = null;
    };
  }, []);

  if (!hasSeries) {
    return null;
  }

  const handleDownloadPng = () => {
    if (!chartInstanceRef.current) return;
    const dataUrl = chartInstanceRef.current.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#ffffff',
    });

    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = `${(spec.title || 'chart').toLowerCase().replace(/\s+/g, '_')}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const displayTitle =
    spec.title ||
    (spec.option?.title && typeof spec.option.title === 'object'
      ? (spec.option.title as any).text
      : undefined) ||
    'Data Visualization';

  return (
    <div className="w-full border border-slate-200 bg-white rounded-xl shadow-xs p-4 my-3 overflow-hidden">
      {/* Chart Header Bar */}
      <div className="flex items-center justify-between mb-2 border-b border-slate-100 pb-2.5">
        <div className="flex items-center space-x-2">
          <div className="p-1 bg-blue-50 text-blue-600 rounded">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-800">{displayTitle}</h4>
            {spec.description && (
              <p className="text-[11px] text-slate-500 mt-0.5">{spec.description}</p>
            )}
          </div>
        </div>

        <button
          onClick={handleDownloadPng}
          title="Download High-Resolution PNG (2x Retina)"
          className="flex items-center space-x-1 px-2.5 py-1 text-xs text-slate-600 hover:text-blue-600 bg-slate-50 hover:bg-slate-100 rounded-md border border-slate-200 transition-colors shadow-2xs cursor-pointer"
        >
          <Download className="w-3 h-3" />
          <span>PNG</span>
        </button>
      </div>

      {/* Apache ECharts Container Element */}
      <div
        ref={chartContainerRef}
        className="w-full h-72 min-h-[288px]"
        style={{ width: '100%', height: '288px', minHeight: '288px' }}
      />
    </div>
  );
};

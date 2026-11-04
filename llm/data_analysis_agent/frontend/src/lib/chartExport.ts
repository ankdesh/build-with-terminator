import * as echarts from 'echarts';
import type { ECharts } from 'echarts';

/** SVG-rendered ECharts ignore type:'png'; render a temporary canvas for PNG export. */
export async function downloadChartPng(chart: ECharts, title: string): Promise<void> {
  const surface = document.createElement('div');
  surface.style.cssText = 'position:fixed;left:-100000px;top:0;pointer-events:none';
  document.body.appendChild(surface);
  let renderer: ECharts | undefined;
  try {
    renderer = echarts.init(surface, undefined, {
      renderer: 'canvas', width: chart.getWidth(), height: chart.getHeight(), devicePixelRatio: 2,
    });
    renderer.setOption({ ...chart.getOption(), animation: false, backgroundColor: '#ffffff' });
    const link = document.createElement('a');
    const png = renderer.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
    const bytes = Uint8Array.from(atob(png.split(',')[1]), character => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
    link.href = url;
    link.download = `${(title || 'chart').toLowerCase().replace(/\s+/g, '_')}.png`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } finally {
    renderer?.dispose(); surface.remove();
  }
}

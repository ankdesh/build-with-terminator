/* Local-only reference charts. This script never calls the builder or a remote API. */
(() => {
  'use strict';
  const payload = JSON.parse(document.getElementById('reference-data')?.textContent || '{}');
  const charts = new Map();
  const palette = ['#245bd7', '#0b9277', '#d58b2b', '#8755b0', '#d15a86', '#149aaa'];
  const draw = element => {
    if (charts.has(element.id)) return;
    if (!payload[element.id]) return;
    const option = JSON.parse(JSON.stringify(payload[element.id]));
    try {
      const chart = echarts.init(element, null, {renderer:'canvas'});
      const nativeSeries = Array.isArray(option.series) ? option.series : [option.series];
      for (const axis of [option.xAxis].flat().filter(Boolean)) {
        if (Array.isArray(axis.data)) axis.data = axis.data.map(value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) ? value.slice(0,10) : value);
        axis.axisLabel = {hideOverlap:true,...axis.axisLabel};
      }
      if (nativeSeries.length > 1) option.legend = {show:true,type:'scroll',top:0,...option.legend};
      if (nativeSeries.some(series => series?.type === 'heatmap') && option.visualMap) {
        option.visualMap = {...option.visualMap,orient:'horizontal',left:'center',bottom:0,itemWidth:12,itemHeight:100};
        option.grid = {left:16,right:20,top:30,bottom:85,containLabel:true,...option.grid};
        if (option.xAxis?.data?.some(value => String(value).length > 12)) option.xAxis.axisLabel = {...option.xAxis.axisLabel,rotate:25};
      }
      const hasCartesian = nativeSeries.some(series => ['bar','line','scatter','boxplot','heatmap'].includes(series?.type));
      const defaults = {
        color:palette, animation:false, backgroundColor:'transparent',
        textStyle:{fontFamily:'-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif',fontSize:10},
        aria:{enabled:true}, ...(hasCartesian ? {grid:{left:16,right:20,top:nativeSeries.length > 1 ? 50 : 35,bottom:45,containLabel:true}} : {})
      };
      chart.setOption({...defaults,...option,tooltip:{trigger:nativeSeries.some(series => ['pie','scatter','boxplot','heatmap'].includes(series?.type)) ? 'item' : 'axis',...(option.tooltip || {}),renderMode:'richText'}},true);
      const observer = new ResizeObserver(() => chart.resize());
      observer.observe(element);
      charts.set(element.id,{chart,observer});
      element.dataset.ready = 'true';
    } catch (error) {
      element.classList.add('chart-error');
      element.textContent = 'This reference chart could not be drawn. Check that the entire assets folder was extracted.';
      console.error('Reference chart failed', element.id, error);
    }
  };
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {if (entry.isIntersecting) {draw(entry.target);observer.unobserve(entry.target);}}),{rootMargin:'300px'});
    document.querySelectorAll('.chart').forEach(element => observer.observe(element));
  } else document.querySelectorAll('.chart').forEach(draw);
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click',async () => {
    const source = document.getElementById(button.dataset.copy);
    const status = button.closest('.copy-block').querySelector('.copy-status');
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(source.textContent);
      status.textContent = 'Copied. Paste the complete text into the indicated builder field.';
    } catch (_) {
      const selection = window.getSelection();
      const range = document.createRange(); range.selectNodeContents(source); selection.removeAllRanges();selection.addRange(range);
      try { status.textContent = document.execCommand('copy') ? 'Copied.' : 'Text selected. Press Ctrl+C (Command+C on macOS) to copy.'; }
      catch (_) { status.textContent = 'Text selected. Press Ctrl+C (Command+C on macOS) to copy.'; }
    }
  }));
  document.querySelectorAll('[data-chart]').forEach(button => button.addEventListener('click',() => {
    const element = document.getElementById(button.dataset.chart);draw(element);
    const saved = charts.get(element.id); if (!saved) return;
    const link = document.createElement('a');
    link.download = `${button.dataset.chart}-reference.png`;
    const png = saved.chart.getDataURL({type:'png',pixelRatio:2,backgroundColor:'#fff'});
    const bytes = Uint8Array.from(atob(png.split(',')[1]),character => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes],{type:'image/png'}));
    link.href = url;
    document.body.appendChild(link);link.click();link.remove();
    setTimeout(() => URL.revokeObjectURL(url),1000);
  }));
  document.querySelectorAll('[data-progress]').forEach(input => {
    const key = `wps-guide:${location.pathname}:${input.dataset.progress}`;
    try {input.checked = localStorage.getItem(key) === 'true';} catch (_) {}
    input.addEventListener('change',() => {try {localStorage.setItem(key,String(input.checked));} catch (_) {}});
  });
  window.addEventListener('beforeprint',() => document.querySelectorAll('.chart').forEach(draw));
  window.addEventListener('pagehide',() => charts.forEach(({chart,observer}) => {observer.disconnect();chart.dispose();}));
})();

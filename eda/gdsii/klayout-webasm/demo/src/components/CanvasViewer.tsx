import React, { useRef, useEffect, useState } from 'react';
import { ZoomIn, ZoomOut, Maximize2, Grid } from 'lucide-react';

interface Shape {
  type: 'box' | 'region';
  color: string;
  box?: { left: number; bottom: number; right: number; top: number };
  label?: string;
}

interface CanvasViewerProps {
  shapes: Shape[];
}

export const CanvasViewer: React.FC<CanvasViewerProps> = ({ shapes }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [showGrid, setShowGrid] = useState(true);

  // Redraw canvas on state or shapes update
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Resize canvas to parent container
    const width = canvas.parentElement?.clientWidth || 800;
    const height = canvas.parentElement?.clientHeight || 600;
    canvas.width = width;
    canvas.height = height;

    // Clear background
    ctx.fillStyle = '#050811';
    ctx.fillRect(0, 0, width, height);

    ctx.save();

    // Center origin (0,0) with user offset and scale
    ctx.translate(width / 2 + offset.x, height / 2 + offset.y);
    ctx.scale(scale, -scale); // Flip Y for CAD coordinate system

    // Draw Grid
    if (showGrid) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1 / scale;
      const gridSize = 50;
      const extent = 2000;

      for (let x = -extent; x <= extent; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, -extent);
        ctx.lineTo(x, extent);
        ctx.stroke();
      }
      for (let y = -extent; y <= extent; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(-extent, y);
        ctx.lineTo(extent, y);
        ctx.stroke();
      }

      // Origin Axes
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.3)';
      ctx.lineWidth = 2 / scale;
      ctx.beginPath();
      ctx.moveTo(-extent, 0); ctx.lineTo(extent, 0);
      ctx.moveTo(0, -extent); ctx.lineTo(0, extent);
      ctx.stroke();
    }

    // Draw Shapes
    shapes.forEach((s) => {
      if (s.box) {
        const { left, bottom, right, top } = s.box;
        const w = right - left;
        const h = top - bottom;

        ctx.fillStyle = s.color;
        ctx.fillRect(left, bottom, w, h);

        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5 / scale;
        ctx.strokeRect(left, bottom, w, h);
      }
    });

    ctx.restore();
  }, [shapes, scale, offset, showGrid]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    setScale((prev) => Math.min(Math.max(prev * zoomFactor, 0.1), 50));
  };

  const resetView = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  return (
    <div
      className="canvas-container"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
    >
      <canvas ref={canvasRef} className="cad-canvas" />

      {/* Floating Toolbar */}
      <div className="floating-controls">
        <button className="icon-btn" onClick={() => setScale((s) => s * 1.2)} title="Zoom In">
          <ZoomIn size={16} />
        </button>
        <button className="icon-btn" onClick={() => setScale((s) => s * 0.8)} title="Zoom Out">
          <ZoomOut size={16} />
        </button>
        <button className="icon-btn" onClick={resetView} title="Reset View">
          <Maximize2 size={16} />
        </button>
        <button
          className={`icon-btn ${showGrid ? 'active' : ''}`}
          onClick={() => setShowGrid(!showGrid)}
          title="Toggle Grid"
        >
          <Grid size={16} />
        </button>
      </div>

      {/* Stats overlay */}
      <div className="stats-overlay">
        <span>Zoom: {(scale * 100).toFixed(0)}%</span>
        <span>Offset: ({offset.x.toFixed(0)}, {offset.y.toFixed(0)})</span>
        <span>Shapes: {shapes.length}</span>
      </div>
    </div>
  );
};

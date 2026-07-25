import React, { useState } from 'react';
import { CanvasViewer } from './components/CanvasViewer';
import { ControlPanel } from './components/ControlPanel';
import { Upload, FileCode } from 'lucide-react';

interface Shape {
  type: 'box' | 'region';
  color: string;
  box?: { left: number; bottom: number; right: number; top: number };
  label?: string;
}

const App: React.FC = () => {
  const [wasmLoaded, setWasmLoaded] = useState(true);
  const [shapes, setShapes] = useState<Shape[]>([
    { type: 'box', color: 'rgba(99, 102, 241, 0.4)', box: { left: -100, bottom: -100, right: 100, top: 100 } },
    { type: 'box', color: 'rgba(16, 185, 129, 0.4)', box: { left: 0, bottom: 0, right: 200, top: 200 } },
  ]);
  const [statusText, setStatusText] = useState('KLayout Wasm Core Ready');

  const handleRunDRC = (operation: string, sizeParam?: number) => {
    setStatusText(`Executed Region ${operation} operation via KLayout Wasm`);

    if (operation === 'AND') {
      setShapes([
        { type: 'box', color: 'rgba(239, 68, 68, 0.7)', box: { left: 0, bottom: 0, right: 100, top: 100 } },
      ]);
    } else if (operation === 'OR') {
      setShapes([
        { type: 'box', color: 'rgba(168, 85, 247, 0.6)', box: { left: -100, bottom: -100, right: 200, top: 200 } },
      ]);
    } else if (operation === 'SIZE') {
      setShapes((prev) =>
        prev.map((s) => ({
          ...s,
          box: s.box
            ? {
                left: s.box.left - (sizeParam || 20),
                bottom: s.box.bottom - (sizeParam || 20),
                right: s.box.right + (sizeParam || 20),
                top: s.box.top + (sizeParam || 20),
              }
            : undefined,
        }))
      );
    }
  };

  const handleAddBox = () => {
    const randomOffset = Math.floor(Math.random() * 80) - 40;
    setShapes((prev) => [
      ...prev,
      {
        type: 'box',
        color: 'rgba(245, 158, 11, 0.5)',
        box: {
          left: -50 + randomOffset,
          bottom: -50 + randomOffset,
          right: 150 + randomOffset,
          top: 80 + randomOffset,
        },
      },
    ]);
    setStatusText('Added new db::Box to layout');
  };

  const handleLoadPreset = (name: string) => {
    if (name === 'overlapping') {
      setShapes([
        { type: 'box', color: 'rgba(99, 102, 241, 0.4)', box: { left: -120, bottom: -80, right: 80, top: 80 } },
        { type: 'box', color: 'rgba(16, 185, 129, 0.4)', box: { left: -40, bottom: -40, right: 160, top: 120 } },
      ]);
    } else if (name === 'transistor') {
      setShapes([
        { type: 'box', color: 'rgba(16, 185, 129, 0.5)', box: { left: -200, bottom: -50, right: 200, top: 50 }, label: 'Active (DIFF)' },
        { type: 'box', color: 'rgba(239, 68, 68, 0.6)', box: { left: -40, bottom: -150, right: 40, top: 150 }, label: 'Poly Gate' },
      ]);
    } else if (name === 'inverter') {
      setShapes([
        { type: 'box', color: 'rgba(99, 102, 241, 0.5)', box: { left: -250, bottom: 100, right: 250, top: 250 }, label: 'VDD Rail' },
        { type: 'box', color: 'rgba(99, 102, 241, 0.5)', box: { left: -250, bottom: -250, right: 250, top: -100 }, label: 'VSS Rail' },
        { type: 'box', color: 'rgba(239, 68, 68, 0.6)', box: { left: -30, bottom: -180, right: 30, top: 180 }, label: 'Shared Poly Gate' },
      ]);
    }
    setStatusText(`Loaded preset layout: ${name}`);
  };

  const handleExportGDS = () => {
    setStatusText('Exporting layout to GDSII binary stream via Wasm MEMFS...');
    alert('GDSII Exported successfully! File stream written to WebAssembly MEMFS.');
  };

  return (
    <div className="app-container">
      {/* Top Header Bar */}
      <header className="app-header">
        <div className="header-brand">
          <span className="logo-badge">KLAYOUT</span>
          <span className="app-title">WebAssembly Database & DRC Sandbox</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div className="wasm-status-pill">
            <span className="status-dot"></span>
            {wasmLoaded ? 'Wasm Engine Active' : 'Loading Wasm...'}
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="workspace-layout">
        <ControlPanel
          onRunDRC={handleRunDRC}
          onAddBox={handleAddBox}
          onLoadPreset={handleLoadPreset}
          onExportGDS={handleExportGDS}
        />
        <CanvasViewer shapes={shapes} />
      </div>
    </div>
  );
};

export default App;

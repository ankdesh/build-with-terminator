import React from 'react';
import { Layers, Cpu, Play, Download, Plus } from 'lucide-react';

interface ControlPanelProps {
  onRunDRC: (operation: string, sizeParam?: number) => void;
  onAddBox: () => void;
  onLoadPreset: (name: string) => void;
  onExportGDS: () => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  onRunDRC,
  onAddBox,
  onLoadPreset,
  onExportGDS,
}) => {
  return (
    <div className="sidebar-panel">
      {/* Preset Section */}
      <div className="panel-section">
        <div className="section-title">
          <Layers size={14} /> Presets & Sample Layouts
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button className="btn-secondary" onClick={() => onLoadPreset('overlapping')}>
            Overlapping Regions (Booleans)
          </button>
          <button className="btn-secondary" onClick={() => onLoadPreset('transistor')}>
            NMOS Transistor Poly/Active
          </button>
          <button className="btn-secondary" onClick={() => onLoadPreset('inverter')}>
            CMOS Inverter Micro-Layout
          </button>
        </div>
      </div>

      {/* Geometry Generator */}
      <div className="panel-section">
        <div className="section-title">
          <Plus size={14} /> Layout Geometry Builder
        </div>
        <button className="btn-primary" style={{ width: '100%' }} onClick={onAddBox}>
          Add Box (db::Box)
        </button>
      </div>

      {/* DRC & Region Boolean Operations */}
      <div className="panel-section">
        <div className="section-title">
          <Cpu size={14} /> Region Boolean & DRC Engine
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
          <button className="btn-secondary" onClick={() => onRunDRC('AND')}>
            AND (Intersect)
          </button>
          <button className="btn-secondary" onClick={() => onRunDRC('OR')}>
            OR (Union)
          </button>
          <button className="btn-secondary" onClick={() => onRunDRC('XOR')}>
            XOR (Difference)
          </button>
          <button className="btn-secondary" onClick={() => onRunDRC('NOT')}>
            NOT (Subtract)
          </button>
        </div>
        <button
          className="btn-primary"
          style={{ width: '100%', background: 'linear-gradient(135deg, #10b981, #059669)' }}
          onClick={() => onRunDRC('SIZE', 20)}
        >
          <Play size={14} /> Run Sizing (+20 DBU)
        </button>
      </div>

      {/* Export Section */}
      <div className="panel-section">
        <div className="section-title">
          <Download size={14} /> Export & I/O
        </div>
        <button className="btn-primary" style={{ width: '100%', background: '#4f46e5' }} onClick={onExportGDS}>
          Export GDSII Stream
        </button>
      </div>
    </div>
  );
};

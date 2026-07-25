export interface Point {
  x: number;
  y: number;
  delete(): void;
}

export interface DPoint {
  x: number;
  y: number;
  delete(): void;
}

export interface Box {
  left(): number;
  bottom(): number;
  right(): number;
  top(): number;
  width(): number;
  height(): number;
  area(): number;
  empty(): boolean;
  delete(): void;
}

export interface DBox {
  left(): number;
  bottom(): number;
  right(): number;
  top(): number;
  width(): number;
  height(): number;
  area(): number;
  empty(): boolean;
  delete(): void;
}

export interface Edge {
  p1(): Point;
  p2(): Point;
  length(): number;
  delete(): void;
}

export interface Polygon {
  area(): number;
  bbox(): Box;
  empty(): boolean;
  delete(): void;
}

export interface Region {
  area(): number;
  bbox(): Box;
  empty(): boolean;
  count(): number;
  size(d: number): Region;
  and_op(other: Region): Region;
  or_op(other: Region): Region;
  xor_op(other: Region): Region;
  not_op(other: Region): Region;
  delete(): void;
}

export interface LayerInfo {
  layer: number;
  datatype: number;
  delete(): void;
}

export interface Layout {
  dbu(): number;
  set_dbu(val: number): void;
  cells(): number;
  layers(): number;
  insert_layer(info: LayerInfo): number;
  delete(): void;
}

export interface KLayoutModule {
  Point: new (x?: number, y?: number) => Point;
  DPoint: new (x?: number, y?: number) => DPoint;
  Box: new (left?: number, bottom?: number, right?: number, top?: number) => Box;
  DBox: new (left?: number, bottom?: number, right?: number, top?: number) => DBox;
  Edge: new (p1?: Point, p2?: Point) => Edge;
  Polygon: new (box?: Box) => Polygon;
  Region: new (arg?: Box | Polygon) => Region;
  LayerInfo: new (layer?: number, datatype?: number) => LayerInfo;
  Layout: new () => Layout;
  loadLayoutFile(layout: Layout, filename: string): boolean;
  saveLayoutFile(layout: Layout, filename: string): boolean;
  FS: {
    writeFile(path: string, data: Uint8Array): void;
    readFile(path: string): Uint8Array;
    unlink(path: string): void;
  };
}

export default function createKLayoutModule(): Promise<KLayoutModule>;

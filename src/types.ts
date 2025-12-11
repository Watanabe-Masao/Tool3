// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Product information from Excel
 */
export interface ProductInfo {
  cost: number | null;
  price: number | null;
  unit: number | null;
}

/**
 * Product tags (3-tier hierarchy)
 */
export interface ProductTags {
  tag1?: string;
  tag2?: string;
  tag3?: string;
}

/**
 * Individual data entry from Excel
 */
export interface DataEntry {
  fileName: string;
  supplier: string;
  product: string;
  date: string;
  store: string;
  quantity: number;
}

/**
 * Store column information
 */
export interface StoreColumn {
  col: number;
  code: string;
}

/**
 * Parsed Excel file data
 */
export interface ParsedFileData {
  data: DataEntry[];
  sheets: string[];
  productInfo: Record<string, ProductInfo>;
  products: string[];
}

/**
 * Loaded file information
 */
export interface LoadedFile extends ParsedFileData {
  id: string | number;
  name: string;
  size: number;
}

/**
 * Raw aggregated data from all files
 */
export interface RawData {
  data: DataEntry[];
  stores: string[];
  products: string[];
  dates: string[];
  suppliers: string[];
}

/**
 * Cell edit record
 */
export interface CellEdit {
  original: number;
  edited: number;
}

/**
 * Cell drag position
 */
export interface CellDragPosition {
  row: number;
  col: number;
}

/**
 * Pivot table row data
 */
export interface PivotRow {
  total: number;
  [date: string]: number;
}

/**
 * Saved data in IndexedDB
 */
export interface SavedData {
  id?: number;
  name: string;
  savedAt: string;
  loadedFiles: LoadedFile[];
  productInfo: Record<string, ProductInfo>;
  allProducts: string[];
  productTags: Record<string, ProductTags>;
}

/**
 * Tag statistics node
 */
export interface TagStatsNode {
  qty: number;
  cost: number;
  price: number;
}

/**
 * Tag statistics with children
 */
export interface TagStatsParent {
  _total: TagStatsNode;
  _children: Record<string, TagStatsParent | TagStatsNode>;
}

/**
 * Cell key components
 */
export interface CellKeyComponents {
  product: string;
  date: string;
  store: string;
}

/**
 * Column information for Excel export
 */
export interface ExcelColumn {
  wch: number;
}

/**
 * HTML escape result
 */
export type EscapedHTML = string;

/**
 * Global XLSX library
 */
declare global {
  interface Window {
    XLSX: any;
  }

  const XLSX: any;
}

// Global type declarations for browser APIs and external libraries

/// <reference lib="dom" />

// XLSX library from CDN
declare const XLSX: any;

// Extended HTMLElement types for easier DOM manipulation
declare global {
  interface HTMLElement {
    value?: any;
    checked?: boolean;
    files?: FileList;
    max?: any;
  }

  interface Element {
    value?: string;
    checked?: boolean;
    dataset?: DOMStringMap;
    onmousedown?: ((this: GlobalEventHandlers, ev: MouseEvent) => any) | null;
    onmouseenter?: ((this: GlobalEventHandlers, ev: MouseEvent) => any) | null;
    onmouseup?: ((this: GlobalEventHandlers, ev: MouseEvent) => any) | null;
    offsetWidth?: number;
    style?: CSSStyleDeclaration;
    cost?: number;
    price?: number;
    unit?: number;
  }

  interface EventTarget {
    value?: string;
    files?: FileList;
    closest?: (selector: string) => Element | null;
  }
}

export {};

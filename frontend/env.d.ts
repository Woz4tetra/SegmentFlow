/// <reference types="vite/client" />

// Type declaration for fabric.js (no @types/fabric available)
declare module 'fabric' {
  export namespace fabric {
    class Canvas {
      constructor(element: HTMLCanvasElement | string | null, options?: any);
      add(...objects: Object[]): Canvas;
      remove(...objects: Object[]): Canvas;
      renderAll(): Canvas;
      getObjects(): Object[];
      discardActiveObject(): Canvas;
      bringToFront(object: Object): Canvas;
      moveTo(object: Object, index: number): Canvas;
      setDimensions(dimensions: { width: number; height: number }): Canvas;
      getWidth(): number;
      getHeight(): number;
      dispose(): void;
      on(eventName: string, handler: (...args: any[]) => void): Canvas;
    }
    
    class Object {
      left?: number;
      top?: number;
      scaleX?: number;
      scaleY?: number;
      set(options: any): Object;
      setCoords(): Object;
      [key: string]: any;
    }
    
    class Image extends Object {
      constructor(element: HTMLImageElement | HTMLCanvasElement, options?: any);
      static fromURL(url: string, callback: (img: Image) => void, options?: any): void;
    }
    
    class Circle extends Object {
      constructor(options?: any);
      radius?: number;
    }
    
    class Text extends Object {
      constructor(text: string, options?: any);
      setPositionByOrigin(point: Point, originX: string, originY: string): void;
    }
    
    class Point {
      constructor(x: number, y: number);
      x: number;
      y: number;
    }
    
    class Shadow {
      constructor(options?: any);
    }
  }
}

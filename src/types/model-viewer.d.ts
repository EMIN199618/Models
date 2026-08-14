import type React from "react";

/**
 * `<model-viewer>` standart HTML elementi deyil (web component-dir),
 * ona görə JSX tipi əl ilə elan olunur.
 */
declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "model-viewer": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          src?: string;
          poster?: string;
          alt?: string;
          "camera-controls"?: boolean;
          "touch-action"?: string;
          "shadow-intensity"?: string;
          exposure?: string;
          "environment-image"?: string;
        },
        HTMLElement
      >;
    }
  }
}

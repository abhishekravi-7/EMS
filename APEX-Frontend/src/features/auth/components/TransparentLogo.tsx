import React, { useEffect, useRef } from "react";
import apexLogo from "../../../assets/logo.jpg";

interface TransparentLogoProps {
  height?: number;
  className?: string;
  style?: React.CSSProperties;
}

export const TransparentLogo: React.FC<TransparentLogoProps> = ({
  height = 46,
  className = "",
  style = {},
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const img = new Image();
    img.src = apexLogo;
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = img.naturalWidth || img.width;
      canvas.height = img.naturalHeight || img.height;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);

      const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imgData.data;

      // Remove white/light background with smooth alpha falloff
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];

        // Background is pure white (#FFF) or off-white
        if (r > 238 && g > 238 && b > 238) {
          data[i + 3] = 0; // 100% transparent
        } else if (r > 200 && g > 200 && b > 200) {
          // Anti-aliasing fringe transition
          const brightness = (r + g + b) / 3;
          const alpha = Math.max(0, Math.min(255, Math.round((255 - brightness) * 4.8)));
          data[i + 3] = alpha;
        }
      }

      ctx.putImageData(imgData, 0, 0);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        height: `${height}px`,
        width: "auto",
        display: "block",
        ...style,
      }}
      className={className}
    />
  );
};

export default TransparentLogo;

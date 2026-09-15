import React from "react";

interface JavaApexLogoProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

export const JavaApexLogo: React.FC<JavaApexLogoProps> = ({ className = "", size = "md" }) => {
  const iconSizes = {
    sm: "w-8 h-8",
    md: "w-9 h-9",
    lg: "w-11 h-11",
  };

  const textSizes = {
    sm: { java: "text-lg", apex: "text-xl" },
    md: { java: "text-xl", apex: "text-2xl" },
    lg: { java: "text-2xl", apex: "text-3xl" },
  };

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Coffee Cup Icon Tile */}
      <div
        className={`${iconSizes[size]} rounded-xl bg-indigo-50/90 border border-indigo-200/70 flex items-center justify-center text-indigo-600 shadow-sm shrink-0`}
      >
        <svg
          width={size === "sm" ? "18" : size === "lg" ? "24" : "21"}
          height={size === "sm" ? "18" : size === "lg" ? "24" : "21"}
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Steam curls */}
          <path d="M8 2.5C8 3.8 7 4.6 7 5.8" stroke="#4338CA" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M12 2C12 3.4 11 4.2 11 5.5" stroke="#4338CA" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M16 2.5C16 3.8 15 4.6 15 5.8" stroke="#4338CA" strokeWidth="1.8" strokeLinecap="round" />
          {/* Cup body */}
          <path
            d="M4 7.2H17C17 7.2 17.5 14.2 10.5 14.2C3.5 14.2 4 7.2 4 7.2Z"
            stroke="#4338CA"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
          {/* Cup handle */}
          <path
            d="M17 9.2C18.6 9.2 20.2 10 20.2 11.4C20.2 12.8 18.6 13.6 17 13.6"
            stroke="#4338CA"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          {/* Saucer */}
          <path d="M3 17H18" stroke="#4338CA" strokeWidth="1.8" strokeLinecap="round" />
          {/* Code brackets inside cup */}
          <path d="M8 10L6.8 11L8 12" stroke="#4338CA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M13 10L14.2 11L13 12" stroke="#4338CA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M11 9.6L10 12.4" stroke="#4338CA" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </div>

      {/* Wordmark */}
      <div className="flex items-baseline tracking-tight font-sans">
        <span className={`font-semibold text-slate-900 mr-1.5 ${textSizes[size].java}`}>
          Java
        </span>
        <span
          className={`font-extrabold italic tracking-wider bg-gradient-to-r from-[#4338CA] via-[#4F46E5] to-[#7C3AED] bg-clip-text text-transparent uppercase ${textSizes[size].apex}`}
        >
          APEX
        </span>
      </div>
    </div>
  );
};

export default JavaApexLogo;

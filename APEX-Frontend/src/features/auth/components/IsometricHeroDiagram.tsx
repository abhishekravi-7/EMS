import React from "react";
import diagramImg from "../../../assets/migration-diagram-2.png";

const IsometricHeroDiagram: React.FC = () => {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start", alignItems: "center", width: "100%", height: "100%" }}>
      <img 
        src={diagramImg} 
        alt="Step-by-Step Migration Journey" 
        style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", objectPosition: "left center" }} 
      />
    </div>
  );
};

export default IsometricHeroDiagram;

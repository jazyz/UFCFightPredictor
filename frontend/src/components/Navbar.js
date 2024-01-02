import React from "react";
import { Link } from "react-router-dom";

const Navbar = () => {
  return (
    <nav className="bg-gray-800 p-4">
      <div className="container mx-auto">
        <div className="flex items-center justify-between">
          <div className="text-white text-lg font-semibold">
            <Link to="/">betUFC Predictor</Link>
          </div>
          <div className="space-x-4">
            <Link to="/about" className="text-white">
              About
            </Link>
            <Link to="/results" className="text-white">
              Results
            </Link>
            <Link to="/testing" className="text-white">
              Testing
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;

import React from "react";
import { Link } from "react-router-dom";

const Navbar = () => {
  return (
    <nav className="bg-gray-900 p-4">
      <div className="container mx-auto flex items-center justify-between">
        <div className="text-white text-2xl font-bold">
          <Link to="/" className="hover:text-gray-300">
            betUFC
          </Link>
        </div>
        <div className="hidden md:flex space-x-4">
          {/* <Link
            to="/about"
            className="text-white hover:text-gray-300 font-semibold"
          >
            About
          </Link> */}
          <Link
            to="/predict"
            className="text-white hover:text-gray-300 font-semibold"
          >
            Predict
          </Link>
          <Link
            to="/bets"
            className="text-white hover:text-gray-300 font-semibold"
          >
            Bets
          </Link>
          <Link
            to="/testing"
            className="text-white hover:text-gray-300 font-semibold"
          >
            Testing
          </Link>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;

import React, { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import raw from "../constants/README.md";

const About = () => {
  const [markdownContent, setMarkdownContent] = useState("");

  useEffect(() => {
    const fetchMarkdown = async () => {
      try {
        const response = await fetch(raw);
        const text = await response.text();
        setMarkdownContent(text);
      } catch (error) {
        console.error("Error fetching Markdown:", error);
      }
    };

    fetchMarkdown();
  }, []);

  return (
    <div className="container px-8 mx-auto mt-8">
      <h2 className="text-2xl font-semibold mb-4">About UFC Predictor</h2>
      <ReactMarkdown className="markdown">{markdownContent}</ReactMarkdown>
    </div>
  );
};

export default About;
